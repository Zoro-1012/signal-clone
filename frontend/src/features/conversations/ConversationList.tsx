"use client";

import { Search, SquarePen, X } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

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

  const { data, isLoading, isError, refetch } = useConversations(deferredSearch);
  const conversations = useMemo(() => data ?? [], [data]);

  return (
    <div className="flex h-full w-full flex-col bg-surface-panel md:w-list md:shrink-0 md:border-r md:border-edge-subtle">
      <header className="flex h-header items-center justify-between px-4">
        <h1 className="text-xl font-bold text-content-primary">Chats</h1>
        <button
          onClick={onNewChat}
          aria-label="New chat"
          title="New chat"
          className="flex h-9 w-9 items-center justify-center rounded-full text-content-primary transition-colors hover:bg-surface-hover"
        >
          <SquarePen className="h-5 w-5" strokeWidth={1.75} />
        </button>
      </header>

      <div className="px-3 pb-2">
        <div className="relative">
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
      </div>

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
              {deferredSearch ? "No results" : "No chats"}
            </p>
            <p className="mt-1 text-sm text-content-secondary">
              {deferredSearch
                ? `Nothing matches "${deferredSearch}".`
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
