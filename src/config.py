from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class QueueProvider(Enum):
    REDIS_STREAMS = "redis_streams"
    KAFKA = "kafka"


class DatabaseProvider(Enum):
    TIMESCALEDB = "timescaledb"
    CLICKHOUSE = "clickhouse"
    POSTGRESQL = "postgresql"


@dataclass
class DatabaseConfig:
    provider: DatabaseProvider = DatabaseProvider(
        os.getenv("DATABASE_PROVIDER", "timescaledb")
    )
    host: str = os.getenv("DATABASE_HOST", "localhost")
    port: int = int(os.getenv("DATABASE_PORT", "5432"))
    name: str = os.getenv("DATABASE_NAME", "analytics")
    user: str = os.getenv("DATABASE_USER", "analytics")
    password: str = os.getenv("DATABASE_PASSWORD", "analytics")
    min_connections: int = int(os.getenv("DATABASE_MIN_CONNECTIONS", "5"))
    max_connections: int = int(os.getenv("DATABASE_MAX_CONNECTIONS", "20"))
    pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    pool_overflow: int = int(os.getenv("DATABASE_POOL_OVERFLOW", "20"))
    pool_timeout: int = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
    echo: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def synchronous_dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    db: int = int(os.getenv("REDIS_DB", "0"))
    password: Optional[str] = os.getenv("REDIS_PASSWORD") or None
    stream_maxlen: int = int(os.getenv("REDIS_STREAM_MAXLEN", "100000"))
    consumer_group: str = os.getenv("REDIS_CONSUMER_GROUP", "analytics-group")
    ssl: bool = os.getenv("REDIS_SSL", "false").lower() == "true"

    @property
    def dsn(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        ssl_suffix = "?ssl=true" if self.ssl else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}{ssl_suffix}"


@dataclass
class KafkaConfig:
    bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )
    topic: str = os.getenv("KAFKA_TOPIC", "analytics-events")
    consumer_group: str = os.getenv(
        "KAFKA_CONSUMER_GROUP", "analytics-consumer"
    )
    partitions: int = int(os.getenv("KAFKA_PARTITIONS", "6"))
    replication_factor: int = int(os.getenv("KAFKA_REPLICATION_FACTOR", "3"))
    max_poll_records: int = int(os.getenv("KAFKA_MAX_POLL_RECORDS", "500"))
    session_timeout_ms: int = int(
        os.getenv("KAFKA_SESSION_TIMEOUT_MS", "30000")
    )


@dataclass
class AuthConfig:
    jwt_secret: str = os.getenv("JWT_SECRET", "super-secret-key-change-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    refresh_token_expire_days: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )
    bcrypt_rounds: int = int(os.getenv("BCRYPT_ROUNDS", "12"))


@dataclass
class RateLimitConfig:
    enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    requests_per_minute: int = int(
        os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60")
    )
    burst_size: int = int(os.getenv("RATE_LIMIT_BURST_SIZE", "100"))


@dataclass
class RetentionConfig:
    raw_events_days: int = int(os.getenv("RETENTION_RAW_EVENTS_DAYS", "30"))
    aggregated_hourly_days: int = int(
        os.getenv("RETENTION_AGGREGATED_HOURLY_DAYS", "90")
    )
    aggregated_daily_days: int = int(
        os.getenv("RETENTION_AGGREGATED_DAILY_DAYS", "365")
    )
    checkpoint_interval: int = int(
        os.getenv("RETENTION_CHECKPOINT_INTERVAL", "3600")
    )


@dataclass
class SamplingConfig:
    default_sample_rate: float = float(
        os.getenv("SAMPLING_DEFAULT_RATE", "1.0")
    )
    high_volume_threshold: int = int(
        os.getenv("SAMPLING_HIGH_VOLUME_THRESHOLD", "10000")
    )
    high_volume_sample_rate: float = float(
        os.getenv("SAMPLING_HIGH_VOLUME_RATE", "0.1")
    )


@dataclass
class CORSConfig:
    allowed_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
        ).split(",")
    )
    allow_credentials: bool = (
        os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    )
    allow_methods: list[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,PATCH,OPTIONS"
        ).split(",")
    )
    allow_headers: list[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_ALLOW_HEADERS", "*"
        ).split(",")
    )


@dataclass
class TracingConfig:
    enabled: bool = os.getenv("TRACING_ENABLED", "true").lower() == "true"
    service_name: str = os.getenv("TRACING_SERVICE_NAME", "analytics-pipeline")
    exporter_endpoint: str = os.getenv(
        "TRACING_EXPORTER_ENDPOINT", "http://localhost:4318/v1/traces"
    )
    sample_rate: float = float(os.getenv("TRACING_SAMPLE_RATE", "0.1"))


@dataclass
class MetricsConfig:
    enabled: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    port: int = int(os.getenv("METRICS_PORT", "9090"))


@dataclass
class AppConfig:
    environment: Environment = Environment(
        os.getenv("ENVIRONMENT", "development")
    )
    log_level: LogLevel = LogLevel(os.getenv("LOG_LEVEL", "DEBUG"))
    service_name: str = "real-time-analytics-pipeline"
    version: str = os.getenv("APP_VERSION", "1.0.0")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    workers: int = int(os.getenv("WORKERS", "4"))
    queue_provider: QueueProvider = QueueProvider(
        os.getenv("QUEUE_PROVIDER", "redis_streams")
    )
    max_event_size_bytes: int = int(
        os.getenv("MAX_EVENT_SIZE_BYTES", "65536")
    )
    max_request_size: int = int(os.getenv("MAX_REQUEST_SIZE", str(10 * 1024 * 1024)))
    content_security_policy: str = os.getenv(
        "CONTENT_SECURITY_POLICY", "default-src 'self'"
    )
    batch_size: int = int(os.getenv("BATCH_SIZE", "100"))
    flush_interval_seconds: float = float(
        os.getenv("FLUSH_INTERVAL_SECONDS", "1.0")
    )
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)


config = AppConfig()
