"""Hito 3 — Persistencia extremo a extremo vía CLI.

Levanta el servidor real con uvicorn en un hilo, ejecuta el flujo completo con
la CLI (cargar PDF, crear estudio, leer bloque, completar, preguntar), reinicia
el servidor sobre la misma BD y verifica con la CLI que el estado se conservó.
"""
from __future__ import annotations

import socket
import sys
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

    def restart(self) -> None:
        self.stop()
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.start()


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    from fpdf import FPDF

    pdf_path = tmp_path / "sample.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, "Título del documento de prueba", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 10, "Primer párrafo de contenido.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(200, 10, "Segundo párrafo con más texto.", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(pdf_path))
    return pdf_path


def test_cli_flow_survives_server_restart(tmp_path: Path, sample_pdf: Path):
    db_path = tmp_path / "socratic.db"
    server = _Server(db_path)
    server.start()
    try:
        # --- Sesión 1: flujo completo vía CLI ---
        rc = cli_main(["--url", server.url, "upload", str(sample_pdf)])
        assert rc == 0

        rc = cli_main(["--url", server.url, "documents"])
        assert rc == 0

        # Necesitamos los IDs; los obtenemos vía el cliente directo.
        with SocraticClient(server.url) as c:
            docs = c.list_documents()
            assert len(docs) == 1
            document_id = docs[0]["id"]

            study = c.create_study(document_id)
            study_id = study["id"]
            first_block_id = study["current_block_id"]

        rc = cli_main(["--url", server.url, "study", study_id])
        assert rc == 0

        rc = cli_main(["--url", server.url, "current-block", study_id])
        assert rc == 0

        rc = cli_main(
            ["--url", server.url, "complete-block", study_id, first_block_id]
        )
        assert rc == 0

        rc = cli_main(
            [
                "--url",
                server.url,
                "message",
                study_id,
                "¿De qué trata el título?",
                "--role",
                "user",
            ]
        )
        assert rc == 0

        rc = cli_main(
            [
                "--url",
                server.url,
                "message",
                study_id,
                "Trata de una prueba.",
                "--role",
                "assistant",
            ]
        )
        assert rc == 0

        with SocraticClient(server.url) as c:
            study_before = c.get_study(study_id)
            second_block_id = study_before["current_block_id"]
            messages_before = c.list_messages(study_id)

        # --- Reinicio del servidor sobre la misma BD ---
        server.restart()

        # --- Sesión 2: verificar que el estado se conservó ---
        with SocraticClient(server.url) as c:
            docs_after = c.list_documents()
            assert len(docs_after) == 1
            assert docs_after[0]["id"] == document_id
            assert docs_after[0]["block_count"] == docs[0]["block_count"]

            study_after = c.get_study(study_id)
            assert study_after["last_completed_block_id"] == first_block_id
            assert study_after["current_block_id"] == second_block_id

            current = c.get_current_block(study_id)
            assert current["id"] == second_block_id

            messages_after = c.list_messages(study_id)
            assert len(messages_after) == len(messages_before)
            assert messages_after[0]["role"] == "user"
            assert messages_after[0]["content"] == "¿De qué trata el título?"
            assert messages_after[1]["role"] == "assistant"

        # Verificar también vía CLI que los comandos siguen funcionando
        rc = cli_main(["--url", server.url, "documents"])
        assert rc == 0

        rc = cli_main(["--url", server.url, "study", study_id])
        assert rc == 0

        rc = cli_main(["--url", server.url, "current-block", study_id])
        assert rc == 0

        rc = cli_main(["--url", server.url, "messages", study_id])
        assert rc == 0
    finally:
        server.stop()


def test_cli_help_smoke():
    """`python -m socratic_cli --help` debe listar los subcomandos."""
    import subprocess

    cli_dir = str(Path(__file__).resolve().parent.parent)
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "PYTHONPATH": cli_dir,
    }
    result = subprocess.run(
        [sys.executable, "-m", "socratic_cli", "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0
    assert "upload" in result.stdout
    assert "current-block" in result.stdout
    assert "complete-block" in result.stdout
    assert "messages" in result.stdout
