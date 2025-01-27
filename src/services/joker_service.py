import logging
from typing import List

from domain.models import JokerCard
from domain.interfaces import JokerRepository


class JokerServiceError(Exception):
    """Base exception class for JokerService-related errors."""

    pass


class JokerNotFoundError(JokerServiceError):
    """Exception raised when a requested joker card cannot be found."""

    pass


class JokerValidationError(JokerServiceError):
    """Exception raised when a joker card fails validation."""

    pass


class JokerService:
    """Service class implementing business logic for joker card operations.

    This service acts as an intermediary between the repository layer and the
    application layer, handling data retrieval, validation, and formatting of
    joker card information for the Reddit bot's responses.

    Attributes:
        repository (JokerRepository): Data access layer for joker operations
        logger (Logger): Logger instance for service-level logging
    """

    def __init__(self, repository: JokerRepository):
        """Initialize the joker service with a repository instance.

        Args:
            repository: Implementation of JokerRepository interface for data access
        """
        self.repository = repository
        self.logger = logging.getLogger(__name__)

    def get_joker_information(self, name: str) -> JokerCard:
        """Retrieve and validate information for a specific joker card.

        This method fetches joker data from the repository and ensures its
        validity before returning it to the caller. It implements multiple
        validation steps to ensure data integrity.

        Args:
            name: The name of the joker card to retrieve

        Returns:
            JokerCard: Validated joker card instance

        Raises:
            JokerNotFoundError: If the requested joker doesn't exist
            JokerValidationError: If the joker data fails validation
            JokerServiceError: For other unexpected errors during retrieval
        """
        try:
            joker = self.repository.get_joker_information(name)
            if not joker:
                self.logger.warning(f"Joker not found: {name}")
                raise JokerNotFoundError(f"Joker not found: {name}")

            if not joker.validate():
                self.logger.error(f"Invalid data for Joker: {name}")
                raise JokerValidationError(f"Invalid data for Joker: {name}")

            self.logger.debug(f"Successfully retrieved Joker: {name}")
            return joker

        except (JokerNotFoundError, JokerValidationError):
            raise

        except Exception as e:
            self.logger.error(f"Error retrieving Joker {name}: {str(e)}")
            raise JokerServiceError(f"Error retrieving Joker {name}: {str(e)}")

    def format_joker_response(self, joker: JokerCard) -> str:
        """Format a joker card's information for Reddit response.

        Converts a JokerCard instance into a formatted string suitable for
        posting as a Reddit comment. The format includes the joker's name,
        cost, rarity, effect, and availability information.

        Args:
            joker: JokerCard instance to format

        Returns:
            str: Formatted Reddit-compatible markdown string

        Raises:
            JokerServiceError: If formatting fails for any reason
        """
        try:
            return (
                f"[[{joker.name}]]: Cost: {joker.cost}, Rarity: {joker.rarity}\\"
                f"Effect: {joker.effect}\\"
                f"Availability: {joker.availability}\\"
            )
        except Exception as e:
            self.logger.error(f"Error formatting Joker response: {str(e)}")
            raise JokerServiceError(f"Error formatting Joker response: {str(e)}")

    def format_multiple_jokers(self, joker_names: List[str]) -> str:
        """Process and format multiple joker cards into a single response.

        Retrieves and formats information for multiple joker cards, handling
        failures gracefully by skipping problematic entries while still
        processing the rest.

        Args:
            joker_names: List of joker names to process

        Returns:
            str: Combined formatted response for all successfully processed jokers,
                 with responses separated by newlines

        Note:
            This method will not raise exceptions for individual joker failures,
            instead logging warnings and continuing with the remaining jokers.
            Only successfully processed jokers will appear in the final output.
        """
        responses = []

        for name in joker_names:
            try:
                joker = self.get_joker_information(name)
                responses.append(self.format_joker_response(joker))
            except JokerNotFoundError:
                self.logger.warning(f"Joker not found: {name}")
            except Exception as e:
                self.logger.error(f"Error processing joker {name}: {str(e)}")
                continue

        return "\n\n".join(responses)

    def get_joker_name_list(self) -> List[str]:
        """Retrieve a list of all available joker names.

        Provides access to the complete list of joker names in the system,
        typically used for validation or reference purposes.

        Returns:
            List[str]: List of all joker names in the repository

        Raises:
            JokerServiceError: If retrieval fails for any reason
        """
        try:
            return self.repository.get_joker_name_list()
        except Exception as e:
            self.logger.error(f"Error retrieving Joker list: {str(e)}")
            raise JokerServiceError(f"Error retrieving Joker list: {str(e)}")
