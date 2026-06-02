# bot/x_client.py
import os
import logging
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient, TokenExpiredError

logger = logging.getLogger(__name__)

# X API v2 endpoints
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
POST_TWEET_URL = "https://api.twitter.com/2/tweets"

class XClient:
    def __init__(self):
        self.api_key = os.environ.get("X_API_KEY")
        self.api_secret = os.environ.get("X_API_SECRET")
        self.access_token = os.environ.get("X_ACCESS_TOKEN")
        self.refresh_token = os.environ.get("X_REFRESH_TOKEN")

        if not all([self.api_key, self.api_secret, self.access_token, self.refresh_token]):
            raise ValueError("Missing one or more X API credentials in environment variables.")

        self.client = self._get_oauth_session()

    def _token_updater(self, token):
        logger.info("Refreshing X API token.")
        self.access_token = token.get("access_token")
        self.refresh_token = token.get("refresh_token", self.refresh_token) # Keep old refresh token if new one isn't provided
        logger.info("X API token refreshed. Persist refreshed tokens in a secure store before restarting.")
        os.environ["X_ACCESS_TOKEN"] = self.access_token
        if self.refresh_token:
            os.environ["X_REFRESH_TOKEN"] = self.refresh_token


    def _get_oauth_session(self):
        token = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": "Bearer",
            "expires_in": -30 # Assume expired to force refresh check initially if needed
        }

        session = OAuth2Session(
            client_id=self.api_key,
            token=token,
            auto_refresh_url=TOKEN_URL,
            auto_refresh_kwargs={
                "client_id": self.api_key,
                "client_secret": self.api_secret,
            },
            token_updater=self._token_updater
        )
        return session

    def post_tweet(self, text: str) -> dict:
        """Posts a tweet to X using API v2."""
        payload = {"text": text}
        try:
            response = self.client.post(POST_TWEET_URL, json=payload)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info("Tweet posted successfully.")
            return response.json()
        except TokenExpiredError:
            logger.warning("Token expired during request, attempting refresh...")
            # Token refresh should happen automatically via token_updater
            # Retry the request after potential refresh
            try:
                response = self.client.post(POST_TWEET_URL, json=payload)
                response.raise_for_status()
                logger.info("Tweet posted successfully after token refresh.")
                return response.json()
            except Exception as e:
                logger.error(f"Failed to post tweet after token refresh: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
            logger.error(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
            logger.error("X API response body omitted from logs.")
            raise

# Example usage (for testing purposes, remove later)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Make sure to set environment variables before running
    # export X_API_KEY='...' X_API_SECRET='...' X_ACCESS_TOKEN='...' X_REFRESH_TOKEN='...'
    try:
        client = XClient()
        client.post_tweet("Hello from my bot! #Test")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
