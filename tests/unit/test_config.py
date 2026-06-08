from __future__ import annotations

import os
from unittest.mock import patch

from src.config import (
    AppConfig,
    AuthConfig,
    CORSConfig,
    DatabaseConfig,
    KafkaConfig,
    LogLevel,
    MetricsConfig,
    RateLimitConfig,
    RedisConfig,
    RetentionConfig,
    SamplingConfig,
    TracingConfig,
)


class TestConfigDefaults:
    def test_app_config_defaults(self):
        config = AppConfig()
        assert config.service_name == "real-time-analytics-pipeline"
        assert config.version == "1.0.0"
        assert config.debug is True
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.workers == 4
        assert config.max_event_size_bytes == 65536
        assert config.batch_size == 100
        assert config.flush_interval_seconds == 1.0

    def test_database_config_defaults(self):
        db = DatabaseConfig()
        assert db.host == "localhost"
        assert db.port == 5432
        assert db.name == "analytics"
        assert db.min_connections == 5
        assert db.max_connections == 20
        assert db.pool_size == 10
        assert db.echo is False

    def test_database_dsn(self):
        db = DatabaseConfig()
        assert "postgresql+asyncpg://" in db.dsn
        assert db.user in db.dsn

    def test_database_synchronous_dsn(self):
        db = DatabaseConfig()
        assert "postgresql://" in db.synchronous_dsn
        assert "asyncpg" not in db.synchronous_dsn

    def test_redis_config_defaults(self):
        rc = RedisConfig()
        assert rc.host == "localhost"
        assert rc.port == 6379
        assert rc.db == 0
        assert rc.password is None
        assert rc.ssl is False
        assert "redis://" in rc.dsn

    def test_redis_dsn_with_password(self):
        rc = RedisConfig(password="secret")
        assert ":secret@" in rc.dsn

    def test_kafka_config_defaults(self):
        kc = KafkaConfig()
        assert kc.bootstrap_servers == "localhost:9092"
        assert kc.topic == "analytics-events"
        assert kc.partitions == 6
        assert kc.replication_factor == 3
        assert kc.max_poll_records == 500

    def test_auth_config_defaults(self):
        ac = AuthConfig()
        assert ac.jwt_algorithm == "HS256"
        assert ac.access_token_expire_minutes == 15
        assert ac.refresh_token_expire_days == 7
        assert ac.bcrypt_rounds == 12

    def test_rate_limit_config_defaults(self):
        rl = RateLimitConfig()
        assert rl.enabled is True
        assert rl.requests_per_minute == 60
        assert rl.burst_size == 100

    def test_retention_config_defaults(self):
        rc = RetentionConfig()
        assert rc.raw_events_days == 30
        assert rc.aggregated_hourly_days == 90
        assert rc.aggregated_daily_days == 365
        assert rc.checkpoint_interval == 3600

    def test_sampling_config_defaults(self):
        sc = SamplingConfig()
        assert sc.default_sample_rate == 1.0
        assert sc.high_volume_threshold == 10000
        assert sc.high_volume_sample_rate == 0.1

    def test_cors_config_defaults(self):
        cc = CORSConfig()
        assert "http://localhost:3000" in cc.allowed_origins
        assert cc.allow_credentials is True

    def test_tracing_config_defaults(self):
        tc = TracingConfig()
        assert tc.enabled is True
        assert tc.service_name == "analytics-pipeline"
        assert tc.sample_rate == 0.1

    def test_metrics_config_defaults(self):
        mc = MetricsConfig()
        assert mc.enabled is True
        assert mc.port == 9090

    def test_environment_default(self):
        config = AppConfig()
        assert config.environment.value == "development"

    def test_log_level_default(self):
        config = AppConfig()
        assert config.log_level == LogLevel.DEBUG

    def test_queue_provider_default(self):
        config = AppConfig()
        assert config.queue_provider.value == "redis_streams"


