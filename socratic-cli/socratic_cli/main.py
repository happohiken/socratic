from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from socratic_cli.client import SocraticAPIError, SocraticClient

DEFAULT_URL = "http://127.0.0.1:8885"


def _client(args: argparse.Namespace) -> SocraticClient:
    base_url = getattr(args, "url", None) or os.environ.get("SOCRATIC_URL", DEFAULT_URL)
    return SocraticClient(base_url=base_url)


def _print_kv(pairs: list[tuple[str, Any]]) -> None:
    width = max((len(k) for k, _ in pairs), default=0)
    for k, v in pairs:
        print(f"  {k.ljust(width)}  {v}")


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


# --- Documentos ---


def cmd_upload(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        _err(f"No existe el archivo: {pdf_path}")
        return 1
    with _client(args) as c:
        try:
            data = c.upload_document(pdf_path)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    doc = data["document"]
    _print_kv(
        [
            ("document_id", doc["id"]),
            ("filename", doc["filename"]),
            ("block_count", doc["block_count"]),
            ("page_count", doc["page_count"]),
        ]
    )
    return 0


def cmd_documents(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            docs = c.list_documents()
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    if not docs:
        print("No hay documentos.")
        return 0
    for d in docs:
        print(f"{d['id']}  {d['filename']}  ({d['block_count']} bloques)")
    return 0


def cmd_document(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            data = c.get_document(args.document_id)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    _print_kv(
        [
            ("id", data["id"]),
            ("filename", data["filename"]),
            ("page_count", data["page_count"]),
            ("block_count", data["block_count"]),
        ]
    )
    print("  bloques:")
    for b in data.get("blocks", []):
        preview = b["text"].replace("\n", " ")[:60]
        print(f"    [{b['ordinal']}] {b['id']}  {preview}")
    return 0


# --- Estudios ---


def cmd_create_study(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            data = c.create_study(args.document_id)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    _print_kv(
        [
            ("study_id", data["id"]),
            ("document_id", data["document_id"]),
            ("current_block_id", data["current_block_id"]),
            ("last_completed_block_id", data["last_completed_block_id"]),
        ]
    )
    return 0


def cmd_studies(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            studies = c.list_studies()
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    if not studies:
        print("No hay estudios.")
        return 0
    for s in studies:
        print(f"{s['id']}  doc={s['document_id']}  current={s['current_block_id']}")
    return 0


def cmd_study(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            data = c.get_study(args.study_id)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    _print_kv(
        [
            ("id", data["id"]),
            ("document_id", data["document_id"]),
            ("current_block_id", data["current_block_id"]),
            ("last_completed_block_id", data["last_completed_block_id"]),
            ("updated_at", data["updated_at"]),
        ]
    )
    return 0


def cmd_current_block(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            data = c.get_current_block(args.study_id)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    _print_kv(
        [
            ("block_id", data["id"]),
            ("ordinal", data["ordinal"]),
            ("page", data["page_number"]),
            ("type", data["block_type"]),
        ]
    )
    print()
    print(data["text"])
    return 0


def cmd_complete_block(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            data = c.complete_block(args.study_id, args.block_id)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    _print_kv(
        [
            ("study_id", data["id"]),
            ("last_completed_block_id", data["last_completed_block_id"]),
            ("current_block_id", data["current_block_id"]),
        ]
    )
    return 0


# --- Mensajes ---


def cmd_messages(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            messages = c.list_messages(args.study_id)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    if not messages:
        print("No hay mensajes.")
        return 0
    for m in messages:
        print(f"[{m['role']}] {m['content']}  ({m['created_at']})")
    return 0


def cmd_message(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            data = c.create_message(
                args.study_id,
                args.content,
                role=args.role,
                content_block_id=args.block_id,
            )
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    _print_kv(
        [
            ("message_id", data["id"]),
            ("role", data["role"]),
            ("content", data["content"]),
        ]
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="socratic",
        description="Cliente CLI de Socratic. Consume la API pública del servidor.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help=f"URL base del servidor (default: env SOCRATIC_URL o {DEFAULT_URL})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # upload
    p = sub.add_parser("upload", help="Subir un PDF al servidor")
    p.add_argument("pdf", help="Ruta al archivo PDF")
    p.set_defaults(func=cmd_upload)

    # documents
    p = sub.add_parser("documents", help="Listar documentos")
    p.set_defaults(func=cmd_documents)

    # document
    p = sub.add_parser("document", help="Detalle de un documento y sus bloques")
    p.add_argument("document_id")
    p.set_defaults(func=cmd_document)

    # create-study
    p = sub.add_parser("create-study", help="Crear un estudio para un documento")
    p.add_argument("document_id")
    p.set_defaults(func=cmd_create_study)

    # studies
    p = sub.add_parser("studies", help="Listar estudios")
    p.set_defaults(func=cmd_studies)

    # study
    p = sub.add_parser("study", help="Consultar el estado de un estudio")
    p.add_argument("study_id")
    p.set_defaults(func=cmd_study)

    # current-block
    p = sub.add_parser("current-block", help="Obtener el bloque actual de lectura")
    p.add_argument("study_id")
    p.set_defaults(func=cmd_current_block)

    # complete-block
    p = sub.add_parser("complete-block", help="Marcar un bloque como completado")
    p.add_argument("study_id")
    p.add_argument("block_id")
    p.set_defaults(func=cmd_complete_block)

    # messages
    p = sub.add_parser("messages", help="Listar mensajes de un estudio")
    p.add_argument("study_id")
    p.set_defaults(func=cmd_messages)

    # message
    p = sub.add_parser("message", help="Crear un mensaje en un estudio")
    p.add_argument("study_id")
    p.add_argument("content")
    p.add_argument("--role", default="user", help="user | assistant (default: user)")
    p.add_argument("--block-id", default=None, help="Bloque asociado a la pregunta")
    p.set_defaults(func=cmd_message)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
