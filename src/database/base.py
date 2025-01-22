"""
Base Database Module

This module provides a foundational database interface implementing connection pooling
and basic database operations using psycopg2. It serves as the base layer for more
specific database implementations, handling core functionality like:
- Connection pool management
- Error handling and custom exceptions
- Basic query execution
- Resource cleanup

The module uses connection pooling to efficiently manage database connections and
implements context managers for safe resource handling.
"""

import os
from typing import Any, Optional
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from dataclasses import dataclass
from dotenv import load_dotenv


class DatabaseError(Exception):
    """Base exception for database-related errors."""

    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class QueryError(DatabaseError):
    """Raised when database query fails."""

    pass


@dataclass
class DatabaseConfig:
    """
    Configuration class for database connection settings.

    Attributes:
        host (str): Database server hostname
        port (int): Database server port
        user (str): Database username
        password (str): Database password
        database (str): Database name
        min_connections (int): Minimum number of connections in pool (default: 1)
        max_connections (int): Maximum number of connections in pool (default: 10)
    """

    host: str
    port: int
    user: str
    password: str
    database: str
    min_connections: int = 1
    max_connections: int = 10

    @classmethod
    def from_env(cls):
        load_dotenv()

        required_vars = [
            "JOKER_DB_NAME",
            "JOKER_DB_USER_NAME",
            "JOKER_DB_PASSWORD",
            "JOKER_DB_HOST",
            "JOKER_DB_PORT",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {", ".join(missing_vars)}"
            )

        return cls(
            host=os.getenv("JOKER_DB_HOST"),
            port=int(os.getenv("JOKER_DB_PORT")),
            user=os.getenv("JOKER_DB_USER_NAME"),
            password=os.getenv("JOKER_DB_PASSWORD"),
            database=os.getenv("JOKER_DB_NAME"),
            min_connections=int(os.getenv("JOKER_DB_MIN_CONNECTIONS", 1)),
            max_connections=int(os.getenv("JOKER_DB_MAX_CONNECTIONS", 10)),
        )


class BaseDatabase:
    """
    Base database class implementing connection pooling and core database operations.

    This class provides the foundation for database interactions, handling:
    - Connection pool initialization and management
    - Safe connection acquisition and release
    - Basic query execution with error handling
    - Resource cleanup through context manager support
    """

    def __init__(self, config: DatabaseConfig):
        """
        Initialize database connection pool with provided configuration.

        Args:
            config: DatabaseConfig instance containing connection parameters

        Raises:
            ConnectionError: If connection pool initialization fails
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        try:
            # Initialize connection pool with configured parameters
            self.pool = SimpleConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
            )
            self.logger.info("Successfully initiated database connection pool.")
        except psycopg2.Error as e:
            self.logger.error(f"Failed to initiate database connection pool: {str(e)}")
            raise ConnectionError(f"Database connection failed: {str(e)}")

    @contextmanager
    def get_connection(self):
        """
        Context manager for safely acquiring and releasing database connections.

        Yields:
            psycopg2.connection: Database connection from the pool

        Raises:
            ConnectionError: If connection acquisition fails
        """
        connection = None
        try:
            connection = self.pool.getconn()
            yield connection
        except psycopg2.Error as e:
            self.logger.error(f"Failed to get database connection: {str(e)}")
            raise ConnectionError(f"Failed to get database connection: {str(e)}")
        finally:
            # Ensure connection is always returned to pool
            if connection:
                self.pool.putconn(connection)

    def execute_query(self, query: str, params: Optional[tuple] = None) -> Any:
        """
        Execute a SELECT query and return results.

        Args:
            query: SQL query string
            params: Optional tuple of query parameters

        Returns:
            Query results as a list of dictionaries

        Raises:
            QueryError: If query execution fails
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                try:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                except psycopg2.Error as e:
                    self.logger.error(f"Failed to execute query: {str(e)}")
                    raise QueryError(f"Failed to execute query: {str(e)}")

    def execute_modification(self, query: str, params: Optional[tuple] = None) -> int:
        """
        Execute a modification query (INSERT, UPDATE, DELETE) and return affected rows.

        Args:
            query: SQL query string
            params: Optional tuple of query parameters

        Returns:
            Number of affected rows

        Raises:
            QueryError: If query execution fails
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.rowcount
                except psycopg2.Error as e:
                    self.logger.error(f"Failed to execute modification: {str(e)}")
                    raise QueryError(f"Failed to execute modification: {str(e)}")

    def __enter__(self):
        """Context manager entry point."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager exit point - ensures all connections are closed.

        Properly closes all connections in the pool when the context is exited,
        preventing connection leaks.
        """
        if self.pool:
            self.pool.closeall()
            self.logger.info("Closed all database connections.")
