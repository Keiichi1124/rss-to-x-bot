# tests/test_scheduler.py
import pytest
import os
import sys
from unittest.mock import patch, MagicMock, call

# Make sure bot modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot import scheduler, db

# Use the same test DB setup as test_rss_ingest
from tests.test_rss_ingest import setup_test_db, TEST_DB_PATH

@pytest.fixture
def mock_dependencies(mocker):
    """Mocks external dependencies like x_client and tweet_formatter."""
    mock_x_client_instance = MagicMock()
    mock_x_client_instance.post_tweet.return_value = {"data": {"id": "12345"}} # Simulate success
    mock_x_client = mocker.patch("bot.scheduler.x_client.XClient", return_value=mock_x_client_instance)

    mock_format_tweet = mocker.patch("bot.scheduler.tweet_formatter.format_tweet", return_value="Formatted tweet text")

    # Mock rss_ingest as well, although not strictly needed for post_new_articles test
    mock_rss_ingest = mocker.patch("bot.scheduler.rss_ingest.fetch_and_store_feed")

    return {
        "x_client": mock_x_client,
        "x_client_instance": mock_x_client_instance,
        "format_tweet": mock_format_tweet,
        "rss_ingest": mock_rss_ingest
    }

def test_post_new_articles_run_mode(setup_test_db, mock_dependencies):
    """Tests the post_new_articles function in run mode (not dry run)."""
    # 1. Add some unposted articles to the test DB
    db.add_article("guid1", "Title 1", "link1", "2024-05-01T10:00:00Z", "Content 1", "feed1")
    db.add_article("guid2", "Title 2", "link2", "2024-05-01T11:00:00Z", "Content 2", "feed1")
    db.add_article("guid3", "Title 3", "link3", "2024-05-01T12:00:00Z", "Content 3", "feed2")

    # Mark one as already posted
    db.mark_article_as_posted(2) # Mark article with id=2 (guid2) as posted

    # 2. Run the post_new_articles function (not dry run)
    scheduler.post_new_articles(dry_run=False)

    # 3. Assertions
    mock_format_tweet = mock_dependencies["format_tweet"]
    mock_post_tweet = mock_dependencies["x_client_instance"].post_tweet

    # Check format_tweet was called for the unposted articles (guid1, guid3)
    assert mock_format_tweet.call_count == 2
    mock_format_tweet.assert_has_calls([
        call("Title 1", "link1"),
        call("Title 3", "link3")
    ], any_order=True)

    # Check post_tweet was called for the unposted articles
    assert mock_post_tweet.call_count == 2
    mock_post_tweet.assert_has_calls([
        call("Formatted tweet text"), # Called twice with the mocked formatted text
        call("Formatted tweet text")
    ], any_order=True)

    # Check that the articles were marked as posted in the DB
    remaining_unposted = db.get_unposted_articles()
    assert len(remaining_unposted) == 0

def test_post_new_articles_dry_run_mode(setup_test_db, mock_dependencies):
    """Tests the post_new_articles function in dry run mode."""
    # 1. Add unposted articles
    db.add_article("guid10", "Title 10", "link10", "2024-05-02T10:00:00Z", "Content 10", "feed10")
    db.add_article("guid11", "Title 11", "link11", "2024-05-02T11:00:00Z", "Content 11", "feed11")

    # 2. Run the post_new_articles function (dry run)
    scheduler.post_new_articles(dry_run=True)

    # 3. Assertions
    mock_format_tweet = mock_dependencies["format_tweet"]
    mock_post_tweet = mock_dependencies["x_client_instance"].post_tweet

    # Check format_tweet was called
    assert mock_format_tweet.call_count == 2
    mock_format_tweet.assert_has_calls([
        call("Title 10", "link10"),
        call("Title 11", "link11")
    ], any_order=True)

    # Check post_tweet was NOT called
    mock_post_tweet.assert_not_called()

    # Dry runs should not mutate queue state.
    remaining_unposted = db.get_unposted_articles()
    assert len(remaining_unposted) == 2

def test_post_new_articles_no_articles(setup_test_db, mock_dependencies):
    """Tests the post_new_articles function when there are no unposted articles."""
    # 1. Ensure DB is empty or all articles are posted
    # setup_test_db already ensures a clean DB

    # 2. Run the post_new_articles function
    scheduler.post_new_articles(dry_run=False)

    # 3. Assertions
    mock_format_tweet = mock_dependencies["format_tweet"]
    mock_post_tweet = mock_dependencies["x_client_instance"].post_tweet

    # Check format_tweet and post_tweet were NOT called
    mock_format_tweet.assert_not_called()
    mock_post_tweet.assert_not_called()

# Note: Testing the actual APScheduler loop (`run_scheduled_loop`) is complex
# and often involves mocking time or using specific testing utilities for APScheduler.
# Given the constraints (loop mode won't run properly), focusing on testing the job functions
# (`fetch_rss_feeds`, `post_new_articles`) directly is more practical.
