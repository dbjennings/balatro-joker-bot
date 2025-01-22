"""
Balatro Database Module

This module implements a specialized database interface for the Balatro game's
joker card system. It extends the base database functionality with:
- Joker-specific schema initialization
- CRUD operations for joker cards
- Result caching for improved performance
- Proper cache invalidation on modifications

The module uses an LRU cache to store frequently accessed data and implements
proper cache invalidation strategies when data is modified.
"""

from typing import List, Optional
import os
import logging
import cachetools
from .base import BaseDatabase, QueryError, DatabaseConfig
from src.domain.models import JokerCard
from src.domain.interfaces import JokerRepository
from dotenv import load_dotenv


class BalatroRepository(BaseDatabase, JokerRepository):
    """
    Specialized database class for managing Balatro joker card data.

    Extends BaseDatabase with joker-specific functionality including:
    - Automatic schema initialization
    - Caching layer for improved read performance
    - Specialized CRUD operations for joker cards
    """

    def __init__(self, config: DatabaseConfig, *args, **kwargs):
        """
        Initialize Balatro database with caching support.

        Args:
            config: DatabaseConfig instance
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        super().__init__(config, *args, **kwargs)
        self.logger = logging.getLogger(__name__)
        # Initialize LRU cache with size limit of 1024 entries
        self.cache = cachetools.LRUCache(maxsize=1024)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """
        Initialize database schema for joker cards if not exists.

        Creates the jokers table with appropriate columns and indexes
        if they don't already exist in the database.

        Raises:
            QueryError: If schema initialization fails
        """
        schema = """
            CREATE TABLE IF NOT EXISTS jokers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                effect TEXT NOT NULL,
                rarity VARCHAR(10) NOT NULL,
                cost VARCHAR(5) NOT NULL,
                availability TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_jokers_name ON jokers (name);
        """

        try:
            self.execute_modification(schema)
            self.logger.info("Successfully initialized joker schema.")
        except QueryError as e:
            self.logger.error(f"Failed to initialize joker schema: {str(e)}")
            raise

    def get_joker_information(self, name: str) -> Optional[JokerCard]:
        """
        Retrieve information for a specific joker card.

        Implements a cache-first strategy, falling back to database query
        when cache miss occurs. Updates cache with new data when retrieved
        from database.

        Args:
            name: Name of the joker card

        Returns:
            Dictionary containing joker information or None if not found

        Raises:
            QueryError: If database query fails
        """
        cache_key = f"joker:{name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        query = """
            SELECT name, effect, rarity, cost, availability
            FROM jokers
            WHERE LOWER(name) = LOWER(%s);
        """

        try:
            result = self.execute_query(query, (name,))
            if result:
                joker = JokerCard.from_dict(result[0])
                self.cache[cache_key] = joker
                return joker
            return None
        except QueryError as e:
            # Reset cache if query fails to prevent stale data
            self.cache.pop(cache_key, None)
            self.logger.error(f"Failed to fetch joker information: {str(e)}")
            raise

    def get_joker_name_list(self) -> List[str]:
        """
        Retrieve list of all joker card names.

        Uses caching to improve performance for this frequently accessed list.

        Returns:
            List of joker card names

        Raises:
            QueryError: If database query fails
        """
        cache_key = "joker_list"
        if cache_key in self.cache:
            return self.cache[cache_key]

        query = "SELECT name FROM jokers ORDER BY name;"

        try:
            results = self.execute_query(query)
            joker_names = [row["name"] for row in results]
            self.cache[cache_key] = joker_names
            return joker_names
        except QueryError as e:
            self.cache.pop(cache_key, None)
            self.logger.error(f"Failed to fetch joker list: {str(e)}")
            raise

    def add_joker(self, joker: JokerCard) -> None:
        """
        Add or update a joker card in the database.

        Implements an UPSERT operation, creating new joker entries or updating
        existing ones. Properly invalidates relevant cache entries on modification.

        Args:
            joker_data: Dictionary containing joker card information

        Raises:
            QueryError: If database operation fails
        """
        query = """
            INSERT INTO jokers (name, effect, rarity, cost, availability)
            VALUES (%(name)s, %(effect)s, %(rarity)s, %(cost)s, %(availability)s)
            ON CONFLICT (name) DO UPDATE SET
                effect = EXCLUDED.effect,
                rarity = EXCLUDED.rarity,
                cost = EXCLUDED.cost,
                availability = EXCLUDED.availability,
                updated_at = CURRENT_TIMESTAMP;
        """

        try:
            self.execute_modification(query, joker.as_dict())
            # Invalidate affected cache entries
            self.cache.pop(f"joker:{joker.name.lower()}", None)
            self.cache.pop("joker_list", None)
            self.logger.info(f"Successfully added/updated joker: {joker.name}")
        except QueryError as e:
            self.logger.error(f"Failed to add joker: {str(e)}")
            raise

    def delete_joker(self, name: str) -> bool:
        """
        Delete a joker card from the database.

        Removes the specified joker card and invalidates relevant cache entries.

        Args:
            name: Name of the joker card to delete

        Returns:
            True if deletion was successful

        Raises:
            QueryError: If database operation fails
        """
        query = "DELETE FROM jokers WHERE LOWER(name) = LOWER(%s);"

        try:
            affected = self.execute_modification(query, (name,))
            # Invalidate affected cache entries if deletion successful
            if affected:
                self.cache.pop(f"joker:{name.lower()}", None)
                self.cache.pop("joker_list", None)
            self.logger.info(f"Successfully deleted joker: {name}")
            return True
        except QueryError as e:
            self.logger.error(f"Failed to delete joker: {str(e)}")
            raise


def main():
    """
    Main entry point for testing database functionality.
    """
    load_dotenv()

    config = DatabaseConfig(
        host="localhost",
        port=5432,
        user=os.environ["JOKER_DB_USER_NAME"],
        password=os.environ["JOKER_DB_PASSWORD"],
        database=os.environ["JOKER_DB_NAME"],
    )

    db = BalatroRepository(config)

    print(db.get_joker_name_list())

    new_joker = {
        "name": "Test Joker",
        "effect": "Test effect",
        "rarity": "UR",
        "cost": "3",
        "availability": "Limited",
    }


if __name__ == "__main__":
    main()
