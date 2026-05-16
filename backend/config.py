import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_embedding_model: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    openai_llm_model: str = os.getenv("OPENAI_LLM_MODEL", "gpt-4o")
    neo4j_uri: str = os.getenv("NEO4J_URI", "")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    embedding_dimensions: int = 1536
    salesforce_client_id: str = os.getenv("SALESFORCE_CLIENT_ID", "")
    salesforce_client_secret: str = os.getenv("SALESFORCE_CLIENT_SECRET", "")
    salesforce_instance_url: str = os.getenv("SALESFORCE_INSTANCE_URL", "")
    salesforce_username: str = os.getenv("SALESFORCE_USERNAME", "")
    salesforce_password: str = os.getenv("SALESFORCE_PASSWORD", "")
    salesforce_security_token: str = os.getenv("SALESFORCE_SECURITY_TOKEN", "")
    salesforce_poll_interval: int = int(os.getenv("SALESFORCE_POLL_INTERVAL", "10"))
    webex_bot_token: str = os.getenv("WEBEX_BOT_TOKEN", "")
    webex_room_id: str = os.getenv("WEBEX_ROOM_ID", "")
    reply_poll_interval: int = int(os.getenv("REPLY_POLL_INTERVAL", "60"))
    self_learning_enabled: bool = (
        os.getenv("SELF_LEARNING_ENABLED", "true").lower() == "true"
    )


settings = Settings()
