"use client";

import { FileText, Loader2, Paperclip, Send, Smile, X } from "lucide-react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";

import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fileSize } from "@/lib/format";
import type { Attachment, Message } from "@/lib/types";
import { realtime } from "@/lib/ws";

interface ComposerProps {
  conversationId: string;
  replyTo: Message | null;
  onCancelReply: () => void;
  onSend: (body: string, attachmentIds: string[]) => void;
}

/** How long after the last keystroke we consider the user to have stopped. */
const TYPING_IDLE_MS = 3000;

/** Mirrors the server's limit, so an oversized file fails instantly rather than
 *  after a full upload. The server still enforces it — this is only courtesy. */
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const MAX_ATTACHMENTS = 10;

export function Composer({ conversationId, replyTo, onCancelReply, onSend }: ComposerProps) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
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

  /** Upload happens before send, so a failed upload never loses the message. */
  async function attach(files: FileList | null) {
    if (!files || files.length === 0) return;
    const room = MAX_ATTACHMENTS - pending.length;
    if (room <= 0) {
      toast.error(`You can attach at most ${MAX_ATTACHMENTS} files to one message.`);
      return;
    }

    for (const file of Array.from(files).slice(0, room)) {
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error(`${file.name} is larger than ${fileSize(MAX_UPLOAD_BYTES)}.`);
        continue;
      }
      setUploading((count) => count + 1);
      try {
        const form = new FormData();
        form.append("file", file);
        const uploaded = await api.upload<Attachment>("/attachments", form);
        setPending((current) => [...current, uploaded]);
      } catch {
        toast.error(`${file.name} could not be uploaded.`);
      } finally {
        setUploading((count) => count - 1);
      }
    }
  }

  function submit() {
    const body = value.trim();
    // A message may be media-only; requiring text would make the tray useless.
    if (!body && pending.length === 0) return;

    if (typingRef.current) {
      realtime.send("typing.stop", { conversation_id: conversationId });
      typingRef.current = false;
    }
    onSend(
      body,
      pending.map((attachment) => attachment.id),
    );
    setValue("");
    setPending([]);
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

      {(pending.length > 0 || uploading > 0) && (
        <div className="mb-2 flex flex-wrap gap-2">
          {pending.map((attachment) => (
            <div
              key={attachment.id}
              className="group relative flex items-center gap-2 rounded-lg border border-edge-subtle bg-surface-hover p-1 pr-2"
            >
              {attachment.content_type.startsWith("image/") ? (
                <Image
                  src={attachment.url}
                  alt=""
                  width={40}
                  height={40}
                  // Attachment hosts are user-configured, so the optimiser
                  // cannot be pointed at them without whitelisting every origin.
                  unoptimized
                  className="h-10 w-10 rounded object-cover"
                />
              ) : (
                <FileText className="h-10 w-10 p-2 text-content-secondary" strokeWidth={1.5} />
              )}
              <span className="max-w-[10rem] truncate text-xs text-content-secondary">
                {attachment.file_name}
              </span>
              <button
                onClick={() =>
                  setPending((current) => current.filter((item) => item.id !== attachment.id))
                }
                aria-label={`Remove ${attachment.file_name}`}
                className="rounded-full p-0.5 text-content-tertiary hover:bg-surface-active"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
          {uploading > 0 && (
            <div className="flex items-center gap-2 rounded-lg border border-edge-subtle px-3 py-2 text-xs text-content-secondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              Uploading {uploading}…
            </div>
          )}
        </div>
      )}

      <div className="flex items-end gap-2">
        <input
          ref={fileRef}
          type="file"
          multiple
          accept="image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain"
          className="hidden"
          onChange={(event) => {
            void attach(event.target.files);
            // Reset, or picking the same file twice in a row fires no change.
            event.target.value = "";
          }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          aria-label="Add attachment"
          title="Attach a file"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-content-tertiary transition-colors hover:bg-surface-hover hover:text-content-primary"
        >
          <Paperclip className="h-5 w-5" />
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
          disabled={!value.trim() && pending.length === 0}
          aria-label="Send"
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors",
            value.trim() || pending.length > 0
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
