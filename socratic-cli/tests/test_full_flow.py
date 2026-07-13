"""Hito 5 — Validación del flujo completo.

La CLI ejecuta el flujo completo con un PDF real:
  cargar PDF → crear estudio → leer bloques → preguntar → continuar
  → cerrar y reiniciar → recuperar posición.
"""
from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from socratic.app import create_app
from socratic.llm.base import LLMClient
from socratic_cli.client import SocraticClient
from socratic_cli.main import main as cli_main


class _StubLLM(LLMClient):
    """LLM stub para pruebas sin llamadas a proveedores reales."""

    def __init__(self, response: str = "Este documento trata sobre algoritmos de ordenamiento.") -> None:
        self.response = response

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return self.response


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    def __init__(self, db_path: Path, llm: LLMClient | None = None):
        self.db_path = db_path
        self.llm = llm
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        app = create_app(self.db_path, llm_client=self.llm)
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


def _create_sample_pdf(path: Path) -> Path:
    """Crea un PDF de prueba con varios párrafos."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(
        200, 10, "Introducción a los algoritmos de ordenamiento",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(
        200, 10, "Los algoritmos de ordenamiento son fundamentales en la",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(
        200, 10, "ciencia de la computación. Permiten organizar datos",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(
        200, 10, "en secuencias ordenadas según criterios específicos.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.add_page()
    pdf.cell(
        200, 10, "El algoritmo de burbuja es uno de los más simples.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(
        200, 10, "Comparar elementos adyacentes e intercambiarlos",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(
        200, 10, "si están en el orden incorrecto.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.output(str(path))
    return path


def test_full_flow_with_ask_and_restart(tmp_path: Path):
    """Flujo completo: upload → create-study → read → ask → continue → restart → verify."""
    sample_pdf = _create_sample_pdf(tmp_path / "sample.pdf")
    assert sample_pdf.exists(), f"sample_pdf no existe: {sample_pdf}"

    db_path = tmp_path / "socratic.db"
    stub_llm = _StubLLM()
    server = _Server(db_path, llm=stub_llm)
    server.start()
    try:
        # ---- Sesión 1: flujo completo vía CLI ----

        # 1. Cargar PDF
        rc = cli_main(["--url", server.url, "upload", str(sample_pdf)])
        assert rc == 0

        # 2. Listar documentos
        rc = cli_main(["--url", server.url, "documents"])
        assert rc == 0

        # 3. Obtener IDs con el cliente
        with SocraticClient(server.url) as c:
            docs = c.list_documents()
            assert len(docs) == 1
            document_id = docs[0]["id"]
            assert docs[0]["block_count"] >= 6

            # 4. Crear estudio
            study = c.create_study(document_id)
            study_id = study["id"]
            first_block_id = study["current_block_id"]
            assert study["last_completed_block_id"] is None

        # 5. Consultar estado del estudio
        rc = cli_main(["--url", server.url, "study", study_id])
        assert rc == 0

        # 6. Leer primer bloque (current-block no avanza)
        rc = cli_main(["--url", server.url, "current-block", study_id])
        assert rc == 0

        # 7. Marcar primer bloque como completado → avanza al segundo
        rc = cli_main(
            ["--url", server.url, "complete-block", study_id, first_block_id]
        )
        assert rc == 0

        # 8. Leer segundo bloque
        with SocraticClient(server.url) as c:
            study_after_complete = c.get_study(study_id)
            second_block_id = study_after_complete["current_block_id"]
            assert second_block_id != first_block_id

        rc = cli_main(["--url", server.url, "current-block", study_id])
        assert rc == 0

        # 9. Hacer una pregunta sobre el bloque actual vía ask
        rc = cli_main(
            ["--url", server.url, "ask", study_id, "¿De qué trata este documento?"]
        )
        assert rc == 0

        # 10. Verificar que se guardaron los mensajes (pregunta + respuesta)
        with SocraticClient(server.url) as c:
            messages = c.list_messages(study_id)
            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "¿De qué trata este documento?"
            assert messages[1]["role"] == "assistant"
            assert len(messages[1]["content"]) > 0

            # 11. El bloque actual NO cambió tras la pregunta
            study_after_ask = c.get_study(study_id)
            assert study_after_ask["current_block_id"] == second_block_id

        # 12. Continuar lectura: marcar segundo bloque como completado
        rc = cli_main(
            ["--url", server.url, "complete-block", study_id, second_block_id]
        )
        assert rc == 0

        # 13. Verificar que se avanzó al tercer bloque
        with SocraticClient(server.url) as c:
            study_after_continue = c.get_study(study_id)
            third_block_id = study_after_continue["current_block_id"]
            assert third_block_id != second_block_id
            assert study_after_continue["last_completed_block_id"] == second_block_id

        # 14. Leer tercer bloque
        rc = cli_main(["--url", server.url, "current-block", study_id])
        assert rc == 0

        # ---- Reinicio del servidor sobre la misma BD ----
        server.restart()

        # ---- Sesión 2: verificar que el estado se conservó ----

        # 15. Listar documentos
        rc = cli_main(["--url", server.url, "documents"])
        assert rc == 0

        with SocraticClient(server.url) as c:
            docs_after = c.list_documents()
            assert len(docs_after) == 1
            assert docs_after[0]["id"] == document_id
            assert docs_after[0]["block_count"] >= 6

            # 16. Verificar estudio
            study_after = c.get_study(study_id)
            assert study_after["last_completed_block_id"] == second_block_id
            assert study_after["current_block_id"] == third_block_id

            # 17. Verificar bloque actual
            current = c.get_current_block(study_id)
            assert current["id"] == third_block_id

            # 18. Verificar mensajes conservados
            messages_after = c.list_messages(study_id)
            assert len(messages_after) == 2
            assert messages_after[0]["role"] == "user"
            assert messages_after[0]["content"] == "¿De qué trata este documento?"
            assert messages_after[1]["role"] == "assistant"

        # 19. Verificar que los comandos CLI siguen funcionando tras el reinicio
        rc = cli_main(["--url", server.url, "study", study_id])
        assert rc == 0

        rc = cli_main(["--url", server.url, "current-block", study_id])
        assert rc == 0

        rc = cli_main(["--url", server.url, "messages", study_id])
        assert rc == 0
    finally:
        server.stop()
