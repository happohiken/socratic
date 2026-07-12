from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from socratic.domain.models import ContentBlock, Document, Message, Study


@dataclass
class DB:
    conn: sqlite3.Connection
    path: Path

    def close(self) -> None:
        self.conn.close()


def init_db(path: Path) -> DB:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    return DB(conn=conn, path=path)


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id              TEXT PRIMARY KEY,
            filename        TEXT NOT NULL,
            page_count      INTEGER NOT NULL DEFAULT 0,
            block_count     INTEGER NOT NULL DEFAULT 0,
            format          TEXT NOT NULL DEFAULT 'pdf',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS content_blocks (
            id              TEXT PRIMARY KEY,
            document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            ordinal         INTEGER NOT NULL,
            text            TEXT NOT NULL,
            page_number     INTEGER NOT NULL DEFAULT 0,
            block_type      TEXT NOT NULL DEFAULT 'paragraph',
            metadata        TEXT NOT NULL DEFAULT '{}',
            UNIQUE(document_id, ordinal)
        );

        CREATE TABLE IF NOT EXISTS studies (
            id                  TEXT PRIMARY KEY,
            document_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            current_block_id    TEXT,
            last_completed_block_id TEXT,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              TEXT PRIMARY KEY,
            study_id        TEXT NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
            content_block_id TEXT,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL
        );
    """)


def _row_to_document(row: sqlite3.Row) -> Document:
    from datetime import datetime, timezone

    return Document(
        id=row["id"],
        filename=row["filename"],
        page_count=row["page_count"],
        block_count=row["block_count"],
        format=row["format"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_block(row: sqlite3.Row) -> ContentBlock:
    import json
    return ContentBlock(
        id=row["id"],
        document_id=row["document_id"],
        ordinal=row["ordinal"],
        text=row["text"],
        page_number=row["page_number"],
        block_type=row["block_type"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )


def save_document(conn: sqlite3.Connection, doc: Document) -> None:
    conn.execute(
        """INSERT INTO documents
           (id, filename, page_count, block_count, format, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            doc.id,
            doc.filename,
            doc.page_count,
            doc.block_count,
            doc.format,
            doc.created_at.isoformat(),
            doc.updated_at.isoformat(),
        ),
    )


def update_document(conn: sqlite3.Connection, doc: Document) -> None:
    conn.execute(
        """UPDATE documents
           SET filename=?, page_count=?, block_count=?, format=?, updated_at=?
           WHERE id=?""",
        (
            doc.filename,
            doc.page_count,
            doc.block_count,
            doc.format,
            doc.updated_at.isoformat(),
            doc.id,
        ),
    )


def get_document(conn: sqlite3.Connection, doc_id: str) -> Optional[Document]:
    cur = conn.execute(
        "SELECT * FROM documents WHERE id=?", (doc_id,)
    )
    row = cur.fetchone()
    return _row_to_document(row) if row else None


def list_documents(conn: sqlite3.Connection) -> List[Document]:
    cur = conn.execute(
        "SELECT * FROM documents ORDER BY created_at DESC"
    )
    return [_row_to_document(r) for r in cur.fetchall()]


def save_content_blocks(
    conn: sqlite3.Connection,
    document_id: str,
    blocks: List[ContentBlock],
) -> None:
    cur = conn.cursor()
    cur.executemany(
        """INSERT INTO content_blocks
           (id, document_id, ordinal, text, page_number, block_type, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                b.id,
                document_id,
                b.ordinal,
                b.text,
                b.page_number,
                b.block_type,
                __import__("json").dumps(b.metadata),
            )
            for b in blocks
        ],
    )
    conn.execute(
        "UPDATE documents SET block_count=? WHERE id=?",
        (len(blocks), document_id),
    )


def get_content_blocks(
    conn: sqlite3.Connection,
    document_id: str,
) -> List[ContentBlock]:
    cur = conn.execute(
        "SELECT * FROM content_blocks WHERE document_id=? ORDER BY ordinal",
        (document_id,),
    )
    return [_row_to_block(r) for r in cur.fetchall()]


def get_content_block(
    conn: sqlite3.Connection,
    block_id: str,
) -> Optional[ContentBlock]:
    cur = conn.execute(
        "SELECT * FROM content_blocks WHERE id=?", (block_id,)
    )
    row = cur.fetchone()
    return _row_to_block(row) if row else None


def _row_to_study(row: sqlite3.Row) -> Study:
    from datetime import datetime, timezone

    return Study(
        id=row["id"],
        document_id=row["document_id"],
        current_block_id=row["current_block_id"],
        last_completed_block_id=row["last_completed_block_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_message(row: sqlite3.Row) -> Message:
    from datetime import datetime, timezone

    return Message(
        id=row["id"],
        study_id=row["study_id"],
        content_block_id=row["content_block_id"],
        role=row["role"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def save_study(conn: sqlite3.Connection, study: Study) -> None:
    conn.execute(
        """INSERT INTO studies
           (id, document_id, current_block_id, last_completed_block_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            study.id,
            study.document_id,
            study.current_block_id,
            study.last_completed_block_id,
            study.created_at.isoformat(),
            study.updated_at.isoformat(),
        ),
    )


def update_study(conn: sqlite3.Connection, study: Study) -> None:
    conn.execute(
        """UPDATE studies
           SET document_id=?, current_block_id=?, last_completed_block_id=?, updated_at=?
           WHERE id=?""",
        (
            study.document_id,
            study.current_block_id,
            study.last_completed_block_id,
            study.updated_at.isoformat(),
            study.id,
        ),
    )


def get_study(conn: sqlite3.Connection, study_id: str) -> Optional[Study]:
    cur = conn.execute(
        "SELECT * FROM studies WHERE id=?", (study_id,)
    )
    row = cur.fetchone()
    return _row_to_study(row) if row else None


def list_studies(conn: sqlite3.Connection) -> List[Study]:
    cur = conn.execute(
        "SELECT * FROM studies ORDER BY created_at DESC"
    )
    return [_row_to_study(r) for r in cur.fetchall()]


def save_message(conn: sqlite3.Connection, message: Message) -> None:
    conn.execute(
        """INSERT INTO messages
           (id, study_id, content_block_id, role, content, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            message.id,
            message.study_id,
            message.content_block_id,
            message.role,
            message.content,
            message.created_at.isoformat(),
        ),
    )


def get_messages_for_study(
    conn: sqlite3.Connection,
    study_id: str,
) -> List[Message]:
    cur = conn.execute(
        "SELECT * FROM messages WHERE study_id=? ORDER BY created_at ASC",
        (study_id,),
    )
    return [_row_to_message(r) for r in cur.fetchall()]
