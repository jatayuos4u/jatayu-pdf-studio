"""Store local page bookmarks separately from the PDF."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3


class Bookmarks:
    def __init__(self, database=None):
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        self.database = database or base / "jatayu-pdf-studio" / "bookmarks.sqlite3"

    @contextmanager
    def connection(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database)
        try:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS bookmarks (
                    document TEXT NOT NULL, page INTEGER NOT NULL,
                    PRIMARY KEY (document, page)
                )""")
                db.execute("""CREATE TABLE IF NOT EXISTS spots (
                    id INTEGER PRIMARY KEY, document TEXT NOT NULL, page INTEGER NOT NULL,
                    x REAL NOT NULL, y REAL NOT NULL, label TEXT NOT NULL
                )""")
                yield db
        finally:
            db.close()

    def pages(self, document):
        with self.connection() as db:
            return [row[0] for row in db.execute(
                "SELECT page FROM bookmarks WHERE document = ? ORDER BY page",
                (str(document),),
            )]

    def set(self, document, page, saved):
        with self.connection() as db:
            if saved:
                db.execute("INSERT OR IGNORE INTO bookmarks VALUES (?, ?)", (str(document), page))
            else:
                db.execute("DELETE FROM bookmarks WHERE document = ? AND page = ?",
                           (str(document), page))

    def spots(self, document):
        with self.connection() as db:
            return db.execute(
                "SELECT id, page, x, y, label FROM spots WHERE document = ? ORDER BY page, y, x",
                (str(document),),
            ).fetchall()

    def add_spot(self, document, page, x, y, label):
        with self.connection() as db:
            db.execute("INSERT INTO spots (document, page, x, y, label) VALUES (?, ?, ?, ?, ?)",
                       (str(document), page, x, y, label))

    def remove_spot(self, document, spot_id):
        with self.connection() as db:
            db.execute("DELETE FROM spots WHERE document = ? AND id = ?", (str(document), spot_id))
