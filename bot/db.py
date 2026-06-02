# bot/db.py
import sqlite3
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Database file path (relative to project root)
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH = os.path.join(DB_DIR, "bot.db")

def _init_db():
    """Initializes the SQLite database and creates the articles table if it doesn't exist."""
    try:
        # Ensure the data directory exists
        os.makedirs(DB_DIR, exist_ok=True)
        logger.info(f"Ensuring database directory exists: {DB_DIR}")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT UNIQUE NOT NULL, -- Unique identifier from the feed (or URL for manual)
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                published_date TEXT,      -- Store as ISO 8601 string (UTC)
                content TEXT,             -- Optional content snippet
                feed_source TEXT,         -- Origin feed URL or "manual"
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- When it was added to DB
                posted_at TIMESTAMP NULL  -- When it was successfully posted to X
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guid ON articles (guid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posted_at ON articles (posted_at)")
        conn.commit()
        conn.close()
        logger.info(f"Database initialized successfully at {DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
        raise
    except OSError as e:
        logger.error(f"Error creating database directory {DB_DIR}: {e}", exc_info=True)
        raise

def add_article(guid: str, title: str, link: str, published_date: str | None, content: str | None, feed_source: str) -> bool:
    """Adds a new article to the database if the GUID doesn't already exist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO articles (guid, title, link, published_date, content, feed_source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (guid, title, link, published_date, content, feed_source))
        conn.commit()
        conn.close()
        logger.info(f"Added article with GUID: {guid}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Article with GUID {guid} already exists. Skipping.")
        conn.close()
        return False
    except sqlite3.Error as e:
        logger.error(f"Error adding article with GUID {guid}: {e}", exc_info=True)
        if conn:
            conn.close()
        return False

def get_unposted_articles() -> list[tuple]:
    """Retrieves all articles that haven't been posted yet (posted_at is NULL)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, guid, title, link, published_date, content, feed_source
            FROM articles
            WHERE posted_at IS NULL
            ORDER BY added_at ASC
        """)
        articles = cursor.fetchall()
        conn.close()
        logger.debug(f"Retrieved {len(articles)} unposted articles.")
        return articles
    except sqlite3.Error as e:
        logger.error(f"Error retrieving unposted articles: {e}", exc_info=True)
        if conn:
            conn.close()
        return []

def mark_article_as_posted(article_id: int):
    """Updates the posted_at timestamp for a given article ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor.execute("""
            UPDATE articles
            SET posted_at = ?
            WHERE id = ?
        """, (now_utc, article_id))
        conn.commit()
        conn.close()
        logger.info(f"Marked article ID {article_id} as posted at {now_utc}.")
    except sqlite3.Error as e:
        logger.error(f"Error marking article ID {article_id} as posted: {e}", exc_info=True)
        if conn:
            conn.close()

# Example usage for direct execution (e.g., manual check)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initializing DB (if needed)...")
    _init_db()
    print("Retrieving unposted articles...")
    unposted = get_unposted_articles()
    if unposted:
        print(f"Found {len(unposted)} unposted articles:")
        for article in unposted:
            print(f"  - ID: {article[0]}, Title: {article[2]}")
    else:
        print("No unposted articles found.")
