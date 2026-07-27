"use client";

import { Check, CheckCheck, Clock, Trash2, TriangleAlert } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";
import { avatarPalette } from "@/lib/avatars";
import { cn } from "@/lib/cn";
import { messageTime } from "@/lib/format";
import type { Message } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
  isOwn: boolean;
  isGroup: boolean;
  /** Part of a run from the same sender, so the avatar and name are omitted. */
  grouped: boolean;
  /** Last of a run, so it gets the tail. */
  tail: boolean;
  onReact: (messageId: string, emoji: string) => void;
  onReply: (message: Message) => void;
  /** Only offered for your own messages — the server enforces the same rule. */
  onDelete?: (messageId: string) => void;
}

const QUICK_REACTIONS = ["👍", "❤️", "😂", "😮", "😢", "🙏"] as const;

/**
 * Delivery state, drawn the way Signal draws it.
 *
 * One tick sent, two ticks delivered, two accent ticks read. The value is
 * derived server-side from per-recipient receipts, so in a group it only reaches
 * "read" once everyone has read it.
 */
function ReceiptIcon({ status }: { status: Message["status"] }) {
  const shared = "h-3.5 w-3.5 shrink-0";
  switch (status) {
    case "sending":
      return <Clock className={cn(shared, "opacity-60")} aria-label="Sending" />;
    case "failed":
      return <TriangleAlert className={cn(shared, "text-signal-red")} aria-label="Failed to send" />;
    case "delivered":
      return <CheckCheck className={shared} aria-label="Delivered" />;
    case "read":
      return <CheckCheck className={cn(shared, "text-signal-yellow")} aria-label="Read" />;
    default:
      return <Check className={shared} aria-label="Sent" />;
  }
}

export function MessageBubble({
  message,
  isOwn,
  isGroup,
  grouped,
  tail,
  onReact,
  onReply,
  onDelete,
}: MessageBubbleProps) {
  const deleted = message.deleted_at !== null;
  const senderColor = avatarPalette(message.sender?.avatar_color).fg;

  return (
    <div
      className={cn(
        "group flex w-full items-end gap-2 px-4",
        isOwn ? "justify-end" : "justify-start",
        grouped ? "mt-0.5" : "mt-3",
      )}
    >
      {/* The avatar column is reserved even when grouped, so a run of messages
          stays aligned instead of stepping left under the first one. */}
      {!isOwn && isGroup && (
        <div className="w-8 shrink-0">
          {tail && message.sender && (
            <Avatar name={message.sender.display_name} color={message.sender.avatar_color} size="sm" />
          )}
        </div>
      )}

      <div className={cn("flex max-w-[min(75%,32rem)] flex-col", isOwn && "items-end")}>
        <div
          className={cn(
            "relative px-3 py-2",
            isOwn ? "bg-bubble-out-bg text-bubble-out-text" : "bg-bubble-in-bg text-bubble-in-text",
            // Only the last bubble of a run gets the squared tail corner.
            tail
              ? isOwn
                ? "bubble-outgoing"
                : "bubble-incoming"
              : isOwn
                ? "bubble-grouped-outgoing"
                : "bubble-grouped-incoming",
            deleted && "italic opacity-70",
          )}
        >
          {/* Group messages name the speaker in their own avatar colour, which is
              how Signal keeps a busy group readable. */}
          {!isOwn && isGroup && !grouped && message.sender && (
            <p className="mb-0.5 text-sm font-medium" style={{ color: senderColor }}>
              {message.sender.display_name}
            </p>
          )}

          {message.reply_to && (
            <div
              className={cn(
                "mb-1.5 rounded border-l-[3px] px-2 py-1 text-sm",
                isOwn ? "border-white/70 bg-white/15" : "border-accent bg-black/5 dark:bg-white/10",
              )}
            >
              <p className="font-medium opacity-90">
                {message.reply_to.sender_display_name ?? "Unknown"}
              </p>
              <p className="truncate opacity-75">
                {message.reply_to.is_deleted ? "Message deleted" : message.reply_to.preview}
              </p>
            </div>
          )}

          {/* Signal puts the timestamp and receipt inside the bubble, trailing the
              text. Laid out as a wrapping flex row rather than absolutely
              positioned: an absolute meta block has no width in the text's
              layout, so a line that ends near the right edge runs underneath it.
              Wrapping means a long final line simply pushes the meta onto its
              own line instead of colliding. */}
          <div className="flex flex-wrap items-end justify-end gap-x-2">
            <p className="min-w-0 whitespace-pre-wrap break-words text-[15px] leading-snug">
              {deleted ? "This message was deleted" : message.body}
            </p>
            <span
              className={cn(
                "flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] leading-5",
                isOwn ? "text-white/70" : "text-content-tertiary",
              )}
            >
              {message.edited_at && <span className="italic">edited</span>}
              {messageTime(message.created_at)}
              {isOwn && !deleted && <ReceiptIcon status={message.status} />}
            </span>
          </div>

          {message.reactions.length > 0 && (
            <div
              className={cn(
                "absolute -bottom-3 flex gap-0.5 rounded-full border border-edge-subtle bg-surface-raised px-1.5 py-0.5 shadow-sm",
                isOwn ? "right-2" : "left-2",
              )}
            >
              {message.reactions.map((reaction) => (
                <button
                  key={reaction.emoji}
                  onClick={() => onReact(message.id, reaction.emoji)}
                  aria-label={`${reaction.emoji} ${reaction.count}`}
                  className={cn(
                    "flex items-center gap-0.5 rounded-full px-1 text-xs",
                    reaction.reacted_by_me && "text-accent",
                  )}
                >
                  <span>{reaction.emoji}</span>
                  {reaction.count > 1 && <span>{reaction.count}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Hover actions. focus-within keeps them reachable by keyboard, which a
          hover-only affordance would not be. */}
      {!deleted && (
        <div
          className={cn(
            "flex items-center gap-0.5 self-center opacity-0 transition-opacity",
            "group-hover:opacity-100 group-focus-within:opacity-100",
            isOwn && "order-first",
          )}
        >
          <button
            onClick={() => onReply(message)}
            aria-label="Reply"
            title="Reply"
            className="rounded-full p-1.5 text-content-tertiary hover:bg-surface-hover"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 17l-6-6 6-6" />
              <path d="M3 11h11a6 6 0 016 6v2" />
            </svg>
          </button>
          {isOwn && onDelete && (
            <button
              onClick={() => onDelete(message.id)}
              aria-label="Delete message"
              title="Delete message"
              className="rounded-full p-1.5 text-content-tertiary hover:bg-surface-hover hover:text-signal-red"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
          <div className="relative">
            <details className="group/menu">
              <summary
                className="cursor-pointer list-none rounded-full p-1.5 text-content-tertiary hover:bg-surface-hover"
                aria-label="React"
                title="React"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01" />
                </svg>
              </summary>
              <div
                className={cn(
                  "absolute bottom-full z-context-menu mb-1 flex gap-1 rounded-full border border-edge-subtle bg-surface-raised px-2 py-1.5 shadow-lg",
                  isOwn ? "right-0" : "left-0",
                )}
              >
                {QUICK_REACTIONS.map((emoji) => (
                  <button
                    key={emoji}
                    onClick={() => onReact(message.id, emoji)}
                    className="rounded-full px-1 text-lg transition-transform hover:scale-125"
                    aria-label={`React with ${emoji}`}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
