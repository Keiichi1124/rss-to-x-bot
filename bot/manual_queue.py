# bot/manual_queue.py
import logging
import requests
import os # Import os module
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

from . import db

logger = logging.getLogger(__name__)

# Basic headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_url_content(url: str) -> tuple[str | None, str | None]:
    """Fetches the content of a URL and extracts the title."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # Check content type
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type:
            logger.warning(f"URL {url} is not HTML content (type: {content_type}). Skipping title extraction.")
            # Use URL path as fallback title
            parsed_url = urlparse(url)
            fallback_title = os.path.basename(parsed_url.path) or parsed_url.netloc
            return fallback_title, None # Return fallback title, no content

        soup = BeautifulSoup(response.content, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.string.strip() if title_tag else None

        # Fallback title if <title> is missing or empty
        if not title:
            h1_tag = soup.find("h1")
            title = h1_tag.string.strip() if h1_tag else None
        if not title:
            # Use URL path as fallback title
            parsed_url = urlparse(url)
            title = os.path.basename(parsed_url.path) or parsed_url.netloc
            logger.warning(f"Could not find title tag for {url}. Using fallback: {title}")

        # Extract main content (simple approach: join paragraphs)
        # This is very basic and might need significant improvement based on site structure
        paragraphs = soup.find_all("p")
        content = "\n".join(p.get_text().strip() for p in paragraphs if p.get_text().strip())

        logger.info(f"Fetched URL: {url}, Title: {title}")
        return title, content if content else None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Error parsing content from URL {url}: {e}")
        # Use URL path as fallback title in case of parsing error after successful fetch
        parsed_url = urlparse(url)
        fallback_title = os.path.basename(parsed_url.path) or parsed_url.netloc
        return fallback_title, None

def add_url_to_queue(url: str):
    """Fetches URL, extracts title, and adds it to the database queue."""
    logger.info(f"Attempting to add URL to queue: {url}")
    title, content = fetch_url_content(url)

    if title:
        # Use URL as GUID for manually added items
        guid = url
        was_added = db.add_article(
            guid=guid,
            title=title,
            link=url,
            published_date=None, # No published date for manual entries
            content=content,
            feed_source="manual"
        )
        if was_added:
            logger.info(f"Successfully added URL to queue: {url} with title: {title}")
            return True
        else:
            logger.warning(f"URL already exists in queue or DB error occurred: {url}")
            return False # Indicate already exists or error
    else:
        logger.error(f"Failed to fetch or extract title for URL: {url}. Not added to queue.")
        return False

# Example usage (can be integrated into a CLI later)
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        logging.basicConfig(level=logging.INFO)
        print(f"Adding URL: {test_url}")
        # Need to initialize DB for standalone run
        db._init_db()
        add_url_to_queue(test_url)
    else:
        print("Usage: python bot/manual_queue.py <URL>")
