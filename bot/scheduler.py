# bot/scheduler.py
import argparse
import logging
import os
import random
import time
import sys
import threading # Import threading

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Ensure bot modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot import db
from bot import rss_ingest
from bot import tweet_formatter
from bot import x_client
from bot import manual_queue
from bot.log_config import setup_logging # Import setup_logging
from bot.health_check import run_server as run_health_check_server # Import health check server runner

# --- Logging Setup ---
setup_logging() # Setup JSON logging
logger = logging.getLogger(__name__) # Get logger for this module

# --- Load Environment Variables ---
load_dotenv()

# --- Constants ---
# Example feed, could be made configurable later
DEFAULT_FEED_URLS = [os.getenv("RSS_FEED_URL", rss_ingest.DEFAULT_FEED_URL)]
MIN_INTERVAL_MINUTES = 2
MAX_INTERVAL_MINUTES = 5
HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", 8080))

# --- Core Job Functions ---

def fetch_rss_feeds():
    """Fetches all configured RSS feeds."""
    logger.info("Starting RSS feed fetch job.")
    for feed_url in DEFAULT_FEED_URLS:
        try:
            rss_ingest.fetch_and_store_feed(feed_url)
        except Exception as e:
            logger.error(f"Error fetching feed {feed_url}: {e}", exc_info=True)
    logger.info("Finished RSS feed fetch job.")

def post_new_articles(dry_run: bool = False):
    """Fetches unposted articles from DB and posts them to X."""
    logger.info(f"Starting post new articles job. Dry run: {dry_run}")
    try:
        unposted_articles = db.get_unposted_articles()
        if not unposted_articles:
            logger.info("No new articles to post.")
            return

        logger.info(f"Found {len(unposted_articles)} new articles to post.")
        client = x_client.XClient() # Initialize client inside job

        for article in unposted_articles:
            article_id, guid, title, link, published_date, content, feed_source = article
            logger.info(f"Processing article ID: {article_id}, GUID: {guid}, Title: {title}")

            try:
                tweet_text = tweet_formatter.format_tweet(title, link)
                logger.info(f"Formatted tweet: {tweet_text}")

                if dry_run:
                    logger.info(f"[DRY RUN] Would post tweet for article ID: {article_id}")
                    post_success = False
                else:
                    logger.info(f"Attempting to post tweet for article ID: {article_id}")
                    response = client.post_tweet(tweet_text)
                    # Basic check, might need refinement based on actual API response
                    if response and response.get("data", {}).get("id"):
                        logger.info(f"Successfully posted tweet for article ID: {article_id}. Tweet ID: {response['data']['id']}")
                        post_success = True
                    else:
                        logger.error(f"Failed to post tweet for article ID: {article_id}. Response: {response}")
                        post_success = False

                if post_success:
                    db.mark_article_as_posted(article_id)
                    logger.info(f"Marked article ID: {article_id} as posted in DB.")
                elif dry_run:
                    logger.info(f"[DRY RUN] Leaving article ID: {article_id} unposted in DB.")
                else:
                    logger.warning(f"Skipping DB update for article ID: {article_id} due to posting failure.")

                # Optional: Add a small delay between posts to avoid rate limits
                if not dry_run:
                    time.sleep(random.uniform(1, 3))

            except Exception as e:
                logger.error(f"Error processing article ID {article_id}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in post_new_articles job: {e}", exc_info=True)
    finally:
        logger.info("Finished post new articles job.")

# --- Scheduler Setup ---

def run_scheduled_loop(run_health_server: bool = True):
    """Runs the bot in a loop using APScheduler and optionally starts health server."""
    logger.info("Initializing scheduler for loop mode.")
    scheduler = BackgroundScheduler(timezone="UTC")

    # Add jobs with random intervals
    fetch_interval = random.randint(MIN_INTERVAL_MINUTES * 60, MAX_INTERVAL_MINUTES * 60)
    post_interval = random.randint(MIN_INTERVAL_MINUTES * 60, MAX_INTERVAL_MINUTES * 60)

    scheduler.add_job(fetch_rss_feeds, "interval", seconds=fetch_interval, id="fetch_rss")
    # Pass dry_run=False for the scheduled job
    scheduler.add_job(post_new_articles, "interval", seconds=post_interval, id="post_articles", kwargs={"dry_run": False})

    logger.info(f"Added fetch_rss job with interval ~{fetch_interval // 60} mins.")
    logger.info(f"Added post_articles job with interval ~{post_interval // 60} mins.")

    # Start health check server in a separate thread if requested
    health_thread = None
    if run_health_server:
        logger.info("Starting health check server in background thread.")
        health_thread = threading.Thread(target=run_health_check_server, kwargs={"port": HEALTH_CHECK_PORT}, daemon=True)
        health_thread.start()

    scheduler.start()
    logger.info("Scheduler started. Running indefinitely (press Ctrl+C to exit).")

    # Keep the script running
    try:
        while True:
            # Check if health thread is alive if it was started
            if health_thread and not health_thread.is_alive():
                logger.error("Health check server thread unexpectedly stopped.")
                # Optionally attempt to restart or just log and continue
                break # Exit loop if health server dies?
            time.sleep(60) # Check every minute
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler shut down.")
        # Note: Flask server in thread might not shut down gracefully here, but daemon=True helps.

# --- Main Execution Logic ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RSS-to-X Bot Scheduler")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # --- 'run' command ---
    parser_run = subparsers.add_parser("run", help="Fetch RSS and post new articles once.")
    parser_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the posting process without actually sending tweets."
    )

    # --- 'loop' command ---
    parser_loop = subparsers.add_parser("loop", help="Run the bot continuously using the scheduler (may be limited).")
    parser_loop.add_argument(
        "--no-health-server",
        action="store_true",
        help="Disable the health check HTTP server when running in loop mode."
    )

    # --- 'add' command ---
    parser_add = subparsers.add_parser("add", help="Manually add a URL to the posting queue.")
    parser_add.add_argument(
        "url",
        type=str,
        help="The URL to fetch and add to the queue."
    )

    # --- 'health-server' command (standalone) ---
    parser_health = subparsers.add_parser("health-server", help="Run only the health check HTTP server.")

    args = parser.parse_args()

    logger.info(f"Executing command: {args.command}")

    # DB Initialization needed for most commands
    if args.command in ["run", "add", "loop"]:
        logger.info("Initializing database...")
        db._init_db()
        logger.info("Database initialized.")

    if args.command == "run":
        logger.info(f"Executing single run... Dry run: {args.dry_run}")
        fetch_rss_feeds() # Fetch first
        post_new_articles(dry_run=args.dry_run) # Then post
        logger.info("Single run finished.")
    elif args.command == "loop":
        logger.warning("Loop mode selected. Note: Background scheduling may be limited in this environment.")
        run_health_server_flag = not args.no_health_server
        run_scheduled_loop(run_health_server=run_health_server_flag)
    elif args.command == "add":
        logger.info(f"Adding URL: {args.url}")
        success = manual_queue.add_url_to_queue(args.url)
        if success:
            logger.info("URL added successfully.")
        else:
            logger.error("Failed to add URL.")
            sys.exit(1) # Exit with error code if adding failed
    elif args.command == "health-server":
        logger.info("Starting standalone health check server.")
        run_health_check_server(port=HEALTH_CHECK_PORT)
