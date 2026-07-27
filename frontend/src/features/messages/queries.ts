"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/lib/api";
import type { CursorPage, Message } from "@/lib/types";
import { realtime, type Frame } from "@/lib/ws";
import { conversationKeys } from "@/features/conversations/queries";

export const messageKeys = {
  all: ["messages"] as const,
  thread: (conversationId: string) => ["messages", conversationId] as const,
};

/**
 * Transcript history, paged backwards.
 *
 * The API returns newest-first pages; the UI renders oldest-first, so pages are
 * flattened and reversed once here rather than in every consumer.
 */
export function useMessages(conversationId: string | null) {
  return useInfiniteQuery({
    queryKey: messageKeys.thread(conversationId ?? "none"),
    enabled: Boolean(conversationId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      api.get<CursorPage<Message>>(
        `/conversations/${conversationId}/messages?limit=40${
          pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""
        }`,
      ),
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    select: (data) => ({
      ...data,
      // Pages arrive newest-first and each page is itself newest-first, so both
      // levels need reversing to produce a chronological transcript.
      ordered: [...data.pages].reverse().flatMap((page) => [...page.items].reverse()),
    }),
  });
}

interface SendVariables {
  conversationId: string;
  body: string;
  replyToId?: string | null;
  clientMessageId: string;
  attachmentIds?: string[];
}

/**
 * Send a message, showing it immediately.
 *
 * The optimistic row carries the same `client_message_id` the server will echo
 * back, which is what lets the socket's `message.new` frame replace it instead
 * of appending a duplicate. The backend enforces the same key, so even a network
 * retry produces one message.
 */
export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      conversationId,
      body,
      replyToId,
      clientMessageId,
      attachmentIds,
    }: SendVariables) =>
      api.post<Message>(`/conversations/${conversationId}/messages`, {
        body,
        reply_to_message_id: replyToId ?? null,
        client_message_id: clientMessageId,
        attachment_ids: attachmentIds ?? [],
      }),

    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({
        queryKey: messageKeys.thread(variables.conversationId),
      });
      void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
    },
  });
}

export function useToggleReaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, emoji }: { messageId: string; emoji: string }) =>
      api.post<Message>(`/messages/${messageId}/reactions`, { emoji }),
    onSuccess: (message) => {
      void queryClient.invalidateQueries({
        queryKey: messageKeys.thread(message.conversation_id),
      });
    },
  });
}

export function useDeleteMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) => api.delete<void>(`/messages/${messageId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: messageKeys.thread(conversationId) });
      void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
    },
  });
}

/** Push transcript updates into the cache as they arrive. */
export function useMessageRealtime(conversationId: string | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!conversationId) return;

    return realtime.onFrame((frame: Frame) => {
      const payload = frame.payload as { conversation_id?: string };
      if (payload.conversation_id !== conversationId) return;

      if (
        frame.type === "message.new" ||
        frame.type === "message.updated" ||
        frame.type === "message.deleted" ||
        frame.type === "message.status" ||
        frame.type === "reaction.added" ||
        frame.type === "reaction.removed"
      ) {
        void queryClient.invalidateQueries({ queryKey: messageKeys.thread(conversationId) });
      }
    });
  }, [conversationId, queryClient]);
}

/** Mark the newest message read, and tell the server what arrived. */
export function useReadReceipts(conversationId: string | null, newestMessageId?: string) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!conversationId || !newestMessageId) return;

    // Acknowledging delivery first is what starts disappearing-message timers,
    // which the server deliberately begins on delivery rather than on send.
    const run = async () => {
      try {
        await api.post(`/conversations/${conversationId}/delivered`);
        await api.post(
          `/conversations/${conversationId}/messages/${newestMessageId}/read`,
        );
        void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
      } catch {
        // Receipts are best-effort. Failing to record one must never block
        // reading the conversation.
      }
    };
    void run();
  }, [conversationId, newestMessageId, queryClient]);
}
