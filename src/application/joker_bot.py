import logging

from dotenv import load_dotenv
from praw.models import Comment
from prawcore.exceptions import Forbidden

from application.config import JokerBotConfig
from domain.interfaces import JokerRepository
from database.base import DatabaseConfig
from database.balatro_repository import BalatroRepository
from services.joker_service import JokerService
from services.reddit_service import RedditConfig, RedditService
from processors.comment_processor import CommentProcessor, CommentProcessorConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("processors.log"), logging.StreamHandler()],
)


class RedditJokerBot:

    def __init__(self, config: JokerBotConfig, repository: JokerRepository):
        self.config = config
        self.repository = repository
        self.logger = logging.getLogger(__name__)

        # Service declarations
        self.joker_service = None
        self.reddit_service = None
        self.comment_processor = None

        self._initialize_joker_service()
        self._initialize_reddit_service()
        self._initialize_comment_processor()

    def _initialize_joker_service(self) -> None:
        try:
            self.joker_service = JokerService(self.repository)
            self.logger.info("JokerService successfully initiated.")
        except Exception as e:
            self.logger.error(f"JokerService initialization failed: {str(e)}")
            raise e

    def _initialize_reddit_service(self) -> None:
        try:
            self.reddit_service = RedditService(self.config.reddit_service_config)
            self.logger.info("RedditService successfully initialized.")
        except Exception as e:
            self.logger.error(f"RedditService initialization failed: {str(e)}")
            raise e

    def _initialize_comment_processor(self) -> None:
        try:
            self.comment_processor = CommentProcessor(
                self.config.comment_processor_config
            )
            self.logger.info("CommentProcessor successfully initialized.")
        except Exception as e:
            self.logger.error(f"CommentProcessor initialization failed: {str(e)}")
            raise e

    def _signature_line(self):
        return f"This comment brought to you by your friendly, neighborhood u/{self.config.reddit_service_config.username}"

    def run(self):
        try:
            for comment in self.reddit_service.get_comment_stream():
                matches = self.comment_processor.extract_match_names(comment)
                if matches:
                    self.logger.debug(
                        f"Matches found in {comment.id}: {', '.join(matches)}"
                    )

                    reply = self.joker_service.format_multiple_jokers(matches)
                    reply += self._signature_line()

                    self.reddit_service.reply_to_comment(comment, reply)
                    self.logger.info(f"Comment {comment.id} succesfully replied to.")
        except Exception as e:
            self.logger.error(
                f"Error in the comment stream for r/{self.config.reddit_service_config.subreddit}: {str(e)}"
            )


def main():
    load_dotenv()

    database_config = DatabaseConfig.from_env()
    repository = BalatroRepository(database_config)

    reddit_config = RedditConfig.from_env()

    match_phrases = [name.lower() for name in repository.get_joker_name_list()]
    comment_processor_config = CommentProcessorConfig(
        match_phrases=match_phrases, bot_username=reddit_config.username
    )

    bot_config = JokerBotConfig(
        comment_processor_config=comment_processor_config,
        reddit_service_config=reddit_config,
    )
    joker_bot = RedditJokerBot(bot_config, repository)

    joker_bot.run()


if __name__ == "__main__":
    main()
