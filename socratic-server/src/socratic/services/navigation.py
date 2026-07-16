"""Servicio de navegación de lectura.

Centraliza la lógica de obtener/completar/retroceder bloque del estudio.
Lo usan tanto los endpoints REST (`api/studies.py`) como las tools del
orquestador, evitando duplicar lógica y garantizando que las tools no
toquen la persistencia directamente.
"""
from __future__ import annotations

from socratic.domain.models import ContentBlock, Study
from socratic.storage.database import (
    DB,
    get_content_block,
    get_content_blocks,
    update_study,
)


class NavigationError(Exception):
    """Error de navegación sobre el estudio (sin bloques, fuera de rango…)."""


class NavigationService:
    """Operaciones de navegación de lectura sobre un estudio.

    Persiste los cambios de estado del estudio en cada llamada. Las tools
    no persisten por su cuenta: delegan aquí.
    """

    def __init__(self, db: DB) -> None:
        self._db = db

    def get_current_block(self, study: Study) -> ContentBlock | None:
        """Devuelve el bloque actual o ``None`` si no hay."""
        if not study.current_block_id:
            return None
        return get_content_block(self._db.conn, study.current_block_id)

    def complete_block(
        self,
        study: Study,
        block_id: str,
    ) -> ContentBlock | None:
        """Marca ``block_id`` como completado y avanza al siguiente.

        Devuelve el nuevo bloque actual, o ``None`` si se alcanzó el final
        del documento. Lanza ``NavigationError`` si el bloque no pertenece
        al documento.
        """
        blocks = get_content_blocks(self._db.conn, study.document_id)
        block_ids = [b.id for b in blocks]
        if block_id not in block_ids:
            raise NavigationError(
                f"El bloque {block_id} no pertenece al documento"
            )
        current_index = block_ids.index(block_id)
        if current_index < len(block_ids) - 1:
            study.current_block_id = block_ids[current_index + 1]
        else:
            study.current_block_id = None
        study.last_completed_block_id = block_id
        study.touch()
        update_study(self._db.conn, study)
        self._db.conn.commit()

        if study.current_block_id is None:
            return None
        return get_content_block(self._db.conn, study.current_block_id)

    def complete_current_block(self, study: Study) -> ContentBlock | None:
        """Comodidad: completa el bloque actual del estudio.

        Lanza ``NavigationError`` si el estudio no tiene bloque actual.
        """
        if not study.current_block_id:
            raise NavigationError("El estudio no tiene bloque actual")
        return self.complete_block(study, study.current_block_id)

    def previous_block(self, study: Study) -> ContentBlock:
        """Retrocede al bloque anterior.

        Si el estudio está al final (``current_block_id`` es ``None``),
        vuelve al último bloque completado. Lanza ``NavigationError`` si
        no hay bloque al que retroceder.
        """
        blocks = get_content_blocks(self._db.conn, study.document_id)
        block_ids = [b.id for b in blocks]
        if not block_ids:
            raise NavigationError("El documento no tiene bloques")

        if study.current_block_id is None:
            if study.last_completed_block_id is None:
                raise NavigationError(
                    "El estudio no tiene bloques completados para retroceder"
                )
            study.current_block_id = study.last_completed_block_id
        else:
            current_index = block_ids.index(study.current_block_id)
            if current_index == 0:
                raise NavigationError("Ya estás en el primer bloque")
            study.current_block_id = block_ids[current_index - 1]

        study.touch()
        update_study(self._db.conn, study)
        self._db.conn.commit()
        return get_content_block(self._db.conn, study.current_block_id)
