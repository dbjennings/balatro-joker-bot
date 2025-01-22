import os
import logging
import csv

from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

from src.domain.models import JokerCard
from database.base import DatabaseConfig
from database.balatro_repository import BalatroRepository


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("import_jokers.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class CSVImporter:

    def __init__(self, config: DatabaseConfig, csv_path: Path):
        self.repository = BalatroRepository(config)
        self.csv_path = csv_path

        self.total_records = 0
        self.successful_imports = 0
        self.failed_imports = 0
        self.validation_errors = []

    def read_csv(self) -> List[Dict]:

        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        try:
            with open(self.csv_path, "r") as csv_file:
                reader = csv.DictReader(csv_file, delimiter="|")

                required_fields = ["name", "effect", "rarity", "cost", "availability"]
                missing_fields = [
                    field for field in required_fields if field not in reader.fieldnames
                ]
                if missing_fields:
                    raise ValueError(
                        f"Missing required fields: {', '.join(missing_fields)}"
                    )

                return list(reader)

        except csv.Error as e:
            raise ValueError(f"Error reading CSV file: {e}")

    def process_record(self, record: Dict) -> Optional[JokerCard]:
        try:
            cleaned_record = {k: v.strip() for k, v in record.items()}

            joker = JokerCard.from_dict(cleaned_record)
            if not joker.validate():
                self.validation_errors.append(
                    f"Invalid data for joker: {cleaned_record['name']}"
                )
                return None

            return joker

        except ValueError as e:
            self.validation_errors.append(
                f"Error processing record {record.get('name', 'Unknown')}: {str(e)}"
            )
            return None

    def import_data(self) -> None:
        try:
            records = self.read_csv()
            self.total_records = len(records)

            for record in records:
                try:
                    joker = self.process_record(record)
                    if joker:
                        self.repository.add_joker(joker)
                        self.successful_imports += 1
                    else:
                        self.failed_imports += 1
                except Exception as e:
                    self.failed_imports += 1
                    logger.error(
                        f"Error importing record {record.get('name', 'Unknown')}: {str(e)}"
                    )

            self._log_import_summary()

        except Exception as e:
            logger.error(f"Import process failed: {str(e)}")
            raise

    def _log_import_summary(self) -> None:
        summary = [
            "=== IMPORT PROCESS SUMMARY ===",
            f"Total records processed: {self.total_records}",
            f"Successful imports: {self.successful_imports}",
            f"Failed imports: {self.failed_imports}",
        ]

        if self.validation_errors:
            summary.extend(["\nValidation errors:", *self.validation_errors])

        logger.info("\n".join(summary))


def main():
    try:
        load_dotenv()

        db_config = DatabaseConfig.from_env()
        logger.info("Database configuration loaded successfully")

        csv_path = Path(os.environ["JOKER_CSV_PATH"])
        logger.info(f"CSV file path: {csv_path}")

        importer = CSVImporter(db_config, csv_path)
        importer.import_data()

    except Exception as e:
        logger.error(f"Main process failed: {str(e)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
