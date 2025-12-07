import os
from typing import Optional

from loguru import logger
from post_orm import Database


class DatabaseManager:
    """
    Singleton database connection manager for the project.
    Ensures only one database connection instance exists across the application.
    """

    _instance: Optional["DatabaseManager"] = None
    _db: Optional[Database] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the database connection if not already initialized."""
        if self._db is None:
            self._initialize_connection()

    def _initialize_connection(self):
        """Create the database connection using environment variables."""
        try:
            self._db = Database(
                database=os.environ["POSTGRES_DB"],
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
                host=os.environ.get("POSTGRES_HOST", "localhost"),
                port=os.environ["POSTGRES_PORT"],
            )
            logger.info("Database connection initialized successfully")
        except KeyError as e:
            logger.error(f"Missing required environment variable: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise

    @property
    def db(self) -> Database:
        """Get the database connection instance."""
        if self._db is None:
            self._initialize_connection()
        return self._db

    def close(self):
        """Close the database connection."""
        if self._db is not None:
            try:
                # Add cleanup logic if post_orm provides a close method
                logger.info("Database connection closed")
                self._db = None
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
                raise

    def reset(self):
        """Reset the connection (useful for testing or reconnection)."""
        self.close()
        self._initialize_connection()


# Singleton instance
_db_manager = DatabaseManager()


def get_db() -> Database:
    """
    Get the singleton database connection instance.

    Returns:
        Database: The database connection instance

    Example:
        from db.db import get_db

        db = get_db()
        # Use db for queries
    """
    return _db_manager.db


def close_db():
    """
    Close the database connection.
    Should be called when the application shuts down.
    """
    _db_manager.close()


def reset_db():
    """
    Reset the database connection.
    Useful for testing or when connection needs to be refreshed.
    """
    _db_manager.reset()


# Backward compatibility: expose db directly for existing code
db = get_db()