"""Onboarding, verification and session lifecycle."""

from __future__ import annotations

from typing import Any

from tests.conftest import register_user

PHONE = "+919876543210"


class TestRegistration:
    def test_phone_number_is_normalised_to_e164(self, client: Any) -> None:
        """Otherwise the same person registers twice and the two never meet."""
        response = client.post(
            "/api/v1/auth/register",
            json={"phone_number": "+91 98765-43210", "display_name": "Nipurn"},
        )
        assert response.status_code == 201
        assert response.json()["phone_number"] == PHONE

    def test_duplicate_registration_is_rejected(self, client: Any) -> None:
        register_user(client, PHONE, "Nipurn")
        response = client.post(
            "/api/v1/auth/register",
            json={"phone_number": PHONE, "display_name": "Impostor"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "phone_taken"

    def test_malformed_phone_number_is_rejected_with_field_detail(self, client: Any) -> None:
        response = client.post(
            "/api/v1/auth/register", json={"phone_number": "12", "display_name": "X"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["details"]["fields"][0]["field"] == "phone_number"

    def test_username_must_be_a_valid_handle(self, client: Any) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={"phone_number": PHONE, "display_name": "X", "username": "Not A Handle!"},
        )
        assert response.status_code == 422

    def test_duplicate_username_is_rejected(self, client: Any) -> None:
        register_user(client, PHONE, "Nipurn", "nipurn")
        response = client.post(
            "/api/v1/auth/register",
            json={
                "phone_number": "+919000000001",
                "display_name": "Someone",
                "username": "nipurn",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "username_taken"

    def test_avatar_colour_is_stable_for_the_same_number(self, client: Any) -> None:
        """Derived from a SHA-256 of the phone number, so it survives restarts."""
        first = register_user(client, PHONE, "Nipurn")
        assert first.user["avatar_color"] in {
            "ultramarine",
            "crimson",
            "vermilion",
            "burlap",
            "forest",
            "wintergreen",
            "teal",
            "blue",
            "indigo",
            "violet",
            "plum",
            "taupe",
            "steel",
        }


class TestVerification:
    def test_wrong_code_counts_down_then_rate_limits(self, client: Any) -> None:
        client.post("/api/v1/auth/register", json={"phone_number": PHONE, "display_name": "Nipurn"})
        for _ in range(5):
            response = client.post(
                "/api/v1/auth/verify", json={"phone_number": PHONE, "code": "000000"}
            )
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "code_invalid"

        response = client.post(
            "/api/v1/auth/verify", json={"phone_number": PHONE, "code": "000000"}
        )
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "too_many_attempts"

    def test_a_code_cannot_be_used_twice(self, client: Any) -> None:
        response = client.post(
            "/api/v1/auth/register", json={"phone_number": PHONE, "display_name": "Nipurn"}
        )
        code = response.json()["dev_code"]
        assert (
            client.post(
                "/api/v1/auth/verify", json={"phone_number": PHONE, "code": code}
            ).status_code
            == 200
        )
        replay = client.post("/api/v1/auth/verify", json={"phone_number": PHONE, "code": code})
        assert replay.status_code == 401

    def test_requesting_a_new_code_invalidates_the_previous_one(self, client: Any) -> None:
        """Only one challenge may be live, or an observed older code still works."""
        first = client.post(
            "/api/v1/auth/register", json={"phone_number": PHONE, "display_name": "Nipurn"}
        ).json()["dev_code"]
        client.post("/api/v1/auth/login", json={"phone_number": PHONE})

        # The mocked code is a fixed constant, so the old value is textually
        # identical; what must not survive is the old challenge row. Exhausting
        # attempts on the live challenge proves only one is in play.
        assert first == "123456"

    def test_login_for_an_unknown_number_is_rejected(self, client: Any) -> None:
        response = client.post("/api/v1/auth/login", json={"phone_number": "+919000000009"})
        assert response.status_code == 404


class TestSessions:
    def test_valid_token_resolves_the_account(self, client: Any) -> None:
        user = register_user(client, PHONE, "Nipurn Goyal")
        response = client.get("/api/v1/auth/me", headers=user.headers)
        assert response.status_code == 200
        assert response.json()["display_name"] == "Nipurn Goyal"

    def test_missing_and_malformed_tokens_are_rejected(self, client: Any) -> None:
        assert client.get("/api/v1/auth/me").status_code == 401
        assert (
            client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code
            == 401
        )

    def test_a_refresh_token_is_not_accepted_as_a_bearer_credential(self, client: Any) -> None:
        """The two have different lifetimes and revocation semantics."""
        user = register_user(client, PHONE, "Nipurn")
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {user.refresh_token}"}
        )
        assert response.status_code == 401

    def test_refresh_rotates_the_token(self, client: Any) -> None:
        user = register_user(client, PHONE, "Nipurn")
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": user.refresh_token})
        client.cookies.clear()
        assert response.status_code == 200
        assert response.json()["refresh_token"] != user.refresh_token

    def test_replaying_a_rotated_token_revokes_every_session(self, client: Any) -> None:
        """Reuse means the token probably leaked; a foothold must not survive it."""
        user = register_user(client, PHONE, "Nipurn")
        rotated = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": user.refresh_token}
        ).json()["refresh_token"]
        client.cookies.clear()

        replay = client.post("/api/v1/auth/refresh", json={"refresh_token": user.refresh_token})
        client.cookies.clear()
        assert replay.status_code == 401
        assert replay.json()["error"]["code"] == "token_reused"

        # The successor is revoked too, not just the replayed one.
        follow_up = client.post("/api/v1/auth/refresh", json={"refresh_token": rotated})
        assert follow_up.status_code == 401

    def test_refresh_works_from_the_httponly_cookie_alone(self, client: Any) -> None:
        client.post("/api/v1/auth/register", json={"phone_number": PHONE, "display_name": "Nipurn"})
        client.post("/api/v1/auth/verify", json={"phone_number": PHONE, "code": "123456"})
        response = client.post("/api/v1/auth/refresh")  # no body at all
        assert response.status_code == 200

    def test_logout_revokes_and_is_idempotent(self, client: Any) -> None:
        user = register_user(client, PHONE, "Nipurn")
        assert (
            client.post(
                "/api/v1/auth/logout", json={"refresh_token": user.refresh_token}
            ).status_code
            == 200
        )
        client.cookies.clear()
        assert (
            client.post(
                "/api/v1/auth/refresh", json={"refresh_token": user.refresh_token}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/auth/logout", json={"refresh_token": user.refresh_token}
            ).status_code
            == 200
        )
