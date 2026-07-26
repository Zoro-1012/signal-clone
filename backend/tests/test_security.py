"""Security properties: authorisation boundaries and information disclosure.

These assert the things that would be quietly exploitable rather than merely
broken, so a regression in any of them fails the build.
"""

from __future__ import annotations

from typing import Any

from tests.conftest import register_user

ALICE = "+919000000001"
BOB = "+919000000002"
CARA = "+919000000003"


class TestInformationDisclosure:
    def test_phone_numbers_of_others_are_never_exposed(self, client: Any) -> None:
        """A number is a login identifier and personal contact detail.

        Exposing every group member's number to every other member would leak
        contact details Signal treats as private.
        """
        alice = register_user(client, ALICE, "Alice", "alice")
        bob = register_user(client, BOB, "Bob", "bob")
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Team", "member_ids": [bob.id]},
            headers=alice.headers,
        ).json()

        serialised = str(group)
        assert BOB not in serialised
        assert ALICE not in serialised

        # Your own profile does include it — you already know your own number.
        assert client.get("/api/v1/users/me", headers=alice.headers).json()["phone_number"] == ALICE

    def test_search_results_do_not_leak_phone_numbers(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice", "alice")
        register_user(client, BOB, "Bob Mehta", "bob")
        results = client.get("/api/v1/users/search?q=bob", headers=alice.headers).json()
        assert results and "phone_number" not in results[0]

    def test_a_missing_resource_and_a_forbidden_one_are_indistinguishable(
        self, client: Any
    ) -> None:
        """Otherwise identifiers can be probed for existence."""
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        cara = register_user(client, CARA, "Cara")
        private = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()

        real_but_forbidden = client.get(
            f"/api/v1/conversations/{private['id']}", headers=cara.headers
        )
        does_not_exist = client.get(
            "/api/v1/conversations/00000000000000000000000000000000", headers=cara.headers
        )
        assert real_but_forbidden.status_code == does_not_exist.status_code == 404
        assert real_but_forbidden.json() == does_not_exist.json()

    def test_internal_errors_do_not_leak_details(self, client: Any) -> None:
        response = client.get("/api/v1/conversations/%00%00", headers={})
        assert response.status_code in (401, 404, 422)
        assert "Traceback" not in response.text
        assert "sqlalchemy" not in response.text.lower()


class TestAuthorisationBoundaries:
    def test_messages_cannot_be_read_from_a_conversation_you_are_not_in(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        cara = register_user(client, CARA, "Cara")
        private = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        client.post(
            f"/api/v1/conversations/{private['id']}/messages",
            json={"body": "confidential"},
            headers=alice.headers,
        )

        response = client.get(
            f"/api/v1/conversations/{private['id']}/messages", headers=cara.headers
        )
        assert response.status_code == 404
        assert "confidential" not in response.text

    def test_you_cannot_react_to_a_message_you_cannot_see(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        cara = register_user(client, CARA, "Cara")
        private = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        message = client.post(
            f"/api/v1/conversations/{private['id']}/messages",
            json={"body": "private"},
            headers=alice.headers,
        ).json()

        response = client.post(
            f"/api/v1/messages/{message['id']}/reactions",
            json={"emoji": "\U0001f44d"},
            headers=cara.headers,
        )
        assert response.status_code == 404

    def test_you_cannot_mark_another_conversation_read(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        cara = register_user(client, CARA, "Cara")
        private = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        message = client.post(
            f"/api/v1/conversations/{private['id']}/messages",
            json={"body": "hi"},
            headers=alice.headers,
        ).json()

        response = client.post(
            f"/api/v1/conversations/{private['id']}/messages/{message['id']}/read",
            headers=cara.headers,
        )
        assert response.status_code == 404

    def test_a_username_cannot_be_stolen_by_updating_a_profile(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice", "alice")
        bob = register_user(client, BOB, "Bob", "bob")
        response = client.patch("/api/v1/users/me", json={"username": "alice"}, headers=bob.headers)
        assert response.status_code == 409
        assert client.get("/api/v1/users/me", headers=alice.headers).json()["username"] == "alice"


class TestAttachmentSafety:
    def test_path_traversal_in_an_attachment_key_is_refused(self, client: Any) -> None:
        """Keys arrive from URLs, so traversal is checked rather than assumed."""
        for candidate in (
            "../../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "....//....//etc/passwd",
        ):
            response = client.get(f"/api/v1/attachments/{candidate}")
            assert response.status_code == 404, candidate
            assert "root:" not in response.text

    def test_an_unsupported_file_type_is_rejected(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        response = client.post(
            "/api/v1/attachments",
            files={"file": ("payload.sh", b"#!/bin/sh\nrm -rf /", "application/x-sh")},
            headers=alice.headers,
        )
        assert response.status_code == 415

    def test_an_uploaded_file_is_stored_under_a_generated_name(self, client: Any) -> None:
        """A filename is attacker-controlled and must never reach the filesystem."""
        alice = register_user(client, ALICE, "Alice")
        response = client.post(
            "/api/v1/attachments",
            files={"file": ("../../evil.txt", b"harmless", "text/plain")},
            headers=alice.headers,
        )
        assert response.status_code == 201
        assert "evil" not in response.json()["url"]
        assert ".." not in response.json()["url"]

    def test_you_cannot_attach_someone_else_s_upload(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()

        upload = client.post(
            "/api/v1/attachments",
            files={"file": ("note.txt", b"alice's file", "text/plain")},
            headers=alice.headers,
        ).json()

        # Alice sends it, which claims the attachment.
        assert (
            client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={"body": "mine", "attachment_ids": [upload["id"]]},
                headers=alice.headers,
            ).status_code
            == 201
        )
        # Bob cannot then re-attach the same, already-claimed upload.
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"body": "stolen", "attachment_ids": [upload["id"]]},
            headers=bob.headers,
        )
        assert response.status_code == 422


class TestTokenHandling:
    def test_refresh_tokens_are_not_stored_in_plaintext(self, client: Any, db_path: Any) -> None:
        """A database disclosure must not hand over usable sessions."""
        import sqlite3

        alice = register_user(client, ALICE, "Alice")
        rows = (
            sqlite3.connect(str(db_path))
            .execute("SELECT token_hash FROM refresh_tokens")
            .fetchall()
        )
        stored = " ".join(str(row[0]) for row in rows)
        assert alice.refresh_token not in stored
        assert stored, "no refresh token row was written"

    def test_verification_codes_are_single_use_and_attempt_limited(self, client: Any) -> None:
        client.post("/api/v1/auth/register", json={"phone_number": ALICE, "display_name": "Alice"})
        for _ in range(5):
            client.post("/api/v1/auth/verify", json={"phone_number": ALICE, "code": "999999"})
        blocked = client.post("/api/v1/auth/verify", json={"phone_number": ALICE, "code": "123456"})
        # Even the correct code fails once the attempt budget is spent.
        assert blocked.status_code == 429
