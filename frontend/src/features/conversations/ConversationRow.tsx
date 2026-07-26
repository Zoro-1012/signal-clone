"use client";

import { CheckCheck } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";
import { cn } from "@/lib/cn";
import { conversationTime } from "@/lib/format";
import type { Conversation } from "@/lib/types";

interface ConversationRowProps {
  conversation: Conversation;
  isActive: boolean;
  currentUserId: string;
  onSelect: (id: string) => void;
}

/** Renders the system event as a sentence, since the server sends structure. */
function systemPreview(event: string | null): string {
  switch (event) {
    case "group_created":
      return "Group created";
    case "members_added":
      return "Members added";
    case "member_removed":
      return "Member removed";
    case "member_left":
      return "Member left";
    case "group_renamed":
      return "Group renamed";
    case "disappearing_timer_changed":
      return "Disappearing messages updated";
    default:
      return "Updated";
  }
}

export function ConversationRow({
  conversation,
  isActive,
  currentUserId,
  onSelect,
}: ConversationRowProps) {
  const last = conversation.last_message;
  const isGroup = conversation.type === "group";

  // In a direct chat the other participant carries the presence dot; a group has
  // no single person to represent, so it shows none.
  const other = conversation.participants.find((p) => p.user.id !== currentUserId);

  const sentByMe = last?.sender_id === currentUserId;
  let preview = "";
  if (last) {
    if (last.is_deleted) preview = "This message was deleted";
    else if (last.type === "system") preview = systemPreview(last.system_event);
    else if (last.preview) preview = last.preview;
    else preview = "Attachment";

    // Group previews name the speaker, because the avatar is the group's.
    if (isGroup && last.type !== "system") {
      preview = `${sentByMe ? "You" : (last.sender_display_name ?? "")}: ${preview}`;
    }
  }

  return (
    <button
      type="button"
      onClick={() => onSelect(conversation.id)}
      // aria-current tells assistive tech which row is open; the grey fill only
      // communicates that visually.
      aria-current={isActive ? "true" : undefined}
      className={cn(
        "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors",
        isActive ? "bg-surface-active" : "hover:bg-surface-hover",
      )}
    >
      <Avatar
        name={conversation.name ?? "Conversation"}
        color={conversation.avatar_color}
        src={conversation.avatar_url}
        size="md"
        online={!isGroup && other?.user.is_online}
      />

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate font-medium text-content-primary">
            {conversation.name ?? "Unknown"}
          </span>
          <span
            className={cn(
              "shrink-0 text-xs",
              conversation.unread_count > 0 ? "text-accent" : "text-content-tertiary",
            )}
          >
            {conversationTime(conversation.last_message_at)}
          </span>
        </div>

        <div className="mt-0.5 flex items-center gap-1.5">
          {/* Receipt glyphs appear only on your own messages — you cannot have a
              read receipt for someone else's. */}
          {sentByMe && last && !last.is_deleted && last.type !== "system" && (
            <ReceiptGlyph />
          )}
          <span className="min-w-0 flex-1 truncate text-sm text-content-secondary">
            {preview}
          </span>
          {conversation.unread_count > 0 && (
            <span
              className="ml-1 shrink-0 rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-content-on-accent"
              aria-label={`${conversation.unread_count} unread messages`}
            >
              {conversation.unread_count > 99 ? "99+" : conversation.unread_count}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

/**
 * The list preview does not carry per-message receipt counts, so it shows a
 * single delivered glyph. The precise sent/delivered/read distinction is drawn
 * in the transcript, where the data to justify it exists.
 */
function ReceiptGlyph() {
  return <CheckCheck className="h-4 w-4 shrink-0 text-content-tertiary" aria-hidden="true" />;
}