class TestConfigConstruction:
    def test_database_custom(self):
        db = DatabaseConfig(
            host="db.example.com",
            port=15432,
            name="test_db",
            user="test_user",
            password="test_pass",
        )
        assert db.host == "db.example.com"
        assert db.port == 15432
        assert db.name == "test_db"
        assert db.user == "test_user"
        assert db.password == "test_pass"

    def test_app_custom(self):
        config = AppConfig(
            host="127.0.0.1",
            port=9000,
            workers=8,
            batch_size=200,
            debug=False,
        )
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.workers == 8
        assert config.batch_size == 200
        assert config.debug is False

    def test_retention_custom(self):
        rc = RetentionConfig(
            raw_events_days=7,
            aggregated_hourly_days=14,
            aggregated_daily_days=60,
        )
        assert rc.raw_events_days == 7
        assert rc.aggregated_hourly_days == 14
        assert rc.aggregated_daily_days == 60

    def test_sampling_custom(self):
        sc = SamplingConfig(
            default_sample_rate=0.5,
            high_volume_threshold=5000,
            high_volume_sample_rate=0.05,
        )
        assert sc.default_sample_rate == 0.5
        assert sc.high_volume_threshold == 5000
        assert sc.high_volume_sample_rate == 0.05

    def test_auth_custom(self):
        ac = AuthConfig(
            jwt_secret="my-custom-secret",
            access_token_expire_minutes=30,
            refresh_token_expire_days=14,
        )
        assert ac.jwt_secret == "my-custom-secret"
        assert ac.access_token_expire_minutes == 30
        assert ac.refresh_token_expire_days == 14

    def test_cors_custom(self):
        cc = CORSConfig(allowed_origins=["https://app.example.com", "https://admin.example.com"])
        assert "https://app.example.com" in cc.allowed_origins
        assert "https://admin.example.com" in cc.allowed_origins

    def test_redis_custom(self):
        rc = RedisConfig(
            host="redis.example.com",
            port=16379,
            db=5,
            password="r3d1s",
            ssl=True,
        )
        assert rc.host == "redis.example.com"
        assert rc.port == 16379
        assert rc.db == 5
        assert rc.password == "r3d1s"
        assert rc.ssl is True

    def test_redis_dsn_with_password_custom(self):
        rc = RedisConfig(password="hunter2")
        assert ":hunter2@" in rc.dsn

    def test_kafka_custom(self):
        kc = KafkaConfig(
            bootstrap_servers="kafka1:9092,kafka2:9092",
            topic="custom-events",
            partitions=12,
        )
        assert kc.bootstrap_servers == "kafka1:9092,kafka2:9092"
        assert kc.topic == "custom-events"
        assert kc.partitions == 12

    def test_log_level_custom(self):
        config = AppConfig(log_level=LogLevel.INFO)
        assert config.log_level == LogLevel.INFO

    def test_metrics_custom(self):
        mc = MetricsConfig(enabled=False, port=9091)
        assert mc.enabled is False
        assert mc.port == 9091

    def test_tracing_custom(self):
        tc = TracingConfig(enabled=False, service_name="custom-analytics")
        assert tc.enabled is False
        assert tc.service_name == "custom-analytics"

    def test_rate_limit_custom(self):
        rl = RateLimitConfig(enabled=False, requests_per_minute=120)
        assert rl.enabled is False
        assert rl.requests_per_minute == 120

    def test_app_config_accepts_sub_configs(self):
        rc = RetentionConfig(raw_events_days=14)
        sc = SamplingConfig(default_sample_rate=0.75)
        config = AppConfig(retention=rc, sampling=sc)
        assert config.retention.raw_events_days == 14
        assert config.sampling.default_sample_rate == 0.75

    def test_environment_custom(self):
        from src.config import Environment
        config = AppConfig(environment=Environment.PRODUCTION)
        assert config.environment.value == "production"

    def test_queue_provider_custom(self):
        from src.config import QueueProvider
        config = AppConfig(queue_provider=QueueProvider.KAFKA)
        assert config.queue_provider.value == "kafka"

    def test_database_provider_custom(self):
        from src.config import DatabaseProvider
        db = DatabaseConfig(provider=DatabaseProvider.POSTGRESQL)
        assert db.provider.value == "postgresql"
