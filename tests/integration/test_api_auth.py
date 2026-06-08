from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.domain.models import User, UserRole


class TestAuthRegister:
    async def test_register_success(self, async_client: AsyncClient):
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepassword123",
        }
        with patch.object(
            type(async_client._transport.app),
            "dependency_overrides",
            {},
        ):
            with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = None
                with patch("src.api.routes.auth._get_user_by_email", new_callable=AsyncMock) as mock_get_email:
                    mock_get_email.return_value = None
                    with patch("src.api.routes.auth.db_manager.session") as mock_session_ctx:
                        mock_session = AsyncMock()
                        mock_session_ctx.return_value.__aenter__.return_value = mock_session
                        response = await async_client.post(
                            "/api/v1/auth/register",
                            json=payload,
                        )
                        assert response.status_code == 201
                        data = response.json()
                        assert "access_token" in data
                        assert "refresh_token" in data
                        assert data["token_type"] == "bearer"
                        assert "expires_in" in data

    async def test_register_duplicate_username(self, async_client: AsyncClient):
        payload = {
            "username": "existinguser",
            "email": "new@example.com",
            "password": "securepassword123",
        }
        with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = User(
                username="existinguser",
                email="existing@example.com",
                hashed_password="hash",
            )
            response = await async_client.post(
                "/api/v1/auth/register",
                json=payload,
            )
            assert response.status_code == 422
            data = response.json()
            assert "Username already taken" in data["error"]["message"]

    async def test_register_duplicate_email(self, async_client: AsyncClient):
        payload = {
            "username": "uniqueuser",
            "email": "taken@example.com",
            "password": "securepassword123",
        }
        with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None
            with patch("src.api.routes.auth._get_user_by_email", new_callable=AsyncMock) as mock_get_email:
                mock_get_email.return_value = User(
                    username="other",
                    email="taken@example.com",
                    hashed_password="hash",
                )
                response = await async_client.post(
                    "/api/v1/auth/register",
                    json=payload,
                )
                assert response.status_code == 422
                assert "Email already registered" in response.json()["error"]["message"]

    async def test_register_short_password(self, async_client: AsyncClient):
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "short",
        }
        response = await async_client.post(
            "/api/v1/auth/register",
            json=payload,
        )
        assert response.status_code == 422

    async def test_register_invalid_username(self, async_client: AsyncClient):
        payload = {
            "username": "user with spaces!",
            "email": "test@example.com",
            "password": "securepassword123",
        }
        response = await async_client.post(
            "/api/v1/auth/register",
            json=payload,
        )
        assert response.status_code == 422


class TestAuthLogin:
    async def test_login_success(self, async_client: AsyncClient):
        payload = {
            "username": "loginuser",
            "password": "correctpassword123",
        }
        hashed = "$2b$12$abcdefghijklmnopqrstuvabcdefghijklmnopqrstuv"
        with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = User(
                username="loginuser",
                email="login@example.com",
                hashed_password=hashed,
                role=UserRole.ANALYST,
                is_active=True,
            )
            with patch("src.api.routes.auth._verify_password", return_value=True):
                response = await async_client.post(
                    "/api/v1/auth/login",
                    json=payload,
                )
                assert response.status_code == 200
                data = response.json()
                assert "access_token" in data
                assert "refresh_token" in data

    async def test_login_wrong_password(self, async_client: AsyncClient):
        payload = {
            "username": "loginuser",
            "password": "wrongpassword",
        }
        hashed = "$2b$12$abcdefghijklmnopqrstuvabcdefghijklmnopqrstuv"
        with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = User(
                username="loginuser",
                email="login@example.com",
                hashed_password=hashed,
                is_active=True,
            )
            with patch("src.api.routes.auth._verify_password", return_value=False):
                response = await async_client.post(
                    "/api/v1/auth/login",
                    json=payload,
                )
                assert response.status_code == 401

    async def test_login_user_not_found(self, async_client: AsyncClient):
        payload = {
            "username": "unknown",
            "password": "somepassword",
        }
        with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            response = await async_client.post(
                "/api/v1/auth/login",
                json=payload,
            )
            assert response.status_code == 401

    async def test_login_inactive_user(self, async_client: AsyncClient):
        payload = {
            "username": "inactive",
            "password": "password123",
        }
        with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = User(
                username="inactive",
                email="inactive@example.com",
                hashed_password="hash",
                is_active=False,
            )
            response = await async_client.post(
                "/api/v1/auth/login",
                json=payload,
            )
            assert response.status_code == 401

    async def test_login_missing_fields(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "test"},
        )
        assert response.status_code == 422

    async def test_login_empty_body(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={},
        )
        assert response.status_code == 422


class TestAuthRefresh:
    async def test_refresh_success(self, async_client: AsyncClient):
        import jwt as pyjwt
        from src.config import config
        now = datetime.utcnow()
        refresh_payload = {
            "sub": "user-id",
            "iat": now,
            "exp": now + timedelta(days=7),
            "type": "refresh",
        }
        refresh_token = pyjwt.encode(refresh_payload, config.auth.jwt_secret, algorithm=config.auth.jwt_algorithm)

        with patch("src.api.routes.auth.db_manager.session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_row = MagicMock()
            mock_row.user_id = "user-id"
            mock_row.username = "refresheduser"
            mock_row.email = "refresh@test.com"
            mock_row.hashed_password = "hash"
            mock_row.role = "analyst"
            mock_row.is_active = True
            mock_row.created_at = now
            mock_row.updated_at = now
            mock_result.scalar_one_or_none.return_value = mock_row
            mock_session.execute.return_value = mock_result

            response = await async_client.post(
                "/api/v1/auth/refresh",
                headers={"X-Refresh-Token": refresh_token},
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data

    async def test_refresh_invalid_token(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/auth/refresh",
            headers={"X-Refresh-Token": "invalid-token"},
        )
        assert response.status_code == 401

    async def test_refresh_expired_token(self, async_client: AsyncClient):
        import jwt as pyjwt
        from src.config import config
        now = datetime.utcnow()
        refresh_payload = {
            "sub": "user-id",
            "iat": now - timedelta(days=30),
            "exp": now - timedelta(days=1),
            "type": "refresh",
        }
        expired_token = pyjwt.encode(refresh_payload, config.auth.jwt_secret, algorithm=config.auth.jwt_algorithm)
        response = await async_client.post(
            "/api/v1/auth/refresh",
            headers={"X-Refresh-Token": expired_token},
        )
        assert response.status_code == 401

    async def test_refresh_missing_header(self, async_client: AsyncClient):
        response = await async_client.post("/api/v1/auth/refresh")
        assert response.status_code == 401


class TestAuthMe:
    async def test_get_me_success(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        with patch("src.api.routes.auth.db_manager.session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_row = MagicMock()
            mock_row.user_id = "test-user-id"
            mock_row.username = "testuser"
            mock_row.email = "test@example.com"
            mock_row.role = "analyst"
            mock_row.is_active = True
            mock_result.scalar_one_or_none.return_value = mock_row
            mock_session.execute.return_value = mock_result

            response = await async_client.get(
                "/api/v1/auth/me",
                headers=auth_header,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "testuser"
            assert data["role"] == "analyst"

    async def test_get_me_unauthorized(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/auth/me")
        assert response.status_code == 401


from datetime import datetime, timedelta
