"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, Search, ShieldCheck, UserMinus, UserPlus } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { conversationKeys } from "@/features/conversations/queries";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Contact, Conversation, UserPrivate, UserPublic } from "@/lib/types";
import { useUi } from "@/stores/ui";

interface GroupInfoPanelProps {
  conversation: Conversation;
  user: UserPrivate;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GroupInfoPanel({
  conversation,
  user,
  open,
  onOpenChange,
}: GroupInfoPanelProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const openConversation = useUi((s) => s.openConversation);
  const [adding, setAdding] = useState(false);

  const isAdmin = conversation.my_role === "admin";
  const members = conversation.participants;

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
  }

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      api.delete<void>(`/conversations/${conversation.id}/participants/${userId}`),
    onSuccess: (_data, userId) => {
      refresh();
      // Leaving your own group closes the pane, because you can no longer read it.
      if (userId === user.id) {
        openConversation(null);
        onOpenChange(false);
        toast.success("You left the group.");
      } else {
        toast.success("Member removed.");
      }
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove that member."),
  });

  return (
    <>
      <Modal
        open={open}
        onOpenChange={onOpenChange}
        title="Group info"
        footer={
          <div className="flex justify-between gap-2">
            <Button
              variant="danger"
              size="sm"
              onClick={() => removeMember.mutate(user.id)}
              loading={removeMember.isPending && removeMember.variables === user.id}
            >
              <LogOut className="h-4 w-4" />
              Leave group
            </Button>
            {isAdmin && (
              <Button size="sm" onClick={() => setAdding(true)}>
                <UserPlus className="h-4 w-4" />
                Add members
              </Button>
            )}
          </div>
        }
      >
        <div className="mb-6 flex flex-col items-center text-center">
          <Avatar
            name={conversation.name ?? "Group"}
            color={conversation.avatar_color}
            src={conversation.avatar_url}
            size="xl"
          />
          <h3 className="mt-3 text-lg font-semibold text-content-primary">
            {conversation.name}
          </h3>
          <p className="text-sm text-content-secondary">{members.length} members</p>
        </div>

        <h4 className="mb-2 text-sm font-medium text-content-secondary">Members</h4>
        <ul className="space-y-0.5">
          {members.map((participant) => {
            const isSelf = participant.user.id === user.id;
            return (
              <li
                key={participant.user.id}
                className="flex items-center gap-3 rounded-xl px-2 py-2"
              >
                <Avatar
                  name={participant.user.display_name}
                  color={participant.user.avatar_color}
                  src={participant.user.avatar_url}
                  online={participant.user.is_online}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-content-primary">
                    {isSelf ? "You" : participant.user.display_name}
                  </p>
                  {participant.user.username && (
                    <p className="truncate text-sm text-content-secondary">
                      @{participant.user.username}
                    </p>
                  )}
                </div>

                {participant.role === "admin" && (
                  <span
                    className="flex shrink-0 items-center gap-1 rounded-full bg-surface-hover px-2 py-0.5 text-xs text-content-secondary"
                    title="Group admin"
                  >
                    <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                    Admin
                  </span>
                )}

                {/* Removal is admin-only and never offered for yourself — leaving
                    is a different action with different semantics, and it has its
                    own button in the footer. */}
                {isAdmin && !isSelf && (
                  <button
                    onClick={() => removeMember.mutate(participant.user.id)}
                    disabled={removeMember.isPending}
                    aria-label={`Remove ${participant.user.display_name}`}
                    title={`Remove ${participant.user.display_name}`}
                    className="shrink-0 rounded-full p-1.5 text-content-tertiary transition-colors hover:bg-surface-hover hover:text-signal-red disabled:opacity-50"
                  >
                    <UserMinus className="h-4 w-4" />
                  </button>
                )}
              </li>
            );
          })}
        </ul>

        {!isAdmin && (
          <p className="mt-4 text-xs text-content-tertiary">
            Only group admins can add or remove members.
          </p>
        )}
      </Modal>

      <AddMembersModal
        conversation={conversation}
        open={adding}
        onOpenChange={setAdding}
        onAdded={() => {
          refresh();
          toast.success("Members added.");
        }}
      />
    </>
  );
}

function AddMembersModal({
  conversation,
  open,
  onOpenChange,
  onAdded,
}: {
  conversation: Conversation;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdded: () => void;
}) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const existing = new Set(conversation.participants.map((p) => p.user.id));

  const { data: contacts } = useQuery({
    queryKey: ["contacts", search],
    queryFn: () =>
      api.get<Contact[]>(`/contacts${search ? `?q=${encodeURIComponent(search)}` : ""}`),
    enabled: open,
  });

  // People already in the group are filtered out rather than shown disabled:
  // offering an action that cannot do anything is noise.
  const candidates: UserPublic[] = (contacts ?? [])
    .map((contact) => contact.user)
    .filter((person) => !existing.has(person.id));

  const addMembers = useMutation({
    mutationFn: () =>
      api.post<Conversation>(`/conversations/${conversation.id}/participants`, {
        user_ids: selected,
      }),
    onSuccess: () => {
      onAdded();
      setSelected([]);
      setSearch("");
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not add those members."),
  });

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Add members"
      footer={
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-content-secondary">{selected.length} selected</span>
          <Button
            onClick={() => addMembers.mutate()}
            loading={addMembers.isPending}
            disabled={selected.length === 0}
          >
            Add
          </Button>
        </div>
      }
    >
      <div className="relative mb-3">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-content-tertiary"
          aria-hidden="true"
        />
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search contacts"
          aria-label="Search contacts"
          className="w-full rounded-full bg-surface-hover py-2 pl-9 pr-3 text-sm text-content-primary outline-none placeholder:text-content-tertiary focus:ring-1 focus:ring-accent"
        />
      </div>

      {candidates.length === 0 ? (
        <p className="py-8 text-center text-sm text-content-secondary">
          Everyone in your contacts is already in this group.
        </p>
      ) : (
        <ul className="space-y-0.5">
          {candidates.map((person) => {
            const isSelected = selected.includes(person.id);
            return (
              <li key={person.id}>
                <button
                  onClick={() =>
                    setSelected((current) =>
                      current.includes(person.id)
                        ? current.filter((id) => id !== person.id)
                        : [...current, person.id],
                    )
                  }
                  aria-pressed={isSelected}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors",
                    isSelected ? "bg-surface-hover" : "hover:bg-surface-hover",
                  )}
                >
                  <Avatar name={person.display_name} color={person.avatar_color} />
                  <span className="min-w-0 flex-1 truncate font-medium text-content-primary">
                    {person.display_name}
                  </span>
                  {isSelected && <span className="shrink-0 text-sm text-accent">Selected</span>}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Modal>
  );
}
