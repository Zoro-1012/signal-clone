"""Conversations, membership and group administration."""

from __future__ import annotations

from typing import Any

from tests.conftest import register_user

ALICE = "+919000000001"
BOB = "+919000000002"
CARA = "+919000000003"


def _cast(client: Any) -> tuple[Any, Any, Any]:
    alice = register_user(client, ALICE, "Alice Kapoor", "alice")
    bob = register_user(client, BOB, "Bob Mehta", "bob")
    cara = register_user(client, CARA, "Cara Rao", "cara")
    return alice, bob, cara


class TestDirectConversations:
    def test_opening_a_chat_twice_returns_the_same_thread(self, client: Any) -> None:
        """Tapping a contact twice must not create a second conversation."""
        alice, bob, _ = _cast(client)
        first = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        )
        second = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        )
        assert first.status_code == 201
        assert first.json()["id"] == second.json()["id"]

    def test_the_same_thread_is_found_from_either_side(self, client: Any) -> None:
        """The canonical direct key is order-independent, so B->A finds A->B."""
        alice, bob, _ = _cast(client)
        from_alice = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        from_bob = client.post(
            "/api/v1/conversations/direct", json={"user_id": alice.id}, headers=bob.headers
        ).json()
        assert from_alice["id"] == from_bob["id"]

    def test_a_direct_chat_is_presented_as_the_other_person(self, client: Any) -> None:
        """Direct conversations store no name; the API resolves it per viewer."""
        alice, bob, _ = _cast(client)
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        assert conversation["name"] == "Bob Mehta"

        seen_by_bob = client.get("/api/v1/conversations", headers=bob.headers).json()[0]
        assert seen_by_bob["name"] == "Alice Kapoor"

    def test_direct_conversations_cannot_be_renamed(self, client: Any) -> None:
        alice, bob, _ = _cast(client)
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        response = client.patch(
            f"/api/v1/conversations/{conversation['id']}",
            json={"name": "Nope"},
            headers=alice.headers,
        )
        assert response.status_code == 422


class TestAuthorisation:
    def test_a_non_member_cannot_see_a_conversation(self, client: Any) -> None:
        """404, not 403: revealing existence would leak other people's threads."""
        alice, bob, cara = _cast(client)
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        response = client.get(f"/api/v1/conversations/{conversation['id']}", headers=cara.headers)
        assert response.status_code == 404

    def test_a_plain_member_cannot_administer_a_group(self, client: Any) -> None:
        alice, bob, cara = _cast(client)
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Weekend Plans", "member_ids": [bob.id]},
            headers=alice.headers,
        ).json()

        assert (
            client.patch(
                f"/api/v1/conversations/{group['id']}",
                json={"name": "Hijacked"},
                headers=bob.headers,
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/conversations/{group['id']}/participants",
                json={"user_ids": [cara.id]},
                headers=bob.headers,
            ).status_code
            == 403
        )


class TestGroups:
    def test_creator_becomes_admin_and_members_are_added(self, client: Any) -> None:
        alice, bob, cara = _cast(client)
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Weekend Plans", "member_ids": [bob.id, cara.id]},
            headers=alice.headers,
        ).json()

        assert group["type"] == "group"
        assert group["my_role"] == "admin"
        assert len(group["participants"]) == 3
        roles = {p["user"]["id"]: p["role"] for p in group["participants"]}
        assert roles[alice.id] == "admin"
        assert roles[bob.id] == "member"

    def test_creating_a_group_records_a_system_message(self, client: Any) -> None:
        """System events share the messages table so the timeline is one sequence."""
        alice, bob, _ = _cast(client)
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Weekend Plans", "member_ids": [bob.id]},
            headers=alice.headers,
        ).json()
        assert group["last_message"]["type"] == "system"
        assert group["last_message"]["system_event"] == "group_created"

    def test_duplicate_member_ids_are_a_no_op_not_an_error(self, client: Any) -> None:
        """A double-tap or stale list must not violate the unique constraint."""
        alice, bob, _ = _cast(client)
        response = client.post(
            "/api/v1/conversations/group",
            json={"name": "Dupes", "member_ids": [bob.id, bob.id, bob.id]},
            headers=alice.headers,
        )
        assert response.status_code == 201
        assert len(response.json()["participants"]) == 2

    def test_adding_someone_already_present_is_skipped(self, client: Any) -> None:
        alice, bob, cara = _cast(client)
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Team", "member_ids": [bob.id]},
            headers=alice.headers,
        ).json()
        response = client.post(
            f"/api/v1/conversations/{group['id']}/participants",
            json={"user_ids": [bob.id, cara.id]},
            headers=alice.headers,
        )
        assert response.status_code == 200
        assert len(response.json()["participants"]) == 3

    def test_a_member_may_leave_without_being_an_admin(self, client: Any) -> None:
        alice, bob, _ = _cast(client)
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Team", "member_ids": [bob.id]},
            headers=alice.headers,
        ).json()
        response = client.delete(
            f"/api/v1/conversations/{group['id']}/participants/{bob.id}", headers=bob.headers
        )
        assert response.status_code == 204
        assert client.get("/api/v1/conversations", headers=bob.headers).json() == []

    def test_a_group_is_never_left_without_an_admin(self, client: Any) -> None:
        """The last admin leaving would otherwise make the group unmanageable."""
        alice, bob, cara = _cast(client)
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Team", "member_ids": [bob.id, cara.id]},
            headers=alice.headers,
        ).json()

        client.delete(
            f"/api/v1/conversations/{group['id']}/participants/{alice.id}", headers=alice.headers
        )

        remaining = client.get(f"/api/v1/conversations/{group['id']}", headers=bob.headers).json()
        roles = {p["user"]["id"]: p["role"] for p in remaining["participants"]}
        assert "admin" in roles.values(), "group was left with no admin"

    def test_removed_members_disappear_from_the_participant_list(self, client: Any) -> None:
        alice, bob, cara = _cast(client)
        group = client.post(
            "/api/v1/conversations/group",
            json={"name": "Team", "member_ids": [bob.id, cara.id]},
            headers=alice.headers,
        ).json()
        client.delete(
            f"/api/v1/conversations/{group['id']}/participants/{cara.id}", headers=alice.headers
        )
        after = client.get(f"/api/v1/conversations/{group['id']}", headers=alice.headers).json()
        assert cara.id not in {p["user"]["id"] for p in after["participants"]}


