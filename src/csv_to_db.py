"""
CSV to Database Import Script for Balatro Joker Cards

This module provides functionality to import joker card data from a CSV file
into the Balatro game database. It processes the CSV file row by row and
inserts each joker card entry using the BalatroDB interface.

Environment Variables Required:
    JOKERS_DATA_PATH: Path to the CSV file containing joker data

Dependencies:
    - src.balatrodb: Custom database interface for Balatro
    - csv: CSV file processing
    - os: Operating system interface
    - python-dotenv: Environment variable management

Expected CSV Format:
    Column 1: Joker name
    Column 2: Effect description
    Column 3: Rarity level
    Column 4: Cost value
    Column 5: Availability status
"""

from src.balatrodb import BalatroDB
import csv
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def process_csv(file_path: str):
    """
    Process a CSV file containing joker card data and insert entries into database.

    Reads the CSV file row by row, processes each joker card entry, and inserts
    it into the database using the BalatroDB interface.

    Args:
        file_path: Path to the CSV file containing joker data

    Raises:
        Exception: If file processing or database operations fail
    """
    try:
        with BalatroDB() as db:
            with open(file_path) as file:
                joker_reader = csv.reader(file, delimiter=",")
                for row in joker_reader:
                    db.insert_joker(
                        name=row[0].strip(),
                        effect=row[1].strip(),
                        rarity=row[2].strip(),
                        cost=row[3].strip(),
                        availability=row[4].strip(),
                    )
    except Exception as e:
        raise e


def main():
    """
    Main entry point for the CSV import script.
    """
    try:
        process_csv(os.environ["JOKERS_DATA_PATH"])
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
