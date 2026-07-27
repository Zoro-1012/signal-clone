"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { CheckCheck, ListFilter, Menu, MoreHorizontal, Search, Settings, SquarePen, Users, X } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { UserPrivate } from "@/lib/types";
import { useUi } from "@/stores/ui";

import { ConversationRow } from "./ConversationRow";
import { useConversations } from "./queries";

interface ConversationListProps {
  user: UserPrivate;
  onNewChat: () => void;
}

export function ConversationList({ user, onNewChat }: ConversationListProps) {
  const [search, setSearch] = useState("");
  // The input stays perfectly responsive while the (heavier) filtered list
  // re-renders at a lower priority. Typing never stutters.
  const deferredSearch = useDeferredValue(search);

  const activeId = useUi((s) => s.activeConversationId);
  const openConversation = useUi((s) => s.openConversation);
  const toggleRail = useUi((s) => s.toggleRail);
  const railVisible = useUi((s) => s.railVisible);
  const unreadOnly = useUi((s) => s.unreadOnly);
  const setUnreadOnly = useUi((s) => s.setUnreadOnly);
  const setNavTab = useUi((s) => s.setNavTab);
  const toast = useToast();

  const { data, isLoading, isError, refetch } = useConversations(deferredSearch);
  const all = useMemo(() => data ?? [], [data]);
  // Filtering client-side: the list is already loaded in full, so a round trip
  // would only add latency to a toggle that should feel instant.
  const conversations = useMemo(
    () => (unreadOnly ? all.filter((conversation) => conversation.unread_count > 0) : all),
    [all, unreadOnly],
  );

  /**
   * Clear every unread badge at once.
   *
   * The read watermark is per-conversation and anchored to a message, so this
   * is a fan-out of the same call the chat pane makes rather than a bulk
   * endpoint — there is no separate server concept of "all read" to invoke.
   */
  async function markAllRead() {
    const unread = all.filter(
      (conversation) => conversation.unread_count > 0 && conversation.last_message,
    );
    if (unread.length === 0) {
      toast.info("Nothing unread.");
      return;
    }
    await Promise.allSettled(
      unread.map((conversation) =>
        api.post(`/conversations/${conversation.id}/read`, {
          message_id: conversation.last_message!.id,
        }),
      ),
    );
    void refetch();
    toast.success(`Marked ${unread.length} ${unread.length === 1 ? "chat" : "chats"} as read.`);
  }

  return (
    <div className="flex h-full w-full flex-col bg-surface-panel md:w-list md:shrink-0 md:border-r md:border-edge-subtle">
      <header className="flex h-header items-center gap-1 px-3">
        {/* Collapses the nav rail, as Signal's "Hide tabs" does. Desktop only:
            on a phone the bar is the only navigation there is. */}
        <button
          onClick={toggleRail}
          aria-label={railVisible ? "Hide tabs" : "Show tabs"}
          aria-pressed={!railVisible}
          title={railVisible ? "Hide tabs" : "Show tabs"}
          className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full text-content-primary transition-colors hover:bg-surface-hover md:flex"
        >
          <Menu className="h-5 w-5" strokeWidth={1.75} />
        </button>

        <h1 className="flex-1 px-1 text-xl font-bold text-content-primary">Chats</h1>

        <button
          onClick={onNewChat}
          aria-label="New chat"
          title="New chat"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-content-primary transition-colors hover:bg-surface-hover"
        >
          <SquarePen className="h-5 w-5" strokeWidth={1.75} />
        </button>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              aria-label="More options"
              title="More options"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-content-primary transition-colors hover:bg-surface-hover"
            >
              <MoreHorizontal className="h-5 w-5" strokeWidth={1.75} />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={6}
              className="z-context-menu min-w-48 rounded-2xl border border-edge-subtle bg-surface-raised p-1.5 shadow-lg animate-fade-in"
            >
              {[
                { key: "group", label: "New group", icon: <Users className="h-4 w-4" />, run: onNewChat },
                {
                  key: "read",
                  label: "Mark all read",
                  icon: <CheckCheck className="h-4 w-4" />,
                  run: () => void markAllRead(),
                },
                {
                  key: "settings",
                  label: "Settings",
                  icon: <Settings className="h-4 w-4" />,
                  run: () => setNavTab("settings"),
                },
              ].map((item) => (
                <DropdownMenu.Item
                  key={item.key}
                  onSelect={item.run}
                  className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm text-content-primary outline-none data-[highlighted]:bg-surface-hover"
                >
                  {item.icon}
                  {item.label}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </header>

      <div className="flex items-center gap-2 px-3 pb-2">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-content-tertiary"
            aria-hidden="true"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search"
            aria-label="Search conversations"
            className="w-full rounded-full bg-surface-hover py-2 pl-9 pr-9 text-sm text-content-primary outline-none placeholder:text-content-tertiary focus:ring-1 focus:ring-accent"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-content-tertiary hover:bg-surface-active"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Signal's filter is a single toggle: unread only. Rendered pressed
            rather than as a menu, so its state is visible without opening it. */}
        <button
          onClick={() => setUnreadOnly(!unreadOnly)}
          aria-label={unreadOnly ? "Show all chats" : "Show unread chats only"}
          aria-pressed={unreadOnly}
          title={unreadOnly ? "Showing unread only" : "Filter by unread"}
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors",
            unreadOnly
              ? "bg-accent text-content-on-accent"
              : "text-content-primary hover:bg-surface-hover",
          )}
        >
          <ListFilter className="h-5 w-5" strokeWidth={1.75} />
        </button>
      </div>

      {unreadOnly && (
        <button
          onClick={() => setUnreadOnly(false)}
          className="mx-3 mb-2 rounded-lg bg-surface-hover px-3 py-1.5 text-left text-xs text-content-secondary hover:bg-surface-active"
        >
          Filtered by unread · <span className="font-medium text-accent">Clear</span>
        </button>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {isLoading && <ListSkeleton />}

        {isError && (
          <div className="px-4 py-10 text-center">
            <p className="text-sm text-content-secondary">Could not load your chats.</p>
            <button
              onClick={() => void refetch()}
              className="mt-3 text-sm font-medium text-accent hover:underline"
            >
              Try again
            </button>
          </div>
        )}

        {!isLoading && !isError && conversations.length === 0 && (
          <div className="px-6 py-16 text-center">
            <p className="font-semibold text-content-primary">
              {deferredSearch ? "No results" : unreadOnly ? "Nothing unread" : "No chats"}
            </p>
            <p className="mt-1 text-sm text-content-secondary">
              {deferredSearch
                ? `Nothing matches "${deferredSearch}".`
                : unreadOnly
                  ? "You are all caught up."
                  : "Recent chats will appear here."}
            </p>
          </div>
        )}

        <div
          className={cn(
            "space-y-0.5",
            // Dims the list while a new search resolves, so stale results are
            // visibly stale instead of silently wrong.
            search !== deferredSearch && "opacity-60",
          )}
        >
          {conversations.map((conversation) => (
            <ConversationRow
              key={conversation.id}
              conversation={conversation}
              isActive={conversation.id === activeId}
              currentUserId={user.id}
              onSelect={openConversation}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/** Skeleton rows sized to the real ones, so the layout does not jump on load. */
function ListSkeleton() {
  return (
    <div className="space-y-0.5" aria-hidden="true">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="flex items-center gap-3 px-3 py-2.5">
          <div className="h-12 w-12 shrink-0 animate-pulse rounded-full bg-surface-hover" />
          <div className="flex-1 space-y-2">
            <div className="h-3.5 w-1/3 animate-pulse rounded bg-surface-hover" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-surface-hover" />
          </div>
        </div>
      ))}
    </div>
  );
}
