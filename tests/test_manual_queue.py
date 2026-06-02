# tests/test_manual_queue.py
import pytest
import os
import sys
from unittest.mock import patch, MagicMock
import requests

# Make sure bot modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot import manual_queue, db

# Use the same test DB setup as test_rss_ingest
from tests.test_rss_ingest import setup_test_db, TEST_DB_PATH

@pytest.fixture
def mock_requests_get(mocker):
    """Mocks requests.get."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = b"<html><head><title>Test Title</title></head><body><p>Paragraph 1.</p><p>Paragraph 2.</p></body></html>"

    mock_get = mocker.patch("bot.manual_queue.requests.get", return_value=mock_response)
    return mock_get, mock_response

def test_fetch_url_content_success(mock_requests_get):
    """Tests fetching HTML content and extracting title successfully."""
    mock_get, mock_response = mock_requests_get
    test_url = "http://example.com/page"

    title, content = manual_queue.fetch_url_content(test_url)

    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)
    assert title == "Test Title"
    assert content == "Paragraph 1.\nParagraph 2."

def test_fetch_url_content_no_title_fallback_h1(mock_requests_get):
    """Tests fallback to H1 tag if title tag is missing."""
    mock_get, mock_response = mock_requests_get
    mock_response.content = b"<html><head></head><body><h1>Main Heading</h1><p>Some text.</p></body></html>"
    test_url = "http://example.com/no-title"

    title, content = manual_queue.fetch_url_content(test_url)

    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)
    assert title == "Main Heading"
    assert content == "Some text."

def test_fetch_url_content_no_title_fallback_url(mock_requests_get):
    """Tests fallback to URL path if title and H1 are missing."""
    mock_get, mock_response = mock_requests_get
    mock_response.content = b"<html><head></head><body><p>Just a paragraph.</p></body></html>"
    test_url = "http://example.com/just-a-para"

    title, content = manual_queue.fetch_url_content(test_url)

    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)
    assert title == "just-a-para" # Fallback to URL path component
    assert content == "Just a paragraph."

def test_fetch_url_content_not_html(mock_requests_get):
    """Tests handling of non-HTML content."""
    mock_get, mock_response = mock_requests_get
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.content = b"%PDF-1.4..."
    test_url = "http://example.com/document.pdf"

    title, content = manual_queue.fetch_url_content(test_url)

    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)
    assert title == "document.pdf" # Fallback to URL path component
    assert content is None

def test_fetch_url_content_request_error(mock_requests_get):
    """Tests handling of requests exceptions."""
    mock_get, mock_response = mock_requests_get
    mock_get.side_effect = requests.exceptions.RequestException("Connection error")
    test_url = "http://example.com/error"

    title, content = manual_queue.fetch_url_content(test_url)

    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)
    assert title is None
    assert content is None

def test_add_url_to_queue_success(setup_test_db, mock_requests_get):
    """Tests adding a new URL to the queue successfully."""
    mock_get, mock_response = mock_requests_get
    test_url = "http://example.com/new-article"

    success = manual_queue.add_url_to_queue(test_url)

    assert success is True
    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)

    # Check DB content
    articles = db.get_unposted_articles()
    assert len(articles) == 1
    article_id, guid, title, link, published_date, content, feed_source = articles[0]
    assert guid == test_url
    assert title == "Test Title"
    assert link == test_url
    assert published_date is None
    assert content == "Paragraph 1.\nParagraph 2."
    assert feed_source == "manual"

def test_add_url_to_queue_already_exists(setup_test_db, mock_requests_get):
    """Tests attempting to add a URL that already exists."""
    mock_get, mock_response = mock_requests_get
    test_url = "http://example.com/existing-article"

    # Add it the first time
    manual_queue.add_url_to_queue(test_url)
    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)

    # Reset mock for the second call
    mock_get.reset_mock()

    # Attempt to add it again
    success = manual_queue.add_url_to_queue(test_url)

    assert success is False # Should indicate it wasn't added (already exists)
    # fetch_url_content should NOT be called the second time because add_article returns False
    # However, the current implementation calls fetch_url_content *before* db.add_article.
    # Let's assert fetch was called again, but DB count remains 1.
    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)

    # Check DB content - should still only have 1 entry
    articles = db.get_unposted_articles()
    assert len(articles) == 1
    assert articles[0][1] == test_url # Check GUID

def test_add_url_to_queue_fetch_fails(setup_test_db, mock_requests_get):
    """Tests adding a URL when the initial fetch fails."""
    mock_get, mock_response = mock_requests_get
    mock_get.side_effect = requests.exceptions.RequestException("Fetch error")
    test_url = "http://example.com/fetch-error"

    success = manual_queue.add_url_to_queue(test_url)

    assert success is False
    mock_get.assert_called_once_with(test_url, headers=manual_queue.HEADERS, timeout=10)

    # Check DB content - should be empty
    articles = db.get_unposted_articles()
    assert len(articles) == 0
