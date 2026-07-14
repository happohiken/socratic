from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from socratic.document_processing.extractor import parse_pdf
from socratic.document_processing.formatters import format_json, format_text


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def cmd_inspect_pdf(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        _err(f"No existe el archivo: {pdf_path}")
        return 1

    page_range: tuple[int, int] | None = None
    if args.pages:
        try:
            parts = args.pages.split("-")
            if len(parts) == 2:
                page_range = (int(parts[0]), int(parts[1]))
            elif len(parts) == 1:
                p = int(parts[0])
                page_range = (p, p)
            else:
                _err(f"Formato de rango inválido: {args.pages}. Usa N-M o N.")
                return 1
        except ValueError:
            _err(f"Números inválidos en el rango: {args.pages}")
            return 1

    try:
        doc = parse_pdf(pdf_path, page_range)
    except Exception as e:
        _err(f"Error al procesar {pdf_path}: {e}")
        return 1

    if args.format == "json":
        output = format_json(doc)
    else:
        output = format_text(doc)

    if args.output:
        try:
            out_path = Path(args.output)
            out_path.write_text(output, encoding="utf-8")
        except OSError as e:
            _err(f"No se pudo escribir en {args.output}: {e}")
            return 1
    else:
        print(output)

    return 0


def add_inspect_pdf_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "inspect-pdf",
        help="Inspeccionar la descomposición documental de un PDF",
    )
    p.add_argument("pdf", help="Ruta al archivo PDF")
    p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Formato de salida (default: text)",
    )
    p.add_argument(
        "--pages",
        default=None,
        help="Rango de páginas a inspeccionar (ej: 1-5)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Escribir salida en archivo en lugar de stdout",
    )
    p.set_defaults(func=cmd_inspect_pdf)
