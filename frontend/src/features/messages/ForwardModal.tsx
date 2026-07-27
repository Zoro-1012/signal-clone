"use client";

import { useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useConversations } from "@/features/conversations/queries";
import { cn } from "@/lib/cn";
import type { Message } from "@/lib/types";

import { useSendMessage } from "./queries";

/**
 * Send an existing message on to another conversation.
 *
 * Forwarding sends a new message rather than referencing the original: the two
 * conversations may share no members, so a reference would either leak the
 * source thread or dangle. Attachments are not carried across for the same
 * reason the server claims them once — an attachment belongs to the message
 * that claimed it.
 */
export function ForwardModal({
  message,
  onClose,
}: {
  message: Message | null;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [sendingTo, setSendingTo] = useState<string | null>(null);
  const { data } = useConversations("");
  const send = useSendMessage();
  const toast = useToast();

  const conversations = (data ?? []).filter(
    (conversation) =>
      conversation.is_active_member &&
      conversation.id !== message?.conversation_id &&
      (conversation.name ?? "").toLowerCase().includes(query.trim().toLowerCase()),
  );

  function forward(conversationId: string, name: string) {
    if (!message?.body) return;
    setSendingTo(conversationId);
    send.mutate(
      {
        conversationId,
        body: message.body,
        clientMessageId: crypto.randomUUID(),
      },
      {
        onSuccess: () => {
          toast.success(`Forwarded to ${name}.`);
          onClose();
        },
        onError: () => toast.error("Could not forward that message."),
        onSettled: () => setSendingTo(null),
      },
    );
  }

  return (
    <Modal
      open={message !== null}
      onOpenChange={(open) => !open && onClose()}
      title="Forward to"
      description="Choose a conversation to forward this message to."
    >
      <div className="space-y-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search"
          aria-label="Search conversations"
        />
        <div className="max-h-72 space-y-1 overflow-y-auto">
          {conversations.length === 0 && (
            <p className="px-1 py-4 text-center text-sm text-content-secondary">
              No other conversations to forward to.
            </p>
          )}
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              onClick={() => forward(conversation.id, conversation.name ?? "that chat")}
              disabled={sendingTo !== null}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors",
                "enabled:hover:bg-surface-hover disabled:opacity-50",
              )}
            >
              <Avatar
                name={conversation.name ?? "Conversation"}
                color={conversation.avatar_color}
                src={conversation.avatar_url}
                size="sm"
              />
              <span className="min-w-0 flex-1 truncate text-sm text-content-primary">
                {conversation.name}
              </span>
              {sendingTo === conversation.id && (
                <span className="text-xs text-content-secondary">Sending…</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </Modal>
  );
}
