from dataclasses import dataclass
from processors.comment_processor import CommentProcessorConfig
from services.reddit_service import RedditConfig


@dataclass
class JokerBotConfig:
    comment_processor_config: CommentProcessorConfig
    reddit_service_config: RedditConfig
