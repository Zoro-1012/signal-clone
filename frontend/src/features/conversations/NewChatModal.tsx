"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Search, Users } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Contact, Conversation, UserPublic } from "@/lib/types";
import { useUi } from "@/stores/ui";

import { conversationKeys } from "./queries";

type Mode = "pick" | "group";

interface NewChatModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NewChatModal({ open, onOpenChange }: NewChatModalProps) {
  const queryClient = useQueryClient();
  const openConversation = useUi((s) => s.openConversation);

  const [mode, setMode] = useState<Mode>("pick");
  const [search, setSearch] = useState("");
  const [groupName, setGroupName] = useState("");
  const [selected, setSelected] = useState<UserPublic[]>([]);
  const [error, setError] = useState<string | null>(null);

  const deferredSearch = useDeferredValue(search);

  const { data: contacts } = useQuery({
    queryKey: ["contacts", deferredSearch],
    queryFn: () =>
      api.get<Contact[]>(
        `/contacts${deferredSearch ? `?q=${encodeURIComponent(deferredSearch)}` : ""}`,
      ),
    enabled: open,
  });

  // Searching beyond your address book, because Signal lets you message someone
  // you have not saved. Only runs once the term is long enough to be meaningful.
  const { data: discovered } = useQuery({
    queryKey: ["user-search", deferredSearch],
    queryFn: () => api.get<UserPublic[]>(`/users/search?q=${encodeURIComponent(deferredSearch)}`),
    enabled: open && deferredSearch.trim().length >= 2,
  });

  const people: UserPublic[] = (() => {
    const fromContacts = (contacts ?? []).map((contact) => contact.user);
    const seen = new Set(fromContacts.map((person) => person.id));
    return [...fromContacts, ...(discovered ?? []).filter((person) => !seen.has(person.id))];
  })();

  function reset() {
    setMode("pick");
    setSearch("");
    setGroupName("");
    setSelected([]);
    setError(null);
  }

  function close() {
    reset();
    onOpenChange(false);
  }

  const startDirect = useMutation({
    mutationFn: (userId: string) =>
      api.post<Conversation>("/conversations/direct", { user_id: userId }),
    onSuccess: (conversation) => {
      void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
      openConversation(conversation.id);
      close();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not start that chat."),
  });

  /** What is stopping the group from being created, if anything. */
  const blocker =
    groupName.trim().length === 0
      ? "Add a group name to continue"
      : selected.length === 0
        ? "Choose at least one member"
        : null;

  const createGroup = useMutation({
    mutationFn: () =>
      api.post<Conversation>("/conversations/group", {
        name: groupName.trim(),
        member_ids: selected.map((person) => person.id),
      }),
    onSuccess: (conversation) => {
      void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
      openConversation(conversation.id);
      close();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not create that group."),
  });

  function toggle(person: UserPublic) {
    setSelected((current) =>
      current.some((p) => p.id === person.id)
        ? current.filter((p) => p.id !== person.id)
        : [...current, person],
    );
  }

  return (
    <Modal
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : close())}
      title={mode === "group" ? "New group" : "New chat"}
      footer={
        mode === "group" ? (
          <div className="flex items-center justify-between gap-3">
            {/* A disabled button with no stated reason is a dead end: the person
                sees "4 selected", presses Create, nothing happens, and nothing
                on screen explains why. Say what is missing instead. */}
            <span className="text-sm text-content-secondary">
              {blocker ?? `${selected.length} selected`}
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setMode("pick")}>
                Back
              </Button>
              <Button
                onClick={() => createGroup.mutate()}
                loading={createGroup.isPending}
                disabled={blocker !== null}
              >
                Create
              </Button>
            </div>
          </div>
        ) : undefined
      }
    >
      {mode === "group" && (
        <div className="mb-4">
          <Input
            label="Group name"
            autoFocus
            required
            placeholder="Weekend plans"
            value={groupName}
            onChange={(event) => setGroupName(event.target.value)}
            // Only complains once the person has done the other half of the
            // job, so it reads as the remaining step rather than as an error
            // on a form they have not filled in yet.
            error={
              selected.length > 0 && groupName.trim().length === 0
                ? "A group needs a name."
                : undefined
            }
          />
        </div>
      )}

      <div className="relative mb-3">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-content-tertiary"
          aria-hidden="true"
        />
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Name, username, or number"
          aria-label="Search people"
          className="w-full rounded-full bg-surface-hover py-2 pl-9 pr-3 text-sm text-content-primary outline-none placeholder:text-content-tertiary focus:ring-1 focus:ring-accent"
        />
      </div>

      {mode === "pick" && (
        <button
          onClick={() => setMode("group")}
          className="mb-2 flex w-full items-center gap-3 rounded-xl px-2 py-2.5 text-left transition-colors hover:bg-surface-hover"
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-hover">
            <Users className="h-5 w-5 text-content-primary" />
          </span>
          <span className="font-medium text-content-primary">New group</span>
        </button>
      )}

      {error && <p className="mb-2 text-sm text-signal-red">{error}</p>}

      {people.length === 0 ? (
        <p className="py-8 text-center text-sm text-content-secondary">
          {deferredSearch ? "Nobody matches that search." : "No contacts yet."}
        </p>
      ) : (
        <ul className="space-y-0.5">
          {people.map((person) => {
            const isSelected = selected.some((p) => p.id === person.id);
            return (
              <li key={person.id}>
                <button
                  onClick={() =>
                    mode === "group" ? toggle(person) : startDirect.mutate(person.id)
                  }
                  disabled={startDirect.isPending}
                  aria-pressed={mode === "group" ? isSelected : undefined}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors",
                    "hover:bg-surface-hover disabled:opacity-60",
                    isSelected && "bg-surface-hover",
                  )}
                >
                  <Avatar
                    name={person.display_name}
                    color={person.avatar_color}
                    src={person.avatar_url}
                    online={person.is_online}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-content-primary">
                      {person.display_name}
                    </span>
                    {person.username && (
                      <span className="block truncate text-sm text-content-secondary">
                        @{person.username}
                      </span>
                    )}
                  </span>
                  {mode === "group" && isSelected && (
                    <Check className="h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Modal>
  );
}
