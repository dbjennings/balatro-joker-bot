"""
PostgreSQL Database Interface for Balatro Game Joker Cards

This module provides a database interface for managing Balatro game joker cards using PostgreSQL.
It handles connection management, basic CRUD operations, and maintains a cached list of joker cards.

Database Schema:
    - Table: jokers.data
    - Columns: id, name, effect, rarity, cost, availability

Environment Variables Required:
    JOKER_DB_NAME: Database name
    JOKER_DB_USER_NAME: Database username
    JOKER_DB_PASSWORD: Database password
    JOKER_DB_PORT: Database port
    JOKER_DB_HOST: Database host address
"""

import os
import psycopg2
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class BalatroDB:
    """
    Database interface class for managing Balatro joker cards.

    This class provides methods for connecting to the PostgreSQL database,
    retrieving joker information, and inserting new joker cards. It implements
    context manager protocol for safe resource management.

    Attributes:
        db_connect: PostgreSQL database connection object
        db_cursor: Database cursor for executing queries
        _joker_list: Cached list of joker names
        _joker_quantity: Total number of jokers in database
    """

    def __init__(
        self,
        dbname: str = os.environ["JOKER_DB_NAME"] | None,
        username: str = os.environ["JOKER_DB_USER_NAME"] | None,
        password: str = os.environ["JOKER_DB_PASSWORD"] | None,
        port: str = os.environ["JOKER_DB_PORT"] | None,
        host: str = os.environ["JOKER_DB_HOST"] | None,
    ):
        """
        Initialize database connection using environment variables or provided parameters.

        Args:
            dbname: Database name (default: from environment)
            username: Database username (default: from environment)
            password: Database password (default: from environment)
            port: Database port (default: from environment)
            host: Database host address (default: from environment)

        Raises:
            RuntimeError: If database connection fails
        """
        self.db_connect = None
        self.db_cursor = None
        self._joker_list = None
        self._joker_quantity = None

        if all(v is not None for v in [dbname, username, password, port, host]):
            raise ValueError("Environment variables failed to load.")

        try:
            self.db_connect = psycopg2.connect(
                dbname=dbname, user=username, password=password, port=port, host=host
            )
            self.db_cursor = self.db_connect.cursor()
            print(f"Successfully connected to database: {dbname}")
        except psycopg2.Error as err:
            raise RuntimeError(f"Failed to connect to database: {err}")

        self._fetch_joker_list()

    def __del__(self):
        """
        Destructor to ensure database resources are properly cleaned up.
        Closes cursor and connection if they exist.
        """
        if self.db_cursor:
            self.db_cursor.close()
        if self.db_connect:
            self.db_connect.close()

    def __enter__(self):
        """
        Context manager entry point.

        Returns:
            BalatroDB: The database interface instance
        """
        return self

    def __exit__(self, exc_type, exc_value, tb):
        """
        Context manager exit point. Ensures proper resource cleanup.

        Args:
            exc_type: Exception type if an error occurred
            exc_value: Exception value if an error occurred
            tb: Traceback if an error occurred

        Returns:
            bool: False if an exception occurred, True otherwise
        """
        if exc_type is not None:
            return False

        if self.db_cursor:
            self.db_cursor.close()
        if self.db_connect:
            self.db_connect.close()

        return True

    def _fetch_joker_list(self) -> List:
        """
        Private method to fetch and cache the list of joker names from database.

        Updates the internal _joker_list and _joker_quantity attributes.

        Raises:
            Exception: If database query fails
        """
        try:
            self.db_cursor.execute("SELECT name FROM jokers.data;")
            joker_list = self.db_cursor.fetchall()
            self.db_connect.commit()
        except:
            self.db_connect.rollback()
            raise

        self._joker_list = list([data[0].lower() for data in joker_list])
        self._joker_quantity = len(self._joker_list)

    def joker_list(self) -> List:
        """
        Get the list of all joker names in the database.

        Returns:
            List: List of joker names in lowercase
        """
        if not self._joker_list:
            self._fetch_joker_list()
        return self._joker_list

    def fetch_joker_information(self, joker_name: str) -> Dict:
        """
        Retrieve detailed information about a specific joker.

        Args:
            joker_name: Name of the joker to fetch information for

        Returns:
            Dict: Dictionary containing joker details:
                - effect: Joker's effect description
                - rarity: Joker's rarity level
                - cost: Joker's cost value
                - availability: Joker's availability status

        Raises:
            ValueError: If joker_name is not valid
            RuntimeError: If no data found for joker
            Exception: For other database errors
        """
        joker_name = joker_name.lower()

        if joker_name not in self.joker_list():
            raise ValueError(f"{joker_name} not a valid name")

        try:
            self.db_cursor.execute(
                "SELECT effect, rarity, cost, availability FROM joker_data WHERE name = %s;",
                (joker_name,),
            )
            joker_data = self.db_cursor.fetchone()
            # Transaction success
            self.db_connect.commit()

            if joker_data is None:
                raise RuntimeError(f"No data found for joker: {joker_name}")

            return {
                "effect": joker_data[0],
                "rarity": joker_data[1],
                "cost": joker_data[2],
                "availability": joker_data[3],
            }

        except Exception as e:
            # Transaction failure
            self.db_connect.rollback()
            raise

    def insert_joker(
        self, name: str, effect: str, rarity: str, cost: str, availability: str
    ) -> bool:
        """
        Insert a new joker card into the database.

        Args:
            name: Joker name
            effect: Joker effect description
            rarity: Joker rarity level
            cost: Joker cost value
            availability: Joker availability status

        Returns:
            bool: True if insertion successful, False if joker already exists

        Raises:
            RuntimeError: If insertion fails
        """
        if name.lower() in self.joker_list():
            print(f"Joker: {name} already exists.  Insertion skipped.")
            return False
        try:
            self.db_cursor.execute(
                """INSERT INTO jokers.data (id, name, effect, rarity, cost, availability)
                VALUES (%s, %s, %s, %s, %s, %s);""",
                (
                    self._joker_quantity + 1,
                    name.strip(),
                    effect.strip(),
                    rarity.strip(),
                    cost.strip(),
                    availability.strip(),
                ),
            )
            # Transaction success
            self.db_connect.commit()
            # Refresh joker list
            self._fetch_joker_list()
            return True
        except psycopg2.Error as e:
            # Transaction failure
            self.db_connect.rollback()
            raise RuntimeError(f"Failed to insert joker: {str(e)}")


def main():
    """
    Main entry point for testing database connection and basic functionality.
    """
    try:
        with BalatroDB() as db:
            jokers = db.joker_list()
            print(f"The Full Ante: {jokers}")
    except Exception as err:
        print(f"Error: {err}")


if __name__ == "__main__":
    main()
