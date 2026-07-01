from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "netpulse"
    postgres_user: str = "netpulse"
    postgres_password: str = "netpulse_dev"

    # S3 / MinIO — set S3_ENDPOINT_URL for local MinIO; omit in cloud for real AWS S3
    s3_endpoint_url: Optional[str] = None
    s3_bucket: str = "netpulse-lake"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_default_region: str = "us-east-1"

    # OpenCelliD (cloud DAG 0) — set in .env.cloud; never commit
    opencellid_api_key: Optional[str] = None

    # Local data paths
    opencellid_data_path: Path = Path("./data/opencellid")
    boundaries_data_path: Path = Path("./data/boundaries")

    # Pipeline constants
    # 0 = seed all towers in the OpenCelliD Indonesia slice; set e.g. 100 for demo
    tower_sample_size: int = 0
    random_seed: int = 42
    backfill_days: int = 35
    subscriber_count: int = 50000

    @property
    def tower_sample_limit(self) -> int | None:
        """None means use all filtered towers; otherwise cap at this count."""
        return None if self.tower_sample_size <= 0 else self.tower_sample_size

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
