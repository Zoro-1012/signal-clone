"""Sending, receipts, reactions, replies and editing."""

from __future__ import annotations

from typing import Any

from tests.conftest import register_user

ALICE = "+919000000001"
BOB = "+919000000002"
CARA = "+919000000003"


def _pair(client: Any) -> tuple[Any, Any, str]:
    alice = register_user(client, ALICE, "Alice Kapoor", "alice")
    bob = register_user(client, BOB, "Bob Mehta", "bob")
    conversation = client.post(
        "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
    ).json()
    return alice, bob, conversation["id"]


def _trio(client: Any) -> tuple[Any, Any, Any, str]:
    alice = register_user(client, ALICE, "Alice Kapoor", "alice")
    bob = register_user(client, BOB, "Bob Mehta", "bob")
    cara = register_user(client, CARA, "Cara Rao", "cara")
    group = client.post(
        "/api/v1/conversations/group",
        json={"name": "Trek", "member_ids": [bob.id, cara.id]},
        headers=alice.headers,
    ).json()
    return alice, bob, cara, group["id"]


def _send(client: Any, user: Any, conversation_id: str, body: str, **extra: Any) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"body": body, **extra},
        headers=user.headers,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


class TestSending:
    def test_a_message_round_trips_as_plaintext(self, client: Any) -> None:
        alice, _, conversation_id = _pair(client)
        message = _send(client, alice, conversation_id, "Hey, are we still on for Saturday?")
        assert message["body"] == "Hey, are we still on for Saturday?"
        assert message["sender"]["display_name"] == "Alice Kapoor"

    def test_content_is_stored_sealed_not_as_plaintext(self, client: Any, db_path: Any) -> None:
        """No plaintext column exists; this asserts the sealing actually happened."""
        import sqlite3

        alice, _, conversation_id = _pair(client)
        _send(client, alice, conversation_id, "a secret sentence")

        # Read the raw rows, bypassing both the ORM and the cipher.
        rows = sqlite3.connect(str(db_path)).execute("SELECT ciphertext FROM messages").fetchall()
        stored = " ".join(str(r[0]) for r in rows if r[0])
        assert "a secret sentence" not in stored

    def test_a_message_needs_text_or_an_attachment(self, client: Any) -> None:
        alice, _, conversation_id = _pair(client)
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"body": "   "},
            headers=alice.headers,
        )
        assert response.status_code == 422

    def test_a_retried_send_does_not_duplicate(self, client: Any) -> None:
        """The client_message_id makes a timeout retry idempotent."""
        alice, _, conversation_id = _pair(client)
        first = _send(client, alice, conversation_id, "Only once", client_message_id="abc-123")
        second = _send(client, alice, conversation_id, "Only once", client_message_id="abc-123")
        assert first["id"] == second["id"]

        history = client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=alice.headers
        ).json()
        assert len([m for m in history["items"] if m["type"] == "text"]) == 1

    def test_a_non_member_cannot_send(self, client: Any) -> None:
        _alice, _bob, conversation_id = _pair(client)
        cara = register_user(client, CARA, "Cara Rao", "cara")
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"body": "let me in"},
            headers=cara.headers,
        )
        assert response.status_code == 404

    def test_sending_moves_the_conversation_to_the_top(self, client: Any) -> None:
        alice, bob, _cara, _group_id = _trio(client)
        direct = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        _send(client, alice, direct["id"], "newest activity")

        listing = client.get("/api/v1/conversations", headers=alice.headers).json()
        assert listing[0]["id"] == direct["id"]
        assert listing[0]["last_message"]["preview"] == "newest activity"


class TestReceipts:
    def test_status_progresses_sent_to_delivered_to_read(self, client: Any) -> None:
        alice, bob, conversation_id = _pair(client)
        message = _send(client, alice, conversation_id, "ping")
        assert message["status"] == "sent"

        client.post(f"/api/v1/conversations/{conversation_id}/delivered", headers=bob.headers)
        after_delivery = client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=alice.headers
        ).json()["items"][0]
        assert after_delivery["status"] == "delivered"

        client.post(
            f"/api/v1/conversations/{conversation_id}/messages/{message['id']}/read",
            headers=bob.headers,
        )
        after_read = client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=alice.headers
        ).json()["items"][0]
        assert after_read["status"] == "read"

    def test_group_status_follows_the_weakest_recipient(self, client: Any) -> None:
        """The double blue check appears only once everyone has read."""
        alice, bob, cara, group_id = _trio(client)
        message = _send(client, alice, group_id, "who is coming?")

        client.post(f"/api/v1/conversations/{group_id}/delivered", headers=bob.headers)
        client.post(f"/api/v1/conversations/{group_id}/delivered", headers=cara.headers)
        client.post(
            f"/api/v1/conversations/{group_id}/messages/{message['id']}/read", headers=bob.headers
        )

        view = client.get(
            f"/api/v1/conversations/{group_id}/messages", headers=alice.headers
        ).json()["items"][0]
        assert view["read_count"] == 1
        assert view["recipient_count"] == 2
        assert view["status"] == "delivered", "one of two read should not show as read"

        client.post(
            f"/api/v1/conversations/{group_id}/messages/{message['id']}/read", headers=cara.headers
        )
        final = client.get(
            f"/api/v1/conversations/{group_id}/messages", headers=alice.headers
        ).json()["items"][0]
        assert final["status"] == "read"

    def test_reading_implies_delivery(self, client: Any) -> None:
        """A message cannot be read without having arrived."""
        alice, bob, conversation_id = _pair(client)
        message = _send(client, alice, conversation_id, "ping")
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages/{message['id']}/read",
            headers=bob.headers,
        )
        view = client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=alice.headers
        ).json()["items"][0]
        assert view["delivered_count"] == 1

    def test_reading_clears_the_unread_count(self, client: Any) -> None:
        alice, bob, conversation_id = _pair(client)
        for i in range(3):
            _send(client, alice, conversation_id, f"message {i}")

        before = client.get("/api/v1/conversations", headers=bob.headers).json()[0]
        assert before["unread_count"] == 3

        newest = client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=bob.headers
        ).json()["items"][0]
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages/{newest['id']}/read",
            headers=bob.headers,
        )
        after = client.get("/api/v1/conversations", headers=bob.headers).json()[0]
        assert after["unread_count"] == 0

    def test_your_own_messages_are_never_unread(self, client: Any) -> None:
        alice, _, conversation_id = _pair(client)
        _send(client, alice, conversation_id, "note to nobody")
        listing = client.get("/api/v1/conversations", headers=alice.headers).json()[0]
        assert listing["unread_count"] == 0


