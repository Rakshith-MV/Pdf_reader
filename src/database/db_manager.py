import os
import sqlite3
import json
from typing import Dict, List, Optional, Any

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

class DatabaseManager:
    """Handles local persistence using SQLite for reading state, bookmarks, notes, highlights, and study lists."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            config_dir = os.path.expanduser("~/.readera_desktop")
            os.makedirs(config_dir, exist_ok=True)
            db_path = os.path.join(config_dir, "reader.db")
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn = self._get_connection()
        try:
            conn.executescript(schema_sql)
        finally:
            conn.close()

    # --- Document Operations ---

    def get_or_create_document(
        self, file_hash: str, file_path: str, title: str, total_pages: int = 0
    ) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    """
                    UPDATE documents
                    SET file_path = ?, title = ?, total_pages = ?, last_opened = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (file_path, title, total_pages, row["id"]),
                )
                conn.commit()
                cur.execute("SELECT * FROM documents WHERE id = ?", (row["id"],))
                return dict(cur.fetchone())
            else:
                cur.execute(
                    """
                    INSERT INTO documents (file_hash, file_path, title, total_pages)
                    VALUES (?, ?, ?, ?)
                    """,
                    (file_hash, file_path, title, total_pages),
                )
                conn.commit()
                doc_id = cur.lastrowid
                cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
                return dict(cur.fetchone())
        finally:
            conn.close()

    def get_document_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_reading_position(
        self, doc_id: int, current_page: int, zoom_level: Optional[float] = None
    ):
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if zoom_level is not None:
                cur.execute(
                    """
                    UPDATE documents
                    SET current_page = ?, zoom_level = ?, last_opened = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (current_page, zoom_level, doc_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE documents
                    SET current_page = ?, last_opened = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (current_page, doc_id),
                )
            conn.commit()
        finally:
            conn.close()

    def get_recent_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM documents ORDER BY last_opened DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def delete_document(self, doc_id: int):
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Bookmark Operations ---

    def add_bookmark(self, doc_id: int, page_number: int, label: str) -> int:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO bookmarks (document_id, page_number, label)
                VALUES (?, ?, ?)
                """,
                (doc_id, page_number, label),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_bookmarks(self, doc_id: int) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM bookmarks WHERE document_id = ? ORDER BY page_number ASC",
                (doc_id,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def delete_bookmark(self, bookmark_id: int):
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Note Operations ---

    def add_note(
        self,
        doc_id: int,
        page_number: int,
        note_text: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> int:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO notes (document_id, page_number, x, y, width, height, note_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, page_number, x, y, width, height, note_text),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_notes(self, doc_id: int) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM notes WHERE document_id = ? ORDER BY page_number ASC, created_at ASC",
                (doc_id,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def update_note(self, note_id: int, note_text: str):
        conn = self._get_connection()
        try:
            conn.execute(
                """
                UPDATE notes
                SET note_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (note_text, note_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_note(self, note_id: int):
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Highlights & Underlines Operations ---

    def add_highlight(
        self,
        doc_id: int,
        page_number: int,
        rects: List[List[float]],
        color: str = "#FFF59D",
        style: str = "highlight",
        selected_text: str = "",
        comment_text: str = "",
    ) -> int:
        rects_json = json.dumps(rects)
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO highlights (document_id, page_number, rects_json, color, style, selected_text, comment_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, page_number, rects_json, color, style, selected_text, comment_text),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_highlights(self, doc_id: int, page_number: Optional[int] = None) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if page_number is not None:
                cur.execute(
                    "SELECT * FROM highlights WHERE document_id = ? AND page_number = ? ORDER BY created_at ASC",
                    (doc_id, page_number),
                )
            else:
                cur.execute(
                    "SELECT * FROM highlights WHERE document_id = ? ORDER BY page_number ASC, created_at ASC",
                    (doc_id,),
                )
            rows = [dict(row) for row in cur.fetchall()]
            for r in rows:
                try:
                    r["rects"] = json.loads(r["rects_json"])
                except Exception:
                    r["rects"] = []
            return rows
        finally:
            conn.close()

    def update_highlight_comment(self, highlight_id: int, comment_text: str):
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE highlights SET comment_text = ? WHERE id = ?",
                (comment_text, highlight_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_highlight(self, highlight_id: int):
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Study Lists Operations ---

    def create_study_list(self, name: str, description: str = "") -> int:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO study_lists (name, description) VALUES (?, ?)",
                (name, description),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_study_lists(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM study_lists ORDER BY name ASC")
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def add_document_to_study_list(self, study_list_id: int, doc_id: int):
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO study_list_items (study_list_id, document_id) VALUES (?, ?)",
                (study_list_id, doc_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_study_list_documents(self, study_list_id: int) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT d.* FROM documents d
                JOIN study_list_items sli ON d.id = sli.document_id
                WHERE sli.study_list_id = ?
                ORDER BY d.last_opened DESC
                """,
                (study_list_id,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_study_lists_for_document(self, doc_id: int) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT sl.* FROM study_lists sl
                JOIN study_list_items sli ON sl.id = sli.study_list_id
                WHERE sli.document_id = ?
                ORDER BY sl.name ASC
                """,
                (doc_id,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def remove_document_from_study_list(self, study_list_id: int, doc_id: int):
        conn = self._get_connection()
        try:
            conn.execute(
                "DELETE FROM study_list_items WHERE study_list_id = ? AND document_id = ?",
                (study_list_id, doc_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_study_list(self, study_list_id: int):
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM study_lists WHERE id = ?", (study_list_id,))
            conn.commit()
        finally:
            conn.close()

    def update_study_list_notes(self, study_list_id: int, notes_markdown: str):
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE study_lists SET notes_markdown = ? WHERE id = ?",
                (notes_markdown, study_list_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_study_list_notes(self, study_list_id: int) -> str:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT notes_markdown FROM study_lists WHERE id = ?", (study_list_id,))
            row = cur.fetchone()
            return row["notes_markdown"] if row and row["notes_markdown"] else ""
        finally:
            conn.close()

    # --- Focus Session Operations ---

    def log_focus_session(self, study_list_id: Optional[int], duration_minutes: int) -> int:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO focus_sessions (study_list_id, duration_minutes)
                VALUES (?, ?)
                """,
                (study_list_id, duration_minutes),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_focus_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT SUM(duration_minutes) as total FROM focus_sessions
                WHERE date(completed_at, 'localtime') = date('now', 'localtime')
                """
            )
            row_today = cur.fetchone()
            today_mins = row_today["total"] if row_today and row_today["total"] else 0

            cur.execute(
                """
                SELECT SUM(duration_minutes) as total FROM focus_sessions
                WHERE date(completed_at, 'localtime') = date('now', '-1 day', 'localtime')
                """
            )
            row_yest = cur.fetchone()
            yest_mins = row_yest["total"] if row_yest and row_yest["total"] else 0

            cur.execute(
                """
                SELECT study_list_id, SUM(duration_minutes) as total
                FROM focus_sessions
                WHERE study_list_id IS NOT NULL
                GROUP BY study_list_id
                """
            )
            sl_mins = {row["study_list_id"]: row["total"] for row in cur.fetchall()}

            cur.execute(
                """
                SELECT DISTINCT date(completed_at, 'localtime') as day
                FROM focus_sessions
                ORDER BY day DESC
                """
            )
            days = [row["day"] for row in cur.fetchall()]
            streak = 0
            if days:
                import datetime
                today_str = datetime.date.today().isoformat()
                yest_str = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
                check_date = datetime.date.today()
                if days[0] not in (today_str, yest_str):
                    streak = 0
                else:
                    if days[0] == yest_str:
                        check_date = datetime.date.today() - datetime.timedelta(days=1)
                    for d in days:
                        if d == check_date.isoformat():
                            streak += 1
                            check_date -= datetime.timedelta(days=1)
                        else:
                            break

            return {
                "today_minutes": today_mins,
                "yesterday_minutes": yest_mins,
                "streak_days": streak,
                "study_list_minutes": sl_mins,
            }
        finally:
            conn.close()
