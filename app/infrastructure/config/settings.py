from pydantic import AmqpDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rabbitmq_url: AmqpDsn
    rabbitmq_prefetch_count: int = 10
    rabbitmq_reconnect_delay: float = 5.0
    rabbitmq_max_retries: int = 5

    app_name: str = "communication"
    log_level: str = "INFO"

    database_url: str = ""

    http_host: str = "0.0.0.0"
    http_port: int = 80

    meta_verify_token: str = ""
    meta_access_token: str = ""
    whatsapp_phone_number_id: str = ""

    aws_s3_bucket: str = ""
    aws_s3_region: str = "us-east-1"
    aws_s3_presign_expires: int = 3600
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
