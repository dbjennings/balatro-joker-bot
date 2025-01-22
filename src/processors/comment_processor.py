# Import necessary libraries for type hints, regex operations, logging, and Reddit API
from typing import List, Pattern, Set
import re
import logging
from praw.models import Comment
from dataclasses import dataclass

# Configure logging to both file and console output
# This helps with debugging and monitoring the application's behavior
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("processors.log"), logging.StreamHandler()],
)


@dataclass
class CommentProcessorConfig:
    """
    Configuration class for the comment processor, using dataclass for clean initialization
    and immutable configuration settings.

    Attributes:
        match_pattern (str): Regex pattern that handles both escaped and unescaped brackets
        match_phrases (List[str]): Valid phrases to match against (e.g., list of joker names)
        bot_username (str): Bot's username to prevent self-replies
        user_blacklist (List[str]): List of users to ignore
        ignore_case (bool): Whether to perform case-insensitive matching
        max_matches (int): Maximum number of matches to process per comment
        strip_whitespace (bool): Whether to remove leading/trailing whitespace from matches
    """

    match_pattern: str = (
        r"\\?\[\\?\[(.*?)\\?\]\\?\]"  # Handles both [[text]] and \[\[text\]\]
    )
    match_phrases: List[str]  # List of valid phrases to match against
    bot_username: str
    user_blacklist: List[str] = []  # Default to empty list if not provided
    ignore_case: bool = True
    max_matches: int = 10
    strip_whitespace: bool = True


class CommentProcessor:
    """
    Main processor class for extracting and validating matches from Reddit comments.
    Designed with separation of concerns in mind, focusing solely on text processing.
    """

    def __init__(self, config: CommentProcessorConfig):
        """
        Initialize the processor with configuration settings and compile the regex pattern.
        The pattern is compiled once at initialization for better performance.
        """
        self.config = config
        self._compiled_pattern: Pattern = self._compile_pattern()
        self.logger = logging.getLogger(__name__)

    def _compile_pattern(self) -> Pattern:
        """
        Compile the regex pattern with appropriate flags.

        Returns:
            Compiled regex pattern

        Raises:
            ValueError: If the regex pattern is invalid

        The pattern is compiled with IGNORECASE flag if specified in config.
        """
        flags = re.IGNORECASE if self.config.ignore_case else 0
        try:
            return re.compile(self.config.joker_pattern, flags)
        except re.error as e:
            self.logger.error(f"Invalid regex pattern: {str(e)}")
            raise ValueError(f"Invalid regex pattern: {str(e)}")

    def _clean_match(self, match: str) -> str:
        """
        Clean a matched string according to configuration settings.
        Currently handles whitespace stripping, but could be extended for other cleaning operations.
        """
        if self.config.strip_whitespace:
            match = match.strip()
        return match

    def _validate_match(self, match: str) -> bool:
        """
        Validate if a match is in the list of allowed phrases.
        Comparison is done case-insensitively since phrases are normalized at initialization.
        """
        return match.lower() in self.config.match_phrases

    def should_process_comment(self, comment: Comment) -> bool:
        """
        Determine if a comment should be processed based on multiple criteria:
        - Comment must exist and have valid attributes
        - Author must not be the bot itself
        - Author must not be blacklisted

        Args:
            comment: Reddit comment to validate

        Returns:
            bool: Whether the comment should be processed

        All exceptions are caught and logged to prevent processing interruption.
        """
        try:
            return all(
                [
                    comment is not None,
                    comment.author.name != self.config.bot_username,
                    comment.author.name not in self.user_blacklist,
                    hasattr(comment, "body") and comment.body is not None,
                    hasattr(comment, "author") and comment.author is not None,
                ]
            )
        except Exception as e:
            self.logger.error(f"Error while validating comment {comment.id}: {str(e)}")
            return False

    def extract_match_names(self, comment: Comment) -> List[str]:
        """
        Extract and validate matches from a comment's text.

        Args:
            comment: Reddit comment to process

        Returns:
            List of valid matched phrases

        The method implements several safeguards:
        - Validates comment before processing
        - Limits number of matches processed
        - Deduplicates matches using a set
        - Handles all exceptions gracefully
        """
        if not self.should_process_comment(comment):
            self.logger.debug(f"Ignoring comment {comment.id}- validation failed")
            return []

        try:
            matches = self._compiled_pattern.finditer(comment.body)
            valid_matches: Set[str] = set()

            for match in matches:
                if len(valid_matches) >= self.config.max_matches:
                    self.logger.debug(
                        f"Reached maximum matches ({self.config.max_matches}) for comment {comment.id}"
                    )
                    break

                cleaned_match = self._clean_match(match.group(1))

                if self._validate_match(cleaned_match):
                    valid_matches.add(cleaned_match)

        except Exception as e:
            self.logger.error(f"Error processing comment {comment.id}: {str(e)}")
            return set()


def default_comment_processor(
    bot_username: str, match_phrases: List[str], user_blacklist: List[str]
) -> CommentProcessor:
    """
    Factory function to create a CommentProcessor with default settings.

    Args:
        bot_username: Username of the bot
        match_phrases: List of valid phrases to match
        user_blacklist: List of users to ignore

    Returns:
        Configured CommentProcessor instance

    The function normalizes match phrases to ensure consistent matching:
    - Converts all phrases to lowercase
    - Strips whitespace
    """

    def clean_phrases(phrases: List[str]) -> List[str]:
        """Helper function to normalize phrases for consistent matching"""
        return [phrase.lower().strip() for phrase in phrases]

    config = CommentProcessorConfig(
        bot_username=bot_username,
        match_phrases=clean_phrases(match_phrases),
        user_blacklist=user_blacklist,
    )
    return CommentProcessor(config)
