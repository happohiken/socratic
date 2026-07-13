from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import httpx


class SocraticClient:
    """Cliente HTTP sync para la API pública de Socratic.

    Thin wrapper sobre httpx. No mantiene estado: cada llamada es
    independiente y el servidor es la fuente de verdad.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8885", timeout: float = 30.0):
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SocraticClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @property
    def base_url(self) -> str:
        return str(self._client.base_url)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            raise SocraticAPIError(resp.status_code, detail)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # --- Documents ---

    def upload_document(self, pdf_path: Path) -> dict:
        with open(pdf_path, "rb") as f:
            return self._request(
                "POST",
                "/documents",
                files={"file": (pdf_path.name, f, "application/pdf")},
            )

    def list_documents(self) -> list[dict]:
        return self._request("GET", "/documents")

    def get_document(self, document_id: str) -> dict:
        return self._request("GET", f"/documents/{document_id}")

    # --- Studies ---

    def create_study(self, document_id: str) -> dict:
        return self._request("POST", "/studies", json={"document_id": document_id})

    def list_studies(self) -> list[dict]:
        return self._request("GET", "/studies")

    def get_study(self, study_id: str) -> dict:
        return self._request("GET", f"/studies/{study_id}")

    def get_current_block(self, study_id: str) -> dict:
        return self._request("GET", f"/studies/{study_id}/current-block")

    def complete_block(self, study_id: str, block_id: str) -> dict:
        return self._request(
            "POST", f"/studies/{study_id}/blocks/{block_id}/complete"
        )

    # --- Messages ---

    def list_messages(self, study_id: str) -> list[dict]:
        return self._request("GET", f"/studies/{study_id}/messages")

    def create_message(
        self,
        study_id: str,
        content: str,
        role: str = "user",
        content_block_id: Optional[str] = None,
    ) -> dict:
        payload: dict = {"content": content, "role": role}
        if content_block_id is not None:
            payload["content_block_id"] = content_block_id
        return self._request("POST", f"/studies/{study_id}/messages", json=payload)

    # --- Ask ---

    def ask(self, study_id: str, question: str) -> dict:
        return self._request(
            "POST", f"/studies/{study_id}/ask", json={"question": question}
        )


class SocraticAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")