class TestListing:
    def test_pinned_conversations_sort_first(self, client: Any) -> None:
        alice, bob, cara = _cast(client)
        older = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        client.post(
            "/api/v1/conversations/group",
            json={"name": "Newer", "member_ids": [cara.id]},
            headers=alice.headers,
        )
        client.post(
            f"/api/v1/conversations/{older['id']}/flags",
            json={"is_pinned": True},
            headers=alice.headers,
        )
        listing = client.get("/api/v1/conversations", headers=alice.headers).json()
        assert listing[0]["id"] == older["id"]
        assert listing[0]["is_pinned"] is True

    def test_search_matches_group_names_and_people(self, client: Any) -> None:
        alice, bob, cara = _cast(client)
        client.post("/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers)
        client.post(
            "/api/v1/conversations/group",
            json={"name": "Trek Planning", "member_ids": [cara.id]},
            headers=alice.headers,
        )

        by_group = client.get("/api/v1/conversations?q=trek", headers=alice.headers).json()
        assert len(by_group) == 1 and by_group[0]["name"] == "Trek Planning"

        by_person = client.get("/api/v1/conversations?q=bob", headers=alice.headers).json()
        assert len(by_person) == 1 and by_person[0]["name"] == "Bob Mehta"

    def test_flags_are_private_to_each_member(self, client: Any) -> None:
        """Mute and pin are per-viewer, which is why they are not on the row."""
        alice, bob, _ = _cast(client)
        conversation = client.post(
            "/api/v1/conversations/direct", json={"user_id": bob.id}, headers=alice.headers
        ).json()
        client.post(
            f"/api/v1/conversations/{conversation['id']}/flags",
            json={"is_muted": True},
            headers=alice.headers,
        )
        seen_by_bob = client.get("/api/v1/conversations", headers=bob.headers).json()[0]
        assert seen_by_bob["is_muted"] is False


class TestContacts:
    def test_add_by_username_and_by_phone_number(self, client: Any) -> None:
        alice, _bob, _cara = _cast(client)
        assert (
            client.post(
                "/api/v1/contacts", json={"identifier": "bob"}, headers=alice.headers
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/contacts", json={"identifier": CARA}, headers=alice.headers
            ).status_code
            == 201
        )
        assert len(client.get("/api/v1/contacts", headers=alice.headers).json()) == 2

    def test_unknown_identifier_is_reported_clearly(self, client: Any) -> None:
        alice, _, _ = _cast(client)
        response = client.post(
            "/api/v1/contacts", json={"identifier": "+919999999999"}, headers=alice.headers
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "user_not_found"

    def test_you_cannot_add_yourself(self, client: Any) -> None:
        alice, _, _ = _cast(client)
        response = client.post(
            "/api/v1/contacts", json={"identifier": "alice"}, headers=alice.headers
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "self_contact"

    def test_duplicate_contacts_are_rejected(self, client: Any) -> None:
        alice, _, _ = _cast(client)
        client.post("/api/v1/contacts", json={"identifier": "bob"}, headers=alice.headers)
        response = client.post(
            "/api/v1/contacts", json={"identifier": "bob"}, headers=alice.headers
        )
        assert response.status_code == 409

    def test_contacts_are_one_way(self, client: Any) -> None:
        """Saving a number must not require consent, nor add you to their list."""
        alice, bob, _ = _cast(client)
        client.post("/api/v1/contacts", json={"identifier": "bob"}, headers=alice.headers)
        assert client.get("/api/v1/contacts", headers=bob.headers).json() == []

    def test_you_cannot_delete_someone_else_s_contact(self, client: Any) -> None:
        alice, bob, _ = _cast(client)
        contact = client.post(
            "/api/v1/contacts", json={"identifier": "bob"}, headers=alice.headers
        ).json()
        response = client.delete(f"/api/v1/contacts/{contact['id']}", headers=bob.headers)
        assert response.status_code == 404
