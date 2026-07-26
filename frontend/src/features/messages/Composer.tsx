"use client";

import { Plus, Send, Smile, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import type { Message } from "@/lib/types";
import { realtime } from "@/lib/ws";

interface ComposerProps {
  conversationId: string;
  replyTo: Message | null;
  onCancelReply: () => void;
  onSend: (body: string) => void;
}

/** How long after the last keystroke we consider the user to have stopped. */
const TYPING_IDLE_MS = 3000;

export function Composer({ conversationId, replyTo, onCancelReply, onSend }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typingRef = useRef(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Focus the composer when a reply starts, so the user does not have to click
  // back into it after choosing what to quote.
  useEffect(() => {
    if (replyTo) textareaRef.current?.focus();
  }, [replyTo]);

  // Stop the typing indicator when the conversation changes or the composer
  // unmounts; otherwise the other person is told you are still typing in a
  // conversation you have left.
  useEffect(() => {
    return () => {
      if (typingRef.current) {
        realtime.send("typing.stop", { conversation_id: conversationId });
        typingRef.current = false;
      }
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, [conversationId]);

  function signalTyping() {
    // Sent once per burst rather than per keystroke: the server expires stale
    // indicators on read, so a frame per character would be pure waste.
    if (!typingRef.current) {
      realtime.send("typing.start", { conversation_id: conversationId });
      typingRef.current = true;
    }
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      realtime.send("typing.stop", { conversation_id: conversationId });
      typingRef.current = false;
    }, TYPING_IDLE_MS);
  }

  function submit() {
    const body = value.trim();
    if (!body) return;

    if (typingRef.current) {
      realtime.send("typing.stop", { conversation_id: conversationId });
      typingRef.current = false;
    }
    onSend(body);
    setValue("");
    // Reset the auto-grow height, or the box stays tall after a long message.
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  return (
    <div className="border-t border-edge-subtle bg-surface-panel px-4 py-3">
      {replyTo && (
        <div className="mb-2 flex items-start gap-2 rounded-lg border-l-[3px] border-accent bg-surface-hover px-3 py-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-accent">
              {replyTo.sender?.display_name ?? "Unknown"}
            </p>
            <p className="truncate text-sm text-content-secondary">{replyTo.body}</p>
          </div>
          <button
            onClick={onCancelReply}
            aria-label="Cancel reply"
            className="rounded-full p-1 text-content-tertiary hover:bg-surface-active"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex items-end gap-2">
        <button
          aria-label="Add attachment"
          title="Attachments are not enabled in this build"
          disabled
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-content-tertiary disabled:opacity-40"
        >
          <Plus className="h-5 w-5" />
        </button>

        <div className="flex min-w-0 flex-1 items-end rounded-2xl bg-surface-hover px-3 py-2">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            placeholder="Message"
            aria-label="Message"
            onChange={(event) => {
              setValue(event.target.value);
              signalTyping();
              // Auto-grow up to a cap, after which the textarea scrolls rather
              // than pushing the transcript off screen.
              const el = event.target;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
            }}
            onKeyDown={(event) => {
              // Enter sends, Shift+Enter breaks the line — the convention every
              // messenger uses, and the one users' fingers already expect.
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            className="max-h-40 w-full resize-none bg-transparent text-[15px] leading-snug text-content-primary outline-none placeholder:text-content-tertiary"
          />
          <button
            aria-label="Emoji"
            title="Emoji picker is not enabled in this build"
            disabled
            className="ml-2 shrink-0 text-content-tertiary disabled:opacity-40"
          >
            <Smile className="h-5 w-5" />
          </button>
        </div>

        <button
          onClick={submit}
          disabled={!value.trim()}
          aria-label="Send"
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors",
            value.trim()
              ? "bg-accent text-content-on-accent hover:bg-accent-hover"
              : "text-content-tertiary",
          )}
        >
          <Send className="h-[18px] w-[18px]" />
        </button>
      </div>
    </div>
  );
}
