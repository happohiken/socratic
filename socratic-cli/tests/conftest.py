"""Añade el path del servidor al sys.path para que los tests de la CLI
puedan importar el paquete `socratic` del servidor.

Solo modifica sys.path cuando se importe el módulo, no al nivel del fixture.
"""
from __future__ import annotations

import sys
from pathlib import Path

if "socratic" not in sys.modules:
    SERVER_SRC = Path(__file__).resolve().parent.parent.parent / "socratic-server" / "src"
    p = str(SERVER_SRC)
    if p not in sys.path:
        sys.path.insert(0, p)
