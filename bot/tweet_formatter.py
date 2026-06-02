# bot/tweet_formatter.py
import os
import logging
from bitlyshortener import Shortener
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

BITLY_ACCESS_TOKEN = os.getenv("BITLY_ACCESS_TOKEN")
DEFAULT_HASHTAG = os.getenv("DEFAULT_HASHTAG", "#NewsDigest")
MAX_TWEET_LENGTH = 280 # Standard Twitter limit

def shorten_url(long_url: str) -> str:
    """Shortens a URL using Bitly."""
    if not BITLY_ACCESS_TOKEN:
        logger.warning("BITLY_ACCESS_TOKEN not set. Returning original URL.")
        return long_url

    try:
        tokens_pool = [BITLY_ACCESS_TOKEN]
        shortener = Shortener(tokens=tokens_pool, max_cache_size=128)
        short_urls = shortener.shorten_urls([long_url])
        if short_urls and short_urls[0]:
            logger.info(f"Shortened {long_url} to {short_urls[0]}")
            return short_urls[0]
        else:
            logger.error(f"Failed to shorten URL: {long_url}")
            return long_url
    except Exception as e:
        logger.error(f"Error shortening URL {long_url}: {e}")
        return long_url

def format_tweet(title: str, link: str, hashtag: str = DEFAULT_HASHTAG) -> str:
    """Formats the tweet content with title, shortened URL, and hashtag."""
    short_link = shorten_url(link)

    # Calculate available length for title
    # Format: "[Title] [URL] [Hashtag]"
    # Spaces between elements: 2
    base_length = len(short_link) + len(hashtag) + 2
    available_title_length = MAX_TWEET_LENGTH - base_length

    if available_title_length <= 0:
        logger.error(f"URL and hashtag alone exceed max tweet length. Link: {short_link}, Hashtag: {hashtag}")
        # Return just the link and hashtag if title doesn't fit at all
        return f"{short_link} {hashtag}"

    truncated_title = title
    if len(title) > available_title_length:
        truncated_title = title[:available_title_length - 1] + "…" # Use ellipsis if truncated

    tweet_text = f"{truncated_title} {short_link} {hashtag}"

    # Final check, although unlikely to fail if calculations are correct
    if len(tweet_text) > MAX_TWEET_LENGTH:
        logger.warning(f"Formatted tweet exceeds max length even after truncation. Text: {tweet_text}")
        # Fallback: Just title and link, potentially truncated further
        alt_available_title_length = MAX_TWEET_LENGTH - (len(short_link) + 1)
        if alt_available_title_length <= 0:
             return short_link # Only link if nothing else fits
        alt_truncated_title = title[:alt_available_title_length -1] + "…" if len(title) > alt_available_title_length else title
        return f"{alt_truncated_title} {short_link}"

    return tweet_text

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_title = "This is a very long example title for an article that needs to be tweeted, hopefully it gets truncated correctly."
    test_link = "https://www.example.com/this-is-a-long-article-link"
    formatted = format_tweet(test_title, test_link)
    print(f"Formatted Tweet:\n{formatted}\nLength: {len(formatted)}")

    test_title_short = "Short Title"
    formatted_short = format_tweet(test_title_short, test_link)
    print(f"Formatted Tweet (Short Title):\n{formatted_short}\nLength: {len(formatted_short)}")
