"""
Interface Definitions Module for the Balatro Joker System

This module defines the core interfaces that establish the contract
between different components of the Balatro joker system.

The interfaces defined here serve as the primary abstraction layer between the
domain models and the various implementations, creating a loose coupling between components.

Two main protocols are defined:
1. JokerRepository - For data access operations
2. CommentProcessor - For Reddit comment processing operations
"""

from typing import Protocol, List, Optional, Set
from src.domain.models import JokerCard
import praw


class JokerRepository(Protocol):
    """
    Protocol defining the interface for joker data access operations.

    Implementations must provide methods for:
    - Retrieving individual joker cards
    - Getting a list of all available joker names
    - Saving new or updated joker cards
    """

    def get_joker_information(self, name: str) -> Optional[JokerCard]:
        """
        Retrieve a specific joker card by name.

        This method should handle the retrieval of joker data and return it
        in the form of a JokerCard domain model instance. It should also
        handle cases where the requested joker doesn't exist.

        Args:
            name: The name of the joker card to retrieve

        Returns:
            JokerCard instance if found, None if not found

        The implementation should handle any storage-specific errors and
        translate them into appropriate application-level exceptions.
        """
        ...

    def get_joker_names_list(self) -> List[str]:
        """
        Retrieve a list of all available joker card names.

        This method should return a complete list of all joker names in the
        system. The list should be sorted in a consistent manner (typically
        alphabetically) to provide a predictable order for display purposes.

        Returns:
            List of joker card names as strings

        The implementation should handle pagination or chunking if dealing
        with large datasets.
        """
        ...

    def add_joker(self, joker: JokerCard) -> None:
        """
        Save a new or updated joker card.

        This method should handle both creation of new joker cards and
        updates to existing ones. The implementation should determine
        whether to perform an insert or update based on the existence
        of the joker in the storage system.

        Args:
            joker: JokerCard instance to save

        The implementation should handle data validation and any necessary
        transformations between the domain model and storage format.
        """
        ...

    def delete_joker(self, name: str) -> None:
        """
        Delete a joker card by name.

        This method should remove the joker card with the specified name
        from the storage system. If the joker doesn't exist, the method
        should not raise an error.

        Args:
            name: The name of the joker card to delete

        The implementation should handle any storage-specific errors and
        ensure that the operation is idempotent.
        """
        ...


class CommentProcessor(Protocol):
    """
    Protocol defining the interface for Reddit comment processing operations.

    This protocol establishes the contract for components that handle Reddit
    comment analysis and processing. It defines methods for extracting joker
    references from comments and determining which comments should be processed.

    Implementations must provide methods for:
    - Extracting joker names from comment text
    - Determining if a comment should be processed
    """

    def extract_joker_names(self, comment: str) -> Set[str]:
        """
        Extract joker card names from a comment's text.

        This method should analyze the comment text and identify any
        references to joker cards. The implementation should handle
        various formats and patterns that might be used to reference
        joker cards in comments.

        Args:
            comment: The text content of the comment to analyze

        Returns:
            Set of unique joker names found in the comment

        The implementation should handle edge cases such as:
        - Duplicate references to the same joker
        - Case sensitivity
        - Common misspellings or variations
        """
        ...

    def should_process_comment(self, comment: praw.models.Comment) -> bool:
        """
        Determine if a comment should be processed.

        This method implements the logic for deciding whether a given
        comment should be analyzed for joker references. It helps filter
        out comments that don't need processing, such as:
        - Bot's own comments
        - Already processed comments
        - Comments from blocked users
        - Comments in inappropriate contexts

        Args:
            comment: praw Comment instance to evaluate

        Returns:
            True if the comment should be processed, False otherwise

        The implementation should consider various factors like comment
        metadata, author information, and any system-specific rules.
        """
        ...
