"""WebSocket authentication, delivery, typing and presence."""

from __future__ import annotations

import time
from typing import Any

from tests.conftest import register_user

ALICE = "+919000000001"
BOB = "+919000000002"
CARA = "+919000000003"


def _drain(socket: Any) -> list[dict[str, Any]]:
    """Collect every frame currently queued on a socket, then stop.

    ``receive_json`` blocks indefinitely, so reading a fixed number of frames
    hangs the suite whenever fewer arrive than expected — which is exactly the
    case a negative test needs to assert. Instead a ping is sent and frames are
    read until the pong comes back.

    This is deterministic rather than a timing guess: an HTTP handler awaits its
    broadcast before returning, so by the time the triggering request has
    completed, its frame is already queued ahead of the pong.
    """
    socket.send_json({"type": "ping", "payload": {}})
    frames: list[dict[str, Any]] = []
    while True:
        frame = socket.receive_json()
        if frame["type"] == "pong":
            return frames
        frames.append(dict(frame))


def _first(frames: list[dict[str, Any]], wanted: str) -> dict[str, Any] | None:
    return next((frame for frame in frames if frame["type"] == wanted), None)


class TestAuthentication:
    def test_a_socket_without_a_token_is_refused(self, client: Any) -> None:
        from starlette.websockets import WebSocketDisconnect

        try:
            with client.websocket_connect("/ws"):
                raise AssertionError("connection should have been refused")
        except WebSocketDisconnect as exc:
            assert exc.code == 1008

    def test_a_socket_with_a_bad_token_is_refused(self, client: Any) -> None:
        from starlette.websockets import WebSocketDisconnect

        try:
            with client.websocket_connect("/ws?token=nonsense"):
                raise AssertionError("connection should have been refused")
        except WebSocketDisconnect as exc:
            assert exc.code == 1008

    def test_a_valid_token_is_accepted(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        with client.websocket_connect(f"/ws?token={alice.access_token}") as socket:
            frame = socket.receive_json()
            assert frame["type"] == "presence.update"
            assert frame["payload"]["is_online"] is True


class TestDelivery:
    def test_a_message_arrives_over_the_socket_in_real_time(self, client: Any) -> None:
        """The end-to-end property the whole feature exists for."""
        alice = register_user(client, ALICE, "Alice Kapoor")
        bob = register_user(client, BOB, "Bob Mehta")
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()

        with client.websocket_connect(f"/ws?token={bob.access_token}") as bob_socket:
            client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={"body": "Are you there?"},
                headers=alice.headers,
            )
            frame = _first(_drain(bob_socket), "message.new")
            assert frame is not None, "no message.new frame arrived"
            assert frame["payload"]["message"]["body"] == "Are you there?"
            assert frame["payload"]["message"]["sender"]["display_name"] == "Alice Kapoor"

    def test_every_group_member_receives_the_message(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        cara = register_user(client, CARA, "Cara")
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Trek", "member_ids": [bob.id, cara.id]},
            headers=alice.headers,
        ).json()

        with (
            client.websocket_connect(f"/ws?token={bob.access_token}") as bob_socket,
            client.websocket_connect(f"/ws?token={cara.access_token}") as cara_socket,
        ):
            client.post(
                f"/api/v1/conversations/{group['id']}/messages",
                json={"body": "route posted"},
                headers=alice.headers,
            )
            for socket, who in ((bob_socket, "bob"), (cara_socket, "cara")):
                frame = _first(_drain(socket), "message.new")
                assert frame is not None, f"{who} received nothing"
                assert frame["payload"]["message"]["body"] == "route posted"

    def test_a_deleted_message_is_announced(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        message = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"body": "oops"},
            headers=alice.headers,
        ).json()

        with client.websocket_connect(f"/ws?token={bob.access_token}") as bob_socket:
            client.delete(f"/api/v1/messages/{message['id']}", headers=alice.headers)
            frame = _first(_drain(bob_socket), "message.deleted")
            assert frame is not None
            assert frame["payload"]["message_id"] == message["id"]


class TestTyping:
    def test_typing_reaches_the_other_participant(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()

        with (
            client.websocket_connect(f"/ws?token={bob.access_token}") as bob_socket,
            client.websocket_connect(f"/ws?token={alice.access_token}") as alice_socket,
        ):
            alice_socket.send_json(
                {"type": "typing.start", "payload": {"conversation_id": conversation["id"]}}
            )
            _drain(alice_socket)  # let the server process alice's frame first

            frame = _first(_drain(bob_socket), "typing.start")
            assert frame is not None
            assert frame["payload"]["user_id"] == alice.id

    def test_typing_into_a_conversation_you_are_not_in_is_ignored(self, client: Any) -> None:
        """Membership is verified, not trusted — a valid token is not authority."""
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        cara = register_user(client, CARA, "Cara")
        private = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()

        with (
            client.websocket_connect(f"/ws?token={bob.access_token}") as bob_socket,
            client.websocket_connect(f"/ws?token={cara.access_token}") as cara_socket,
        ):
            cara_socket.send_json(
                {"type": "typing.start", "payload": {"conversation_id": private["id"]}}
            )
            _drain(cara_socket)  # cara's frame has now been fully processed

            assert (
                _first(_drain(bob_socket), "typing.start") is None
            ), "a non-member's typing signal leaked into the conversation"


class TestProtocol:
    def test_ping_is_answered_with_pong(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        with client.websocket_connect(f"/ws?token={alice.access_token}") as socket:
            assert socket.receive_json()["type"] == "presence.update"
            socket.send_json({"type": "ping", "payload": {}})
            assert socket.receive_json()["type"] == "pong"

    def test_an_unknown_event_gets_an_error_not_a_dropped_socket(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        with client.websocket_connect(f"/ws?token={alice.access_token}") as socket:
            socket.send_json({"type": "definitely.not.real", "payload": {}})
            assert _first(_drain(socket), "error") is not None
            # The socket must still be usable afterwards.
            assert _drain(socket) == []


class TestPresence:
    def test_connecting_marks_the_user_online_for_their_peers(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        client.post("/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers)

        with client.websocket_connect(f"/ws?token={bob.access_token}") as socket:
            # The server sends this frame only after the presence write has
            # committed, so waiting for it makes the assertion below deterministic
            # rather than a race against the connection handshake.
            assert socket.receive_json()["type"] == "presence.update"

            conversation = client.get("/api/v1/conversations", headers=alice.headers).json()[0]
            bob_view = next(p for p in conversation["participants"] if p["user"]["id"] == bob.id)
            assert bob_view["user"]["is_online"] is True

    def test_disconnecting_records_last_seen(self, client: Any) -> None:
        alice = register_user(client, ALICE, "Alice")
        bob = register_user(client, BOB, "Bob")
        client.post("/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers)

        with client.websocket_connect(f"/ws?token={bob.access_token}"):
            pass

        def bob_as_alice_sees_him() -> dict[str, Any]:
            conversation = client.get("/api/v1/conversations", headers=alice.headers).json()[0]
            return next(p for p in conversation["participants"] if p["user"]["id"] == bob.id)

        # The server records last-seen in its disconnect handler, which runs after
        # the client has already let go of the socket. There is no hook to await,
        # so this polls rather than assuming the write is instantaneous — the
        # alternative is a test that passes or fails on scheduling luck.
        deadline = time.monotonic() + 3.0
        view = bob_as_alice_sees_him()
        while view["user"]["last_seen_at"] is None and time.monotonic() < deadline:
            time.sleep(0.05)
            view = bob_as_alice_sees_him()

        assert view["user"]["is_online"] is False
        assert view["user"]["last_seen_at"] is not None
