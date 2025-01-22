"""
Domain Model Module for Joker Cards

This module defines the core domain model for Joker cards in the Balatro game system.
It implements a dataclass-based model with built-in validation rules and data
transformation capabilities. 

The JokerCard class serves as a single model for what constitutes valid
Joker card data, implementing both structural validation (correct types) and
semantic validation (appropriate value ranges and content).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class JokerCard:
    """
    Represents a Joker card in the Balatro game system.

    This class encapsulates all the essential information about a Joker card,
    including its properties, effects, and metadata. It provides built-in validation
    to ensure data integrity and methods for data transformation.

    Attributes:
        name (str): The unique identifier and display name of the Joker card
        effect (str): Description of the Joker's gameplay effect
        rarity (str): The card's rarity level (e.g., Common, Rare, etc.)
        cost (str): The resource cost to acquire or use the Joker
        availability (str): How/where the Joker can be obtained in the game
        created_at (datetime): Timestamp of when the Joker was first created
        updated_at (datetime): Timestamp of the last modification to the Joker

    The class uses dataclass for automatic generation of common methods like
    __init__, __repr__, and __eq__, while adding custom validation logic
    to ensure data integrity.
    """

    name: str
    effect: str
    rarity: str
    cost: str
    availability: str
    # Auto-generated timestamps using field factory to ensure current time
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def as_dict(self) -> dict:
        """
        Convert Joker card data to a dictionary.

        Returns:
            dict: Dictionary containing Joker card data

        This method provides a convenient way to serialize Joker card instances
        to a dictionary for use in JSON serialization, database storage, etc.
        """
        return {
            "name": self.name,
            "effect": self.effect,
            "rarity": self.rarity,
            "cost": self.cost,
            "availability": self.availability,
        }

    def validate(self) -> bool:
        """
        Validate all attributes of the Joker card.

        Performs comprehensive validation of all fields, ensuring:
        - All required fields are present
        - Fields contain appropriate data types
        - String lengths fall within acceptable ranges
        - Values are properly formatted and non-empty

        Returns:
            bool: True if all validations pass, False otherwise

        This method is designed to fail safely, returning False instead of
        raising exceptions for invalid data. This makes it suitable for
        validation in input processing pipelines.
        """
        try:
            return all(
                [
                    # Name validation: non-empty string between 1-50 characters
                    self.name
                    and isinstance(self.name, str)
                    and self._is_length_valid(self.name, 1, 50),
                    # Effect validation: non-empty string with no max length
                    self.effect
                    and isinstance(self.effect, str)
                    and self._is_length_valid(self.effect, 1),
                    # Rarity validation: string between 1-10 characters
                    self.rarity
                    and isinstance(self.rarity, str)
                    and self._is_length_valid(self.rarity, 1, 10),
                    # Cost validation: string between 1-5 characters
                    self.cost
                    and isinstance(self.cost, str)
                    and self._is_length_valid(self.cost, 1, 5),
                    # Availability validation: non-empty string with no max length
                    self.availability
                    and isinstance(self.availability, str)
                    and self._is_length_valid(self.name, 1),
                ]
            )
        except Exception:
            # Fail safely if any validation raises an unexpected error
            return False

    @staticmethod
    def _is_length_valid(
        value: str, min_length: int, max_length: Optional[int] = None
    ) -> bool:
        """
        Validate string length falls within specified bounds.

        This helper method ensures string lengths meet requirements while
        handling edge cases appropriately. It strips whitespace before
        checking length to prevent artificially padded strings from
        passing validation.

        Args:
            value: The string to validate
            min_length: Minimum acceptable length (inclusive)
            max_length: Maximum acceptable length (inclusive), or None for no maximum

        Returns:
            bool: True if length is within bounds, False otherwise

        The method is marked as staticmethod since it doesn't need access
        to instance data and could potentially be useful in other contexts.
        """
        if max_length:
            return min_length <= len(value.strip()) <= max_length
        return min_length <= len(value.strip())

    @classmethod
    def from_dict(cls, data: dict) -> "JokerCard":
        """
        Create a JokerCard instance from a dictionary.

        Factory method that provides a convenient way to create JokerCard
        instances from dictionary data (e.g., from JSON or database results).
        Performs basic data cleaning and validation before instantiation.

        Args:
            data: Dictionary containing Joker card data

        Returns:
            JokerCard: New instance with provided data

        Raises:
            ValueError: If required fields are missing from input data

        This method provides input validation separate from the instance
        validation in validate(), focusing on data presence and basic
        structure rather than content validity.
        """
        # Define required fields for a valid Joker card
        required_fields = ["name", "effect", "rarity", "cost", "availability"]
        supplied_fields = set(data.keys())
        missing_fields = [
            field for field in required_fields if field not in supplied_fields
        ]

        # Check for missing required fields before processing
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Clean input data by stripping whitespace from string fields
        for field in data.keys():
            if isinstance(data[field], str):
                data[field] = data[field].strip()

        return cls(**data)
