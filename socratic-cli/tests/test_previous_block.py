"""Tests para `socratic previous-block <study-id>`."""
from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from socratic.app import create_app
from socratic_cli.client import SocraticClient
from socratic_cli.main import main as cli_main


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        app = create_app(self.db_path)
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="warning"
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        while not self._server.started:
            time.sleep(0.01)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            if self._thread is not None:
                self._thread.join(timeout=10)


def _setup_study(tmp_path: Path, server: _Server):
    """Crea un PDF con 3 páginas (3 bloques), lo sube y crea un estudio.
    Devuelve (study_id, document_id)."""
    sample_pdf = tmp_path / "sample.pdf"
    pdf = __import__("fpdf").FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(
        200, 10, "Primer párrafo del documento de prueba.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(
        200, 10, "Segundo párrafo con contenido diferente.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(
        200, 10, "Tercer párrafo para probar consecutividad.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.output(str(sample_pdf))

    rc = cli_main(["--url", server.url, "upload", str(sample_pdf)])
    assert rc == 0

    with SocraticClient(server.url) as c:
        docs = c.list_documents()
        document_id = docs[0]["id"]
        study = c.create_study(document_id)
        study_id = study["id"]

    return study_id, document_id


# --- Tests ---


def test_previous_block_moves_back(tmp_path: Path):
    """Completa bloque 1, previous-block muestra bloque 0 y avanza current_block."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        study_id, _ = _setup_study(tmp_path, server)

        # Avanzar al segundo bloque
        result1 = cli_main(["--url", server.url, "next-block", study_id])
        assert result1 == 0

        # previous-block debe mostrar el primer bloque Y actualizar current_block
        result2 = cli_main(["--url", server.url, "previous-block", study_id])
        assert result2 == 0

        with SocraticClient(server.url) as c:
            current = c.get_current_block(study_id)
            assert "Primer párrafo del documento de prueba." in current["text"]
    finally:
        server.stop()


def test_previous_block_uses_previous_ordinal(tmp_path: Path):
    """Se usa el bloque anterior por ordinal, no por ID."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        study_id, _ = _setup_study(tmp_path, server)

        # Avanzar al tercer bloque
        cli_main(["--url", server.url, "next-block", study_id])
        cli_main(["--url", server.url, "next-block", study_id])

        # previous-block debe mostrar el segundo bloque (ordinal 2)
        result = cli_main(["--url", server.url, "previous-block", study_id])
        assert result == 0

        # current_block debe haber cambiado al segundo bloque
        with SocraticClient(server.url) as c:
            current = c.get_current_block(study_id)
            assert "Segundo párrafo con contenido diferente." in current["text"]
    finally:
        server.stop()


def test_previous_block_consecutive_moves_back_twice(tmp_path: Path):
    """Dos llamadas consecutivas retroceden bloques distintos."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        study_id, _ = _setup_study(tmp_path, server)

        # Avanzar al tercer bloque
        cli_main(["--url", server.url, "next-block", study_id])
        cli_main(["--url", server.url, "next-block", study_id])

        # Verificar que estamos en el tercer bloque
        with SocraticClient(server.url) as c:
            before = c.get_current_block(study_id)
            assert "Tercer párrafo" in before["text"]

        # Primer retroceso: segundo bloque
        result1 = cli_main(["--url", server.url, "previous-block", study_id])
        assert result1 == 0

        with SocraticClient(server.url) as c:
            after1 = c.get_current_block(study_id)
            assert "Segundo párrafo" in after1["text"]

        # Segundo retroceso: primer bloque
        result2 = cli_main(["--url", server.url, "previous-block", study_id])
        assert result2 == 0

        with SocraticClient(server.url) as c:
            after2 = c.get_current_block(study_id)
            assert "Primer párrafo" in after2["text"]
    finally:
        server.stop()


def test_previous_block_first_block_error(tmp_path: Path):
    """Ya en primer bloque → stderr 'Ya estás en el primer bloque.' → return 1."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        study_id, _ = _setup_study(tmp_path, server)

        # No hemos avanzado, estamos en el primer bloque
        result = cli_main(["--url", server.url, "previous-block", study_id])
        assert result == 1
    finally:
        server.stop()


def test_previous_block_from_end_of_document(tmp_path: Path):
    """Retroceder desde el final del documento (current_block_id es None)."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        study_id, _ = _setup_study(tmp_path, server)

        # Avanzar hasta el final del documento
        cli_main(["--url", server.url, "next-block", study_id])
        cli_main(["--url", server.url, "next-block", study_id])
        cli_main(["--url", server.url, "next-block", study_id])

        # Ahora current_block_id es None, last_completed_block_id es el bloque 3
        with SocraticClient(server.url) as c:
            study = c.get_study(study_id)
            assert study["current_block_id"] is None
            assert study["last_completed_block_id"] is not None

        # previous-block debe retroceder al bloque 3
        result = cli_main(["--url", server.url, "previous-block", study_id])
        assert result == 0

        with SocraticClient(server.url) as c:
            current = c.get_current_block(study_id)
            assert "Tercer párrafo" in current["text"]
    finally:
        server.stop()


def test_previous_block_study_not_found(tmp_path: Path):
    """Study inexistente (404) → error → return 1."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        study_id = "00000000-0000-0000-0000-000000000000"

        result = cli_main(["--url", server.url, "previous-block", study_id])
        assert result == 1
    finally:
        server.stop()


def test_previous_block_no_state_change(tmp_path: Path):
    """previous-block actualiza current_block_id al bloque anterior."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        study_id, _ = _setup_study(tmp_path, server)

        # Avanzar al segundo bloque
        cli_main(["--url", server.url, "next-block", study_id])

        with SocraticClient(server.url) as c:
            before = c.get_study(study_id)
            current_before = before["current_block_id"]

        # previous-block debe cambiar current_block_id
        result = cli_main(["--url", server.url, "previous-block", study_id])
        assert result == 0

        with SocraticClient(server.url) as c:
            after = c.get_study(study_id)
            assert after["current_block_id"] != current_before
            # Debería estar en el primer bloque
            current = c.get_current_block(study_id)
            assert "Primer párrafo" in current["text"]
    finally:
        server.stop()


def test_previous_block_stdout_only_text(tmp_path: Path):
    """stdout en modo normal contiene SOLO el texto del bloque."""
    server = _Server(tmp_path / "socratic.db")
    server.start()
    try:
        # Crear PDF con texto identificable
        sample_pdf = tmp_path / "stdout_sample.pdf"
        pdf = __import__("fpdf").FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(
            200, 10, "Texto del primer bloque.",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(
            200, 10, "Texto del segundo bloque.",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.output(str(sample_pdf))

        cli_main(["--url", server.url, "upload", str(sample_pdf)])

        with SocraticClient(server.url) as c:
            docs = c.list_documents()
            study = c.create_study(docs[0]["id"])
            study_id = study["id"]

        # Avanzar al segundo bloque
        cli_main(["--url", server.url, "next-block", study_id])

        import subprocess
        import sys

        cli_dir = str(Path(__file__).resolve().parent.parent)
        env = __import__("os").environ.copy()
        env["PYTHONPATH"] = cli_dir

        result = subprocess.run(
            [
                sys.executable, "-m", "socratic_cli",
                "--url", server.url,
                "previous-block", study_id,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            cwd=cli_dir,
        )
        assert result.returncode == 0

        stdout = result.stdout.strip()
        assert "Texto del primer bloque." in stdout
        assert "block_id" not in stdout
        assert "ordinal" not in stdout
        assert "page" not in stdout
        assert "type" not in stdout
    finally:
        server.stop()
