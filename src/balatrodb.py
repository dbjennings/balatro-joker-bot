# Standard library imports
import os
import logging
from typing import Dict, List, Optional
from contextlib import contextmanager

# Third-party imports
import psycopg2
from psycopg2.extras import DictCursor
from pydantic import BaseModel, Field, field_validator

# Configure logging with both file and console handlers for comprehensive monitoring
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("balatro.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# Custom exceptions for clear error handling paths
class DatabaseError(Exception):
    """Base exception for database-related errors."""

    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class QueryError(DatabaseError):
    """Raised when database queries fail."""

    pass


class ValidationError(Exception):
    """Raised when data validation fails."""

    pass


class JokerData(BaseModel):
    """
    Pydantic model for joker data validation.
    Ensures all joker data meets our requirements before database operations.
    """

    name: str = Field(..., min_length=1, max_length=100)
    effect: str = Field(..., min_length=1)
    rarity: str = Field(..., regex="^(Common|Uncommon|Rare|Legendary)$")
    cost: str = Field(..., min_length=1, max_length=20)
    availability: str = Field(..., min_length=1)

    @field_validator("name")
    def validate_name(cls, v):
        """Ensure name is properly formatted."""
        if not v.strip():
            raise ValueError("Name cannot be empty or just whitespace")
        return v.strip()

    class Config:
        extra = "forbid"  # Prevent unexpected fields


class BalatroDB:
    """
    Database interface for managing Balatro joker cards.
    Provides secure and reliable database operations with proper error handling.
    """

    def __init__(
        self,
        dbname: str = os.getenv("JOKER_DB_NAME"),
        username: str = os.getenv("JOKER_DB_USER_NAME"),
        password: str = os.getenv("JOKER_DB_PASSWORD"),
        port: str = os.getenv("JOKER_DB_PORT", "5432"),
        host: str = os.getenv("JOKER_DB_HOST", "localhost"),
    ):
        """
        Initialize database connection using environment variables or provided parameters.
        """
        self.connection_params = {
            "dbname": dbname,
            "user": username,
            "password": password,
            "port": port,
            "host": host,
            "cursor_factory": DictCursor,  # Use dictionary cursor for cleaner data access
        }

        self._db_conn = None
        self._db_cursor = None
        self._joker_dict = {}
        self._joker_quantity = 0

        # Establish initial connection and fetch joker data
        self._connect()
        self._fetch_joker_dict()

    def _connect(self) -> None:
        """
        Establish database connection with error handling.
        """
        try:
            self._db_conn = psycopg2.connect(**self.connection_params)
            self._db_cursor = self._db_conn.cursor()
            logger.info(
                f"Successfully connected to database: {self.connection_params['dbname']}"
            )

        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise ConnectionError(f"Failed to connect to database: {str(e)}")

    def __del__(self):
        """
        Ensure database resources are properly cleaned up.
        """
        if self._db_cursor:
            self._db_cursor.close()
        if self._db_conn:
            self._db_conn.close()
            logger.info("Database connection closed")

    @contextmanager
    def transaction(self):
        """
        Context manager for handling database transactions.
        Ensures proper commit/rollback handling.
        """
        try:
            yield self._db_cursor
            self._db_conn.commit()
        except Exception as e:
            self._db_conn.rollback()
            raise e

    def _fetch_joker_dict(self) -> None:
        """
        Cache joker names for efficient lookups.
        """
        query = """
            SELECT name 
            FROM jokers.data;
        """

        try:
            with self.transaction() as cursor:
                cursor.execute(query)
                joker_list = cursor.fetchall()

                # Create case-insensitive lookup dictionary
                self._joker_dict = {
                    row["name"].lower(): row["name"] for row in joker_list
                }
                self._joker_quantity = len(self._joker_dict)
                logger.debug(f"Cached {self._joker_quantity} joker names")

        except psycopg2.Error as e:
            logger.error(f"Failed to fetch joker list: {str(e)}")
            raise QueryError(f"Failed to fetch joker list: {str(e)}")

    def joker_list(self) -> List[str]:
        """
        Get list of all active joker names.
        Refreshes cache to ensure data accuracy.
        """
        try:
            self._fetch_joker_dict()  # Refresh the cache
            return list(self._joker_dict.keys())
        except Exception as e:
            logger.error(f"Error retrieving joker list: {str(e)}")
            raise QueryError(f"Failed to retrieve joker list: {str(e)}")

    def fetch_joker_information(self, joker_name: str) -> Dict:
        """
        Retrieve detailed information about a specific joker.

        Args:
            joker_name: Name of the joker to look up

        Returns:
            Dictionary containing joker details

        Raises:
            ValidationError: If joker name is invalid
            QueryError: If database query fails
        """
        joker_name = joker_name.lower()

        if joker_name not in self._joker_dict:
            raise ValidationError(f"Invalid joker name: {joker_name}")

        query = """
            SELECT effect, rarity, cost, availability
            FROM jokers.data
            WHERE name = %s;
        """

        try:
            with self.transaction() as cursor:
                cursor.execute(query, (self._joker_dict[joker_name],))
                joker_data = cursor.fetchone()

                if joker_data is None:
                    raise QueryError(f"No data found for joker: {joker_name}")

                return {
                    "name": self._joker_dict[joker_name],
                    "effect": joker_data["effect"],
                    "rarity": joker_data["rarity"],
                    "cost": joker_data["cost"],
                    "availability": joker_data["availability"],
                }

        except psycopg2.Error as e:
            logger.error(f"Error fetching joker information: {str(e)}")
            raise QueryError(f"Failed to fetch joker information: {str(e)}")

    def insert_joker(self, joker_data: Dict) -> bool:
        """
        Insert a new joker card into the database.

        Args:
            joker_data: Dictionary containing joker information

        Returns:
            True if insertion successful, False if joker already exists

        Raises:
            ValidationError: If joker data is invalid
            QueryError: If database insertion fails
        """
        try:
            # Validate input data using Pydantic model
            validated_data = JokerData(**joker_data)

            if validated_data.name.lower() in self._joker_dict:
                logger.info(f"Joker already exists: {validated_data.name}")
                return False

            query = """
                INSERT INTO jokers.data 
                (id, name, effect, rarity, cost, availability, active)
                VALUES (%s, %s, %s, %s, %s, %s, true);
            """

            with self.transaction() as cursor:
                cursor.execute(
                    query,
                    (
                        self._joker_quantity + 1,
                        validated_data.name,
                        validated_data.effect,
                        validated_data.rarity,
                        validated_data.cost,
                        validated_data.availability,
                    ),
                )
                logger.info(f"Successfully inserted joker: {validated_data.name}")

                # Refresh joker cache after successful insertion
                self._fetch_joker_dict()
                return True

        except psycopg2.Error as e:
            logger.error(f"Database error during joker insertion: {str(e)}")
            raise QueryError(f"Failed to insert joker: {str(e)}")
        except ValidationError as e:
            logger.error(f"Validation error during joker insertion: {str(e)}")
            raise


def main():
    """
    Example usage of the BalatroDB class.
    """
    try:
        db = BalatroDB()
        jokers = db.joker_list()
        logger.info(f"Successfully retrieved {len(jokers)} jokers")

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
