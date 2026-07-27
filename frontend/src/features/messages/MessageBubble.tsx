"use client";

import { SmilePlus, TriangleAlert } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";

import { Attachments } from "./Attachments";
import { MessageActions, type MessageActionHandlers } from "./MessageActions";
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
  /** Jump to the message this one quotes. Absent if the quote is unreachable. */
  onJumpToQuoted?: (messageId: string) => void;
  /** Briefly ringed after being jumped to, so the eye lands in the right place. */
  highlighted?: boolean;
  actions: MessageActionHandlers;
}

const QUICK_REACTIONS = ["👍", "❤️", "😂", "😮", "😢", "🙏"] as const;

/**
 * Delivery state, traced from Signal's published icon set.
 *
 * Sending is a dotted ring with nothing in it; sent is one solid ring with a
 * tick; delivered adds a second ring behind the first; read fills them both.
 * The progression is structural — a ring appears, then a second, then they
 * fill — so the states stay distinguishable at 14px and without colour, which
 * a row of bare ticks does not.
 */
function ReceiptIcon({ status }: { status: Message["status"] }) {
  const shared = "h-3.5 w-3.5 shrink-0";
  switch (status) {
    case "sending":
      return <SendingRing className={shared} aria-label="Sending" />;
    case "failed":
      return <TriangleAlert className={cn(shared, "text-signal-red")} aria-label="Failed to send" />;
    case "delivered":
      return <TickRings className={shared} doubled aria-label="Delivered" />;
    case "read":
      return <TickRings className={shared} doubled filled aria-label="Read" />;
    default:
      return <TickRings className={shared} aria-label="Sent" />;
  }
}

/** The dotted ring Signal shows while a message is still in flight. */
function SendingRing({ className, ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" className={className} role="img" {...rest}>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray="0.5 4"
      />
    </svg>
  );
}

/**
 * Signal's ticked ring, optionally with a second ring behind it.
 *
 * The front ring carries a fill even when the icon reads as an outline: it has
 * to mask the ring behind it, or the two overlap into a figure-of-eight instead
 * of one disc in front of another.
 */
function TickRings({
  doubled = false,
  filled = false,
  className,
  ...rest
}: {
  doubled?: boolean;
  filled?: boolean;
  className?: string;
} & React.SVGProps<SVGSVGElement>) {
  const mask = "var(--receipt-knockout)";
  return (
    <svg viewBox="0 0 24 24" className={className} role="img" {...rest}>
      {doubled && (
        <circle
          cx="8.5"
          cy="12"
          r="6.5"
          fill={filled ? "currentColor" : mask}
          stroke="currentColor"
          strokeWidth="1.75"
        />
      )}
      <circle
        cx={doubled ? 14.5 : 12}
        cy="12"
        r="6.5"
        fill={filled ? "currentColor" : mask}
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <path
        d={doubled ? "M11.6 12.2l2 2 3.8-4.2" : "M9.1 12.2l2 2 3.8-4.2"}
        fill="none"
        stroke={filled ? mask : "currentColor"}
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** The dotted ring with a bar that Signal uses to mark a timed message. */
function DisappearingGlyph({ className, ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" className={className} role="img" {...rest}>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray="0.5 4"
      />
      <path
        d="M12 7.5v5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function MessageBubble({
  message,
  isOwn,
  isGroup,
  grouped,
  tail,
  onReact,
  onReply,
  onJumpToQuoted,
  highlighted = false,
  actions,
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
            highlighted && "ring-2 ring-accent ring-offset-2 ring-offset-surface-base",
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
            <button
              type="button"
              // A quote is a reference, so it should behave like one. Clicking it
              // scrolls the original into view rather than being decorative.
              onClick={() => onJumpToQuoted?.(message.reply_to!.id)}
              disabled={!onJumpToQuoted || message.reply_to.is_deleted}
              aria-label={
                message.reply_to.is_deleted
                  ? "The quoted message was deleted"
                  : `Go to the quoted message from ${message.reply_to.sender_display_name ?? "Unknown"}`
              }
              className={cn(
                "mb-1.5 block w-full rounded border-l-[3px] px-2 py-1 text-left text-sm transition-opacity",
                isOwn ? "border-white/70 bg-white/15" : "border-accent bg-black/5 dark:bg-white/10",
                "enabled:hover:opacity-80",
              )}
            >
              <p className="font-medium opacity-90">
                {message.reply_to.sender_display_name ?? "Unknown"}
              </p>
              <p className="truncate opacity-75">
                {message.reply_to.is_deleted ? "Message deleted" : message.reply_to.preview}
              </p>
            </button>
          )}

          {!deleted && message.attachments.length > 0 && (
            <Attachments attachments={message.attachments} isOwn={isOwn} />
          )}

          {/* Signal puts the timestamp and receipt inside the bubble, trailing the
              text. Laid out as a wrapping flex row rather than absolutely
              positioned: an absolute meta block has no width in the text's
              layout, so a line that ends near the right edge runs underneath it.
              Wrapping means a long final line simply pushes the meta onto its
              own line instead of colliding. */}
          <div className="flex flex-wrap items-end justify-end gap-x-2">
            {(deleted || message.body) && (
              <p className="min-w-0 whitespace-pre-wrap break-words text-[15px] leading-snug">
                {deleted ? "This message was deleted" : message.body}
              </p>
            )}
            <span
              className={cn(
                "flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] leading-5",
                isOwn ? "text-white/70" : "text-content-tertiary",
              )}
            >
              {message.edited_at && <span className="italic">edited</span>}
              {message.expires_at && (
                <DisappearingGlyph className="h-3.5 w-3.5" aria-label="Disappearing message" />
              )}
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
          hover-only affordance would not be. Ordered "…", reply, react — and
          mirrored for your own messages so the row always sits on the outside
          of the bubble rather than crossing over the transcript. */}
      {!deleted && (
        <div
          className={cn(
            "flex items-center gap-0.5 self-center opacity-0 transition-opacity",
            "group-hover:opacity-100 group-focus-within:opacity-100",
            isOwn && "order-first",
          )}
        >
          <MessageActions message={message} isOwn={isOwn} handlers={actions} />

          <button
            onClick={() => onReply(message)}
            aria-label="Reply"
            title="Reply"
            className="rounded-full p-1.5 text-content-tertiary transition-colors hover:bg-surface-hover hover:text-content-primary"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 17l-6-6 6-6" />
              <path d="M3 11h11a6 6 0 016 6v2" />
            </svg>
          </button>

          <details className="group/menu relative">
            <summary
              className="cursor-pointer list-none rounded-full p-1.5 text-content-tertiary transition-colors hover:bg-surface-hover hover:text-content-primary"
              aria-label="React"
              title="React"
            >
              <SmilePlus className="h-4 w-4" />
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
      )}
    </div>
  );
}
