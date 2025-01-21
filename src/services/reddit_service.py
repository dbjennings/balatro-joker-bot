import time
import logging
import os
from typing import Iterator, Optional
from dataclasses import dataclass
from contextlib import contextmanager

import praw
import praw.exceptions
import praw.models
import prawcore.exceptions
from praw.models import Comment

from dotenv import load_dotenv


# Custom exceptions for clear error handling paths
class RedditServiceError(Exception):
    """Base exception for Reddit service-related errors."""

    pass


class RedditConnectionError(Exception):
    """Raised when Reddit connection fails."""

    pass


class RedditAuthenticationError(Exception):
    """Raised when Reddit authentication fails."""

    pass


class RedditRateLimitError(Exception):
    """Raised when Reddit rate limit is exceeded."""

    pass


# Configuration data class for Reddit service
@dataclass
class RedditConfig:
    """
    Configuration data class for Reddit service.
    """

    client_id: str
    client_secret: str
    user_agent: str
    username: str
    password: str
    subreddit: str
    retry_limit: int = 3
    retry_delay: int = 5
    batch_limit: int = 100


class RedditService:
    """
    Service class for handling all Reddit API interactions.

    This class provides a clean interface for Reddit operations while handling:
    - Connection management
    - Error handling and retries
    - Rate limiting
    - Logging
    - Resource cleanup

    Attributes:
        config (RedditConfig): Configuration settings
        reddit (praw.Reddit): PRAW Reddit instance
        subreddit (praw.models.Subreddit): Subreddit instance
        logger (logging.Logger): Logger instance
    """

    def __init__(self, config: RedditConfig):
        """
        Initialize the Reddit service with configuration.

        Args:
            config: RedditConfig instance containing Reddit credentials and settings

        Raises:
            RedditAuthenticationError: If authentication fails
            RedditConnectionError: If connection cannot be established
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._initialize_reddit()

    def _initialize_reddit(self) -> None:
        try:
            self.reddit = praw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                user_agent=self.config.user_agent,
                username=self.config.username,
                password=self.config.password,
            )
            self.subreddit = self.reddit.subreddit(self.config.subreddit)
            self.logger.info(
                f"Successfully connected to Reddit API and subscribed to r/{self.config.subreddit}"
            )
        except praw.exceptions.PRAWException as e:
            self.logger.error(f"Reddit authentication failed: {str(e)}")
            raise RedditAuthenticationError(f"Failed to connect to Reddit: {str(e)}")
        except Exception as e:
            self.logger.error(f"Reddit connection failed: {str(e)}")
            raise RedditConnectionError(f"Failed to connect to Reddit: {str(e)}")

    @contextmanager
    def _handle_reddit_errors(self, operation: str):
        """
        Context manager for handling Reddit API errors consistently.

        Args:
            operation: Name of the operation being performed for logging

        Raises:
            RedditServiceError: On various Reddit API errors
        """
        try:
            yield
        except praw.exceptions.PRAWException as e:
            self.logger.error(f"PRAW error during {operation}: {str(e)}")
            raise RedditServiceError(f"Reddit API error during {operation}: {str(e)}")
        except prawcore.exceptions.ResponseException as e:
            self.logger.error(f"Reddit API response error during {operation}: {str(e)}")
            raise RedditServiceError(f"Reddit API response error: {str(e)}")
        except prawcore.exceptions.RequestException as e:
            self.logger.error(f"Reddit request error during {operation}: {str(e)}")
            raise RedditConnectionError(f"Reddit connection error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error during {operation}: {str(e)}")
            raise RedditServiceError(f"Unexpected error: {str(e)}")

    def _retry_on_failure(self, operation: callable, *args, **kwargs):
        """
        Retry an operation with exponential backoff to prevent hitting rate limit cap.

        Args:
            operation: Callable operation to retry
            args: Positional arguments for the operation
            kwargs: Keyword arguments for the operation

        Returns:
            Operation result if successful

        Raises:
            RedditServiceError: If operation fails after all retries
        """
        retries = 0
        while retries < self.config.retry_limit:
            try:
                return operation(*args, **kwargs)
            except RedditRateLimitError:
                wait_time = self.config.retry_delay * (2**retries)
                self.logger.warning(
                    f"Rate limit exceeded, waiting {wait_time} seconds before retrying"
                )
                time.sleep(wait_time)
                retries += 1
            except (RedditConnectionError, RedditServiceError) as e:
                if retries == self.config.retry_limit - 1:
                    raise
                wait_time = self.config.retry_delay * (2**retries)
                self.logger.warning(
                    f"Operation failed, waiting {wait_time} seconds before retrying {retries + 1}: {str(e)}"
                )
                time.sleep(wait_time)
                retries += 1

        raise RedditServiceError(
            f"Operation failed after {self.config.retry_limit} retries"
        )

    def get_comment_stream(self) -> Iterator[Comment]:
        """
        Get a stream of new comments from the subreddit.

        Returns:
            Iterator[Comment]: Stream of new comments

        Raises:
            RedditServiceError: On various Reddit API errors
        """

        def stream_operation():
            with self._handle_reddit_errors("comment stream"):
                return self.subreddit.stream.comments(skip_existing=True)

        return self._retry_on_failure(stream_operation)

    def reply_to_comment(self, comment: Comment, response: str) -> None:
        """
        Reply to a Reddit comment with proper error handling and retries.

        Args:
            comment: Reddit comment to reply to
            response: Text content of the reply

        Raises:
            RedditServiceError: If reply fails after retries
        """

        def reply_operation():
            with self._handle_reddit_errors("comment reply"):
                reply = comment.reply(response)
                self.logger.info(f"Successfully eplied to comment {comment.id}")
                return reply

        self._retry_on_failure(reply_operation)

    def get_comment_by_id(self, comment_id: str) -> Optional[Comment]:
        """
        Get a Reddit comment by its ID.

        Args:
            comment_id: Reddit comment ID

        Returns:
            Optional[Comment]: Reddit comment if found, None otherwise

        Raises:
            RedditServiceError: On various Reddit API errors
        """

        def fetch_operation():
            with self._handle_reddit_errors(f"fetch comment {comment_id}"):
                try:
                    comment = self.reddit.comment(comment_id)
                    comment.refresh()
                    return comment
                except praw.exceptions.ClientException:
                    self.logger.warning(f"Comment {comment_id} not found")
                    return None

        return self._retry_on_failure(fetch_operation)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = RedditConfig(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USER_NAME"],
        password=os.environ["REDDIT_USER_PASSWORD"],
        user_agent=os.environ["REDDIT_USER_AGENT"],
        subreddit="balatro",
    )

    service = RedditService(config)

    for comment in service.get_comment_stream():
        print(comment.body)


if __name__ == "__main__":
    main()
