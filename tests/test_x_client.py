# tests/test_x_client.py
import os
import pytest
from unittest.mock import patch, MagicMock
from requests_oauthlib import OAuth2Session
from bot.x_client import XClient, TOKEN_URL, POST_TWEET_URL

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mocks environment variables for X API credentials."""
    monkeypatch.setenv("X_API_KEY", "test_key")
    monkeypatch.setenv("X_API_SECRET", "test_secret")
    monkeypatch.setenv("X_ACCESS_TOKEN", "test_access_token")
    monkeypatch.setenv("X_REFRESH_TOKEN", "test_refresh_token")

@pytest.fixture
def mock_oauth_session(mocker):
    """Mocks the OAuth2Session object."""
    mock_session = MagicMock(spec=OAuth2Session)
    mock_session.post.return_value = MagicMock(status_code=200)
    mock_session.post.return_value.json.return_value = {"data": {"id": "123", "text": "Test tweet"}}
    mocker.patch("bot.x_client.OAuth2Session", return_value=mock_session)
    return mock_session

def test_xclient_init_success(mock_env_vars, mock_oauth_session):
    """Tests successful initialization of XClient."""
    client = XClient()
    assert client.api_key == "test_key"
    assert client.api_secret == "test_secret"
    assert client.access_token == "test_access_token"
    assert client.refresh_token == "test_refresh_token"
    assert isinstance(client.client, MagicMock) # Check if the mocked session is used
    # Check if OAuth2Session was called correctly
    from bot.x_client import OAuth2Session # Re-import to get the mocked version
    OAuth2Session.assert_called_once_with(
        client_id="test_key",
        token={
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "Bearer",
            "expires_in": -30
        },
        auto_refresh_url=TOKEN_URL,
        auto_refresh_kwargs={
            "client_id": "test_key",
            "client_secret": "test_secret",
        },
        token_updater=client._token_updater
    )

def test_xclient_init_missing_env_var(monkeypatch):
    """Tests XClient initialization failure when an env var is missing."""
    for key in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_REFRESH_TOKEN"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("X_API_KEY", "test_key")
    # Missing X_API_SECRET, X_ACCESS_TOKEN, X_REFRESH_TOKEN
    with pytest.raises(ValueError, match="Missing one or more X API credentials"):
        XClient()

def test_post_tweet_success(mock_env_vars, mock_oauth_session):
    """Tests successful tweet posting."""
    client = XClient()
    tweet_text = "This is a test tweet"
    response = client.post_tweet(tweet_text)

    # Check if the post method on the mock session was called correctly
    mock_oauth_session.post.assert_called_once_with(POST_TWEET_URL, json={"text": tweet_text})
    assert response == {"data": {"id": "123", "text": "Test tweet"}}

@patch("bot.x_client.logger") # Mock the logger
def test_post_tweet_api_error(mock_logger, mock_env_vars, mock_oauth_session):
    """Tests tweet posting failure due to API error."""
    # Configure the mock session to raise an exception
    mock_response = MagicMock(status_code=400)
    mock_response.raise_for_status.side_effect = Exception("API Error")
    mock_response.text = "Bad Request"
    mock_oauth_session.post.return_value = mock_response

    client = XClient()
    with pytest.raises(Exception, match="API Error"):
        client.post_tweet("Another test")

    # Check if error was logged
    mock_logger.error.assert_called()
    args, kwargs = mock_logger.error.call_args_list[0]
    assert "Failed to post tweet: API Error" in args[0]
    args, kwargs = mock_logger.error.call_args_list[1]
    assert "Response status: 400" in args[0]
    args, kwargs = mock_logger.error.call_args_list[2]
    assert "X API response body omitted from logs." in args[0]

@patch("bot.x_client.logger")
def test_token_updater(mock_logger, mock_env_vars, mock_oauth_session):
    """Tests the _token_updater callback function."""
    client = XClient() # Initialize client to access _token_updater
    new_token = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "token_type": "Bearer",
        "expires_in": 3600
    }
    client._token_updater(new_token)

    assert client.access_token == "new_access_token"
    assert client.refresh_token == "new_refresh_token"
    assert os.environ["X_ACCESS_TOKEN"] == "new_access_token"
    assert os.environ["X_REFRESH_TOKEN"] == "new_refresh_token"

    mock_logger.info.assert_any_call("Refreshing X API token.")
    mock_logger.info.assert_any_call("X API token refreshed. Persist refreshed tokens in a secure store before restarting.")

    logged_messages = [args[0] for args, _ in mock_logger.info.call_args_list]
    assert "new_access_token" not in " ".join(logged_messages)
    assert "new_refresh_token" not in " ".join(logged_messages)
