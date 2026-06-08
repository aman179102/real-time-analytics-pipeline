#!/bin/bash
set -euo pipefail

DB_NAME="${POSTGRES_DB:-analytics}"
DB_USER="${POSTGRES_USER:-analytics}"
DB_PASS="${POSTGRES_PASSWORD:-analytics}"

echo "=== Initializing database: $DB_NAME ==="

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
EOSQL

echo "=== Extensions installed ==="

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
    CREATE TABLE IF NOT EXISTS users (
        user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        username VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'viewer',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        deleted_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS events (
        event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        event_type VARCHAR(50) NOT NULL,
        source VARCHAR(255) NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}',
        user_id UUID REFERENCES users(user_id),
        session_id VARCHAR(255),
        ip_address VARCHAR(45),
        user_agent TEXT,
        status VARCHAR(20) NOT NULL DEFAULT 'received',
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    SELECT create_hypertable('events', 'timestamp', if_not_exists => TRUE);

    CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_events_source ON events (source, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_events_session_id ON events (session_id, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_events_status ON events (status, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at DESC);

    CREATE TABLE IF NOT EXISTS aggregated_metrics (
        metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        metric_name VARCHAR(255) NOT NULL,
        window VARCHAR(20) NOT NULL,
        window_start TIMESTAMPTZ NOT NULL,
        window_end TIMESTAMPTZ NOT NULL,
        value DOUBLE PRECISION NOT NULL DEFAULT 0,
        count BIGINT NOT NULL DEFAULT 0,
        dimensions JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    SELECT create_hypertable('aggregated_metrics', 'window_start', if_not_exists => TRUE);

    CREATE INDEX IF NOT EXISTS idx_agg_metrics_name ON aggregated_metrics (metric_name, window, window_start DESC);
    CREATE INDEX IF NOT EXISTS idx_agg_metrics_window ON aggregated_metrics (window, window_start DESC);
    CREATE INDEX IF NOT EXISTS idx_agg_metrics_dimensions ON aggregated_metrics USING GIN (dimensions);

    CREATE TABLE IF NOT EXISTS dashboards (
        dashboard_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(255) NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        owner_id UUID REFERENCES users(user_id),
        is_public BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        deleted_at TIMESTAMPTZ
    );

    CREATE INDEX IF NOT EXISTS idx_dashboards_owner ON dashboards (owner_id, deleted_at);
    CREATE INDEX IF NOT EXISTS idx_dashboards_public ON dashboards (is_public, deleted_at);

    CREATE TABLE IF NOT EXISTS dashboard_widgets (
        widget_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        dashboard_id UUID NOT NULL REFERENCES dashboards(dashboard_id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        widget_type VARCHAR(50) NOT NULL,
        metric_name VARCHAR(255) NOT NULL,
        config JSONB NOT NULL DEFAULT '{}',
        position INT NOT NULL DEFAULT 0,
        width INT NOT NULL DEFAULT 6,
        height INT NOT NULL DEFAULT 4,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_widgets_dashboard ON dashboard_widgets (dashboard_id, position);

    CREATE TABLE IF NOT EXISTS refresh_tokens (
        token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        token_hash VARCHAR(255) NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        revoked_at TIMESTAMPTZ
    );

    CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens (user_id, revoked_at);

    CREATE TABLE IF NOT EXISTS retention_log (
        record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        table_name VARCHAR(100) NOT NULL,
        partition_name VARCHAR(255) NOT NULL,
        retention_date TIMESTAMPTZ NOT NULL,
        deleted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(50) PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        description TEXT
    );
EOSQL

echo "=== Schema created successfully ==="

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
    INSERT INTO schema_migrations (version, description) VALUES
        ('001', 'Initial schema with TimescaleDB hypertables')
    ON CONFLICT (version) DO NOTHING;
EOSQL

echo "=== Database initialization complete ==="
