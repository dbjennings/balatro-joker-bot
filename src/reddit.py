"""
Reddit Bot for Balatro Joker Card Information

This module implements a Reddit bot that monitors the r/balatro subreddit for mentions
of joker card names and responds with detailed information about those cards. The bot
uses the PRAW library for Reddit interaction and interfaces with a PostgreSQL database
through the BalatroDB class.

The bot identifies joker names in comments using regular expressions and formats
responses with card information including cost, rarity, effect, and availability.

Environment Variables Required:
    REDDIT_CLIENT_ID: Reddit API client ID
    REDDIT_CLIENT_SECRET: Reddit API client secret
    REDDIT_USER_PASSWORD: Reddit account password
    REDDIT_USER_AGENT: User agent string for Reddit API
    REDDIT_USER_NAME: Reddit account username

Usage:
    from reddit import BalatroBot
    
    bot = BalatroBot()
    bot.run()

Error Handling:
    The bot implements comprehensive error handling for:
    - Reddit API connection issues
    - Database connection failures
    - Rate limiting
    - Network timeouts
    - Invalid comment formats
"""

import re
import praw
import time
import logging
from typing import Set, List
from praw.exceptions import PRAWException
from prawcore.exceptions import (
    RequestException,
    ServerError,
)
import os
from balatrodb import BalatroDB

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("balatro_bot.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class RedditConnectionError(Exception):
    """Custom exception for Reddit connection issues."""

    pass


class BalatroBotError(Exception):
    """Base exception class for BalatroBot errors."""

    pass


class BalatroBot:
    """
    A Reddit bot that monitors and responds to joker card mentions in r/balatro.

    This class handles the core functionality of monitoring Reddit comments,
    identifying joker card mentions, fetching card information from the database,
    and posting formatted responses.

    Attributes:
        _db (BalatroDB): Database interface for joker card information
        _joker_pattern (str): Compiled regex pattern for identifying joker names
        MAX_RETRIES (int): Maximum number of connection retry attempts
        RETRY_DELAY (int): Delay in seconds between retry attempts
        MAX_JOKERS_PER_COMMENT (int): Maximum number of jokers to respond to in one comment
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 5
    MAX_JOKERS_PER_COMMENT = 10

    def __init__(self, db: BalatroDB = None):
        """
        Initialize the BalatroBot with database connection and Reddit configuration.

        Args:
            db (BalatroDB, optional): Database interface instance. If None, creates new instance.

        Raises:
            BalatroBotError: If database initialization fails
        """
        try:
            self._db = db if db is not None else BalatroDB()
            self._joker_pattern = self._compile_joker_pattern()
            logger.info("BalatroBot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BalatroBot: {str(e)}")
            raise BalatroBotError(f"Bot initialization failed: {str(e)}")

    def _compile_joker_pattern(self) -> str:
        """
        Create a regex pattern for matching joker names in comments.

        This method specifically excludes the basic "Joker" card from pattern matching
        to prevent false positives in general discussion about jokers. The exclusion
        is handled at the pattern compilation level rather than the database level.

        For example, this will match:
            - "Credit Card Joker" (specific joker name)
            - "Steel Joker" (specific joker name)
        But will not match:
            - "joker" (generic reference)
            - "Joker" (generic reference)

        Returns:
            str: Compiled regex pattern for matching specific joker names

        Raises:
            BalatroBotError: If pattern compilation fails
        """
        try:
            # Get the full list of jokers and filter out the basic "Joker" card
            joker_list = [joker for joker in self._db.joker_list() if joker != "joker"]

            # Create patterns only for multi-word jokers or unique named jokers
            patterns = []
            for joker in joker_list:
                patterns.append(r"\b" + re.escape(joker) + r"\b")

            # Join all patterns with OR operator
            pattern = "|".join(patterns)

            logger.debug(f"Compiled joker pattern (excluding basic Joker): {pattern}")
            return pattern

        except Exception as e:
            logger.error(f"Failed to compile joker pattern: {str(e)}")
            raise BalatroBotError(f"Pattern compilation failed: {str(e)}")

    def _find_comment_jokers(self, body: str) -> Set[str]:
        """
        Extract unique joker names from a comment body.

        Args:
            body (str): Comment text to search for joker names

        Returns:
            Set[str]: Unique joker names found in the comment

        Raises:
            BalatroBotError: If regex search fails
        """
        try:
            return set(re.findall(self._joker_pattern, body.lower()))
        except Exception as e:
            logger.error(f"Failed to search for jokers in comment: {str(e)}")
            raise BalatroBotError(f"Joker search failed: {str(e)}")

    def _format_joker_info(self, joker_name: str) -> str:
        """
        Format information about a specific joker card.

        Args:
            joker_name (str): Name of the joker card

        Returns:
            str: Formatted string containing joker information

        Raises:
            BalatroBotError: If joker information retrieval or formatting fails
        """
        try:
            joker = self._db.fetch_joker_information(joker_name)
            jstr = f"[[{joker['name']}]]: {joker['cost']}, {joker['rarity']}"
            jstr += f"\n{joker['effect']}\n{joker['availability']}\n"
            return jstr
        except Exception as e:
            logger.error(f"Failed to format joker info for {joker_name}: {str(e)}")
            raise BalatroBotError(f"Joker info formatting failed: {str(e)}")

    def _format_comment(self, joker_list: List[str]) -> str:
        """
        Create a formatted Reddit comment containing joker information.

        Args:
            joker_list (List[str]): List of joker names to include

        Returns:
            str: Formatted comment text

        Raises:
            BalatroBotError: If comment formatting fails
        """
        try:
            # Limit number of jokers to prevent oversized comments
            joker_list = joker_list[: self.MAX_JOKERS_PER_COMMENT]
            joker_data = [self._format_joker_info(joker) for joker in joker_list]
            comment = "\n".join(joker_data)
            comment += "\n\nThis reply brought to you by u/balatro-joker-bot"
            return comment
        except Exception as e:
            logger.error(f"Failed to format comment: {str(e)}")
            raise BalatroBotError(f"Comment formatting failed: {str(e)}")

    def _init_reddit(self) -> praw.Reddit:
        """
        Initialize the Reddit API connection.

        Returns:
            praw.Reddit: Initialized Reddit instance

        Raises:
            RedditConnectionError: If Reddit connection fails
        """
        try:
            return praw.Reddit(
                client_id=os.environ["REDDIT_CLIENT_ID"],
                client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                password=os.environ["REDDIT_USER_PASSWORD"],
                user_agent=os.environ["REDDIT_USER_AGENT"],
                username=os.environ["REDDIT_USER_NAME"],
            )
        except Exception as e:
            logger.error(f"Failed to initialize Reddit connection: {str(e)}")
            raise RedditConnectionError(f"Reddit initialization failed: {str(e)}")

    def _is_own_comment(self, comment: praw.models.Comment) -> bool:
        """
        Check if a comment was made by this bot.

        Args:
            comment (praw.models.Comment): Comment to check

        Returns:
            bool: True if comment was made by this bot, False otherwise

        Note:
            Handles cases where the author might be deleted or None
        """
        try:
            # Check if author exists and matches bot username
            return (
                comment.author is not None
                and comment.author.name == os.environ["REDDIT_USER_NAME"]
            )
        except AttributeError:
            # Handle case where author attribute might not exist
            return False

    def _handle_comment(self, comment: praw.models.Comment) -> None:
        """
        Process a single Reddit comment and post a response if needed.
        Skips processing if the comment was made by this bot.

        Args:
            comment (praw.models.Comment): Reddit comment to process

        Raises:
            BalatroBotError: If comment processing fails
        """
        try:
            # First check if this is our own comment
            if self._is_own_comment(comment):
                logger.debug(f"Skipping own comment {comment.id}")
                return

            present_jokers = self._find_comment_jokers(comment.body.lower())
            if present_jokers:
                response = self._format_comment(list(present_jokers))
                comment.reply(response)
                logger.info(f"Successfully replied to comment {comment.id}")
        except Exception as e:
            logger.error(f"Failed to handle comment {comment.id}: {str(e)}")
            raise BalatroBotError(f"Comment handling failed: {str(e)}")

    def run(self) -> None:
        """
        Main bot execution loop. Monitors Reddit for new comments and responds
        to joker mentions. Implements retry logic for connection issues.

        Raises:
            BalatroBotError: If bot execution fails after maximum retries
        """
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                reddit = self._init_reddit()
                subreddit = reddit.subreddit("balatro")
                logger.info("Starting comment stream")

                for comment in subreddit.stream.comments(skip_existing=True):
                    try:
                        self._handle_comment(comment)
                    except PRAWException as e:
                        logger.warning(f"PRAW error handling comment: {str(e)}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error handling comment: {str(e)}")
                        continue

            except (RequestException, ServerError) as e:
                logger.error(f"Reddit API error: {str(e)}")
                retries += 1
                if retries < self.MAX_RETRIES:
                    logger.info(f"Retrying in {self.RETRY_DELAY} seconds...")
                    time.sleep(self.RETRY_DELAY)
                continue

            except Exception as e:
                logger.critical(f"Critical error in bot execution: {str(e)}")
                raise BalatroBotError(f"Bot execution failed: {str(e)}")

        logger.error("Maximum retries exceeded. Bot shutting down.")
        raise BalatroBotError("Maximum retries exceeded")


def main():
    """
    Main entry point for the Reddit bot script.

    Sets up logging and environment variables, initializes the bot,
    and handles top-level exceptions.
    """
    try:
        load_dotenv()
        bot = BalatroBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
