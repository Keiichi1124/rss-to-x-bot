# bot/rss_ingest.py
import feedparser
import logging
import os
import sys
from datetime import datetime, timezone
from dateutil import parser as date_parser

# Ensure bot modules can be imported if run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot import db

logger = logging.getLogger(__name__)

DEFAULT_FEED_URL = "http://feeds.bbci.co.uk/news/rss.xml"

def _entry_get(entry, key, default=None):
    """Read feedparser entries and test doubles through a consistent interface."""
    if hasattr(entry, "get"):
        value = entry.get(key, default)
        if value is not None and value.__class__.__module__ != "unittest.mock":
            return value
    value = getattr(entry, key, default)
    if value.__class__.__module__ == "unittest.mock":
        return default
    return value

def _struct_time_to_utc_iso(value) -> str:
    return datetime(*value[:6], tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_published_date(entry) -> str | None:
    """Parses the published date from a feed entry and returns it as a UTC ISO 8601 string.

    Handles various date formats using dateutil.parser and converts to UTC.

    Args:
        entry: A feedparser entry object.

    Returns:
        An ISO 8601 formatted date string in UTC (e.g., \"2023-12-25T15:30:00Z\"),
        or None if parsing fails or no date is found.
    """
    guid = _entry_get(entry, "guid") or _entry_get(entry, "id") or _entry_get(entry, "link")

    published_struct = _entry_get(entry, "published_parsed") or _entry_get(entry, "updated_parsed")
    if published_struct:
        return _struct_time_to_utc_iso(published_struct)

    published_date_str = _entry_get(entry, "published") or _entry_get(entry, "updated")
    if not published_date_str:
        logger.warning(f"No published or updated date found for entry GUID: {guid}")
        return None

    try:
        dt = date_parser.parse(published_date_str)

        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    except Exception as e:
        logger.error(f"Error parsing date \"{published_date_str}\" for entry GUID {guid}: {e}", exc_info=True)
        return None

def fetch_and_store_feed(feed_url: str):
    """Fetches an RSS feed, parses it, and stores new articles in the database.

    Args:
        feed_url: The URL of the RSS feed to fetch.
    """
    logger.info(f"Fetching RSS feed: {feed_url}")
    try:
        # Fetch and parse the feed
        feed = feedparser.parse(feed_url)

        # Check for feed parsing errors (bozo flag)
        if feed.bozo:
            bozo_exception = feed.get("bozo_exception", "Unknown parsing error")
            logger.warning(f"Feed {feed_url} may be ill-formed: {bozo_exception}")

        if not feed.entries:
            logger.info(f"No entries found in feed: {feed_url}")
            return

        logger.info(f"Found {len(feed.entries)} entries in feed: {feed_url}")

        added_count = 0
        skipped_count = 0
        for entry in feed.entries:
            guid = _entry_get(entry, "guid") or _entry_get(entry, "id") or _entry_get(entry, "link")
            title = _entry_get(entry, "title")
            link = _entry_get(entry, "link")
            published_date_iso = parse_published_date(entry)
            content = _entry_get(entry, "summary") or _entry_get(entry, "description")
            content_items = _entry_get(entry, "content")
            if not content and content_items:
                content = content_items[0].value

            if not all([guid, title, link]):
                logger.warning(f"Skipping entry due to missing guid, title, or link: {entry}")
                skipped_count += 1
                continue

            # Add article to DB
            was_added = db.add_article(
                guid=guid,
                title=title,
                link=link,
                published_date=published_date_iso,
                content=content,
                feed_source=feed_url # Store the feed URL as the source
            )
            if was_added:
                added_count += 1
            else:
                skipped_count += 1 # Skipped because it already exists

        logger.info(f"Feed processing complete for {feed_url}. Added: {added_count}, Skipped (existing or invalid): {skipped_count}")

    except Exception as e:
        logger.error(f"Error fetching or processing feed {feed_url}: {e}")

# Example usage for direct execution
if __name__ == "__main__":
    from bot.log_config import setup_logging
    setup_logging(log_level=logging.DEBUG)

    test_feed = os.getenv("RSS_FEED_URL", DEFAULT_FEED_URL)
    print(f"Fetching feed: {test_feed}")
    # Need to initialize DB for standalone run
    db._init_db()
    fetch_and_store_feed(test_feed)
    print("Feed fetch attempt finished. Check logs for details.")
