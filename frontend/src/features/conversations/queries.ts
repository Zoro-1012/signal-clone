"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/lib/api";
import type { Conversation } from "@/lib/types";
import { realtime, type Frame } from "@/lib/ws";

export const conversationKeys = {
  all: ["conversations"] as const,
  list: (query: string) => ["conversations", { query }] as const,
};

export function useConversations(query: string) {
  return useQuery({
    queryKey: conversationKeys.list(query),
    queryFn: () =>
      api.get<Conversation[]>(
        `/conversations${query ? `?q=${encodeURIComponent(query)}` : ""}`,
      ),
    // Keeps the previous list on screen while a search request is in flight, so
    // typing does not blank the pane on every keystroke.
    placeholderData: (previous) => previous,
  });
}

/**
 * Keep the conversation list live.
 *
 * Rather than patching cached rows field by field for each event — which means
 * re-deriving unread counts, previews and ordering on the client and getting
 * them subtly wrong — this invalidates the list and lets the server recompute.
 * The list is four queries and small; correctness is worth more than saving it.
 */
export function useConversationRealtime() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const relevant = new Set([
      "message.new",
      "message.deleted",
      "message.status",
      "conversation.updated",
      "presence.update",
    ]);

    return realtime.onFrame((frame: Frame) => {
      if (relevant.has(frame.type)) {
        void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
      }
    });
  }, [queryClient]);
}
