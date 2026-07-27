"use client";

import { Download, FileText, X } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import { cn } from "@/lib/cn";
import { fileSize } from "@/lib/format";
import type { Attachment } from "@/lib/types";

function isImage(attachment: Attachment): boolean {
  return attachment.content_type.startsWith("image/");
}

/**
 * Media and file attachments inside a bubble.
 *
 * Images render inline with their intrinsic aspect ratio reserved, so the
 * transcript does not jump as they load — the backend stores width and height
 * on upload precisely so the client can do this. Non-images become a file card,
 * because a broken image frame reads as an error rather than as a document.
 */
export function Attachments({ attachments, isOwn }: { attachments: Attachment[]; isOwn: boolean }) {
  const [lightbox, setLightbox] = useState<Attachment | null>(null);
  if (attachments.length === 0) return null;

  return (
    <>
      <div className={cn("mb-1 flex flex-col gap-1", attachments.length > 1 && "grid grid-cols-2")}>
        {attachments.map((attachment) =>
          isImage(attachment) ? (
            <button
              key={attachment.id}
              onClick={() => setLightbox(attachment)}
              aria-label={`Open ${attachment.file_name}`}
              className="overflow-hidden rounded-xl"
            >
              <Image
                src={attachment.url}
                alt={attachment.file_name}
                width={attachment.width ?? 480}
                height={attachment.height ?? 360}
                className="h-auto max-h-80 w-full object-cover"
                // Attachment hosts are user-configured, so Next's optimiser
                // cannot be pointed at them without whitelisting every origin.
                unoptimized
              />
            </button>
          ) : (
            <a
              key={attachment.id}
              href={attachment.url}
              download={attachment.file_name}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 transition-colors",
                isOwn ? "bg-white/15 hover:bg-white/25" : "bg-black/5 hover:bg-black/10 dark:bg-white/10",
              )}
            >
              <FileText className="h-8 w-8 shrink-0 opacity-80" strokeWidth={1.5} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{attachment.file_name}</span>
                <span className="block text-xs opacity-70">{fileSize(attachment.size_bytes)}</span>
              </span>
              <Download className="h-4 w-4 shrink-0 opacity-70" />
            </a>
          ),
        )}
      </div>

      {lightbox && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={lightbox.file_name}
          onClick={() => setLightbox(null)}
          onKeyDown={(event) => event.key === "Escape" && setLightbox(null)}
          className="fixed inset-0 z-modal flex items-center justify-center bg-black/85 p-8 animate-fade-in"
        >
          <button
            onClick={() => setLightbox(null)}
            aria-label="Close"
            className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
          >
            <X className="h-6 w-6" />
          </button>
          <Image
            src={lightbox.url}
            alt={lightbox.file_name}
            width={lightbox.width ?? 1200}
            height={lightbox.height ?? 900}
            className="max-h-full w-auto max-w-full object-contain"
            unoptimized
          />
        </div>
      )}
    </>
  );
}
