from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from socratic_cli.client import SocraticAPIError, SocraticClient
from socratic_cli.inspect_pdf import add_inspect_pdf_parser

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


def cmd_delete_document(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            c.delete_document(args.document_id)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    print(f"Documento {args.document_id} eliminado.")
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


# --- Ask ---


def cmd_ask(args: argparse.Namespace) -> int:
    with _client(args) as c:
        try:
            data = c.ask(args.study_id, args.question)
        except SocraticAPIError as e:
            _err(str(e))
            return 1
    print()
    print(data["answer"])
    print()
    _print_kv(
        [
            ("message_id", data["message_id"]),
            ("study_id", data["study_id"]),
        ]
    )
    return 0


# --- Config ---


def _resolve_path(path_str: str) -> Path:
    return Path(path_str).expanduser()


def _load_opencode_config() -> dict:
    config_path = _resolve_path("~/.config/opencode/opencode.json")
    if not config_path.is_file():
        _err(f"No se encontró el archivo: {config_path}")
        sys.exit(1)
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as e:
        _err(f"No se pudo leer el archivo: {e}")
        sys.exit(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        _err(f"JSON inválido en {config_path}: {e}")
        sys.exit(1)


def _list_providers(config: dict) -> list[str]:
    providers = config.get("provider", {})
    if not providers:
        _err("No se encontraron proveedores configurados en opencode.json")
        sys.exit(1)
    return list(providers.keys())


def _list_models(provider_config: dict) -> list[str]:
    models = provider_config.get("models", {})
    if not models:
        _err(f"No se encontraron modelos en el proveedor")
        sys.exit(1)
    return list(models.keys())


def _resolve_api_key(provider_config: dict) -> str | None:
    options = provider_config.get("options", {})
    api_key = options.get("apiKey")
    if api_key:
        return api_key
    env_ref = options.get("api_key_env")
    if env_ref:
        return os.environ.get(env_ref)
    return None


def _resolve_base_url(provider_config: dict) -> str | None:
    options = provider_config.get("options", {})
    return options.get("baseURL") or options.get("base_url")


def _resolve_timeout(provider_config: dict) -> int | None:
    options = provider_config.get("options", {})
    timeout = options.get("timeout")
    if timeout is False or timeout == 0:
        return None
    if isinstance(timeout, (int, float)) and timeout > 0:
        return int(timeout)
    return None


def _select_interactively(prompt: str, options: list[str]) -> str:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}", file=sys.stderr)
    while True:
        try:
            choice = input(f"\n{prompt} [1-{len(options)}]: ")
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except (ValueError, EOFError):
            pass
        print("Opción no válida.", file=sys.stderr)


def _shell_escape(value: str) -> str:
    escaped = value.replace("'", "'\\''")
    return f"'{escaped}'"


def cmd_config_import_opencode(args: argparse.Namespace) -> int:
    config = _load_opencode_config()

    providers = _list_providers(config)

    if args.provider:
        if args.provider not in providers:
            _err(
                f"Proveedor '{args.provider}' no encontrado. "
                f"Proveedores disponibles: {', '.join(providers)}"
            )
            return 1
        provider_name = args.provider
    else:
        if len(providers) == 1:
            provider_name = providers[0]
        else:
            print("Proveedores configurados:", file=sys.stderr)
            provider_name = _select_interactively("Selecciona un proveedor", providers)

    provider_config = config["provider"][provider_name]

    available_models = _list_models(provider_config)

    if args.model:
        model_name = args.model
    else:
        if len(available_models) == 1:
            model_name = available_models[0]
        else:
            print(f"\nModelos disponibles en {provider_name}:", file=sys.stderr)
            model_name = _select_interactively("Selecciona un modelo", available_models)

    if model_name not in provider_config["models"]:
        _err(
            f"Modelo '{model_name}' no encontrado. "
            f"Modelos disponibles: {', '.join(available_models)}"
        )
        return 1

    model_config = provider_config["models"][model_name]

    base_url = _resolve_base_url(provider_config)
    if not base_url:
        _err(
            f"baseURL no encontrado para el proveedor '{provider_name}'. "
            "No se puede conectar sin una URL base."
        )
        return 1

    api_key = _resolve_api_key(provider_config)
    if not api_key:
        _err(
            f"API key no resolvable para el proveedor '{provider_name}'. "
            "Las variables de entorno exportadas no contendrán la API key."
        )

    timeout = _resolve_timeout(provider_config)
    if timeout is None:
        timeout = 120

    env_vars = {
        "SOCRATIC_LLM_PROVIDER": "openai-compatible",
        "SOCRATIC_LLM_BASE_URL": base_url,
        "SOCRATIC_LLM_MODEL": model_name,
        "SOCRATIC_LLM_API_KEY": api_key or "",
        "SOCRATIC_LLM_TIMEOUT_SECONDS": str(timeout),
    }

    if args.export_shell:
        for key, value in env_vars.items():
            if value:
                print(f"export {key}={_shell_escape(value)}")
            else:
                print(f"unset {key}")
        return 0

    if args.print_env:
        print(
            "ADVERTENCIA: esta salida puede contener secretos (API key). "
            "No la redirijas a un archivo en el repositorio.",
            file=sys.stderr,
        )
        for key, value in env_vars.items():
            print(f"{key}={value}")
        return 0

    _err("Debe especificar --export-shell o --print-env")
    return 1


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


    # delete
    p = sub.add_parser("delete", help="Eliminar un documento y todos sus asociados")
    p.add_argument("document_id")
    p.set_defaults(func=cmd_delete_document)
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

    # ask
    p = sub.add_parser("ask", help="Hacer una pregunta al LLM sobre el bloque actual")
    p.add_argument("study_id")
    p.add_argument("question", help="Pregunta sobre el bloque actual")
    p.set_defaults(func=cmd_ask)

    # inspect-pdf
    add_inspect_pdf_parser(sub)

    # config
    config_parser = sub.add_parser("config", help="Gestión de configuración")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)

    # config import-opencode
    p = config_sub.add_parser(
        "import-opencode",
        help="Importar configuración de OpenCode a variables de entorno",
    )
    p.add_argument(
        "--provider",
        default=None,
        help="Nombre del proveedor en opencode.json",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Nombre del modelo dentro del proveedor",
    )
    mode_group = p.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--export-shell",
        action="store_true",
        help="Exportar variables para sesión actual (compatible con sh/bash/zsh)",
    )
    mode_group.add_argument(
        "--print-env",
        action="store_true",
        help="Exportar variables para systemd (formato KEY=value)",
    )
    p.set_defaults(func=cmd_config_import_opencode)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "config_command", None):
        return cmd_config_import_opencode(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