class TestReactionsAndReplies:
    def test_reactions_toggle_and_aggregate(self, client: Any) -> None:
        alice, bob, cara, group_id = _trio(client)
        message = _send(client, alice, group_id, "good news")

        client.post(
            f"/api/v1/messages/{message['id']}/reactions",
            json={"emoji": "\U0001f44d"},
            headers=bob.headers,
        )
        response = client.post(
            f"/api/v1/messages/{message['id']}/reactions",
            json={"emoji": "\U0001f44d"},
            headers=cara.headers,
        ).json()
        assert response["reactions"][0]["count"] == 2
        assert response["reactions"][0]["reacted_by_me"] is True  # viewer is cara

        # Same emoji again from the same person removes it.
        toggled = client.post(
            f"/api/v1/messages/{message['id']}/reactions",
            json={"emoji": "\U0001f44d"},
            headers=cara.headers,
        ).json()
        assert toggled["reactions"][0]["count"] == 1
        assert toggled["reactions"][0]["reacted_by_me"] is False

    def test_a_reply_carries_a_quote(self, client: Any) -> None:
        alice, bob, conversation_id = _pair(client)
        original = _send(client, alice, conversation_id, "Shall we meet at six?")
        reply = _send(client, bob, conversation_id, "Six works", reply_to_message_id=original["id"])
        assert reply["reply_to"]["preview"] == "Shall we meet at six?"
        assert reply["reply_to"]["sender_display_name"] == "Alice Kapoor"

    def test_you_cannot_quote_a_message_from_another_conversation(self, client: Any) -> None:
        """Otherwise a quote leaks content from a thread the recipients are not in."""
        alice, bob, _cara, group_id = _trio(client)
        direct = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        private = _send(client, alice, direct["id"], "something private")

        response = client.post(
            f"/api/v1/conversations/{group_id}/messages",
            json={"body": "look at this", "reply_to_message_id": private["id"]},
            headers=alice.headers,
        )
        assert response.status_code == 422


class TestEditingAndDeleting:
    def test_editing_replaces_the_body_and_stamps_edited_at(self, client: Any) -> None:
        alice, _, conversation_id = _pair(client)
        message = _send(client, alice, conversation_id, "teh meeting is at 5")
        edited = client.patch(
            f"/api/v1/messages/{message['id']}",
            json={"body": "the meeting is at 5"},
            headers=alice.headers,
        ).json()
        assert edited["body"] == "the meeting is at 5"
        assert edited["edited_at"] is not None

    def test_you_cannot_edit_someone_else_s_message(self, client: Any) -> None:
        alice, bob, conversation_id = _pair(client)
        message = _send(client, alice, conversation_id, "mine")
        response = client.patch(
            f"/api/v1/messages/{message['id']}", json={"body": "hijacked"}, headers=bob.headers
        )
        assert response.status_code == 403

    def test_deleting_leaves_a_tombstone_and_drops_the_content(self, client: Any) -> None:
        alice, bob, conversation_id = _pair(client)
        message = _send(client, alice, conversation_id, "please forget this")
        assert (
            client.delete(f"/api/v1/messages/{message['id']}", headers=alice.headers).status_code
            == 204
        )

        history = client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=bob.headers
        ).json()["items"]
        tombstone = next(m for m in history if m["id"] == message["id"])
        assert tombstone["deleted_at"] is not None
        assert tombstone["body"] is None, "content must not survive deletion"


class TestPagination:
    def test_history_is_cursor_paginated_and_stable(self, client: Any) -> None:
        alice, _bob, conversation_id = _pair(client)
        for i in range(12):
            _send(client, alice, conversation_id, f"message {i:02d}")

        first = client.get(
            f"/api/v1/conversations/{conversation_id}/messages?limit=5", headers=alice.headers
        ).json()
        assert len(first["items"]) == 5
        assert first["has_more"] is True

        second = client.get(
            f"/api/v1/conversations/{conversation_id}/messages"
            f"?limit=5&cursor={first['next_cursor']}",
            headers=alice.headers,
        ).json()
        assert len(second["items"]) == 5

        # No overlap between pages, which is the property offset pagination loses.
        assert not {m["id"] for m in first["items"]} & {m["id"] for m in second["items"]}
