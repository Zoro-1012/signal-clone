"use client";

import { format } from "date-fns";

import { Avatar } from "@/components/ui/Avatar";
import { Modal } from "@/components/ui/Modal";
import type { Message } from "@/lib/types";

import { useMessageInfo } from "./queries";

/**
 * Expands a message's single summary tick into per-recipient detail.
 *
 * The bubble can only show one status, and in a group that is necessarily the
 * weakest link — "delivered" until the last person reads it. That hides
 * something people reasonably want to know, so this shows the rows the summary
 * was computed from.
 */
export function MessageInfoModal({
  message,
  onClose,
}: {
  message: Message | null;
  onClose: () => void;
}) {
  const { data, isLoading, isError } = useMessageInfo(message?.id ?? null);

  return (
    <Modal open={message !== null} onOpenChange={(open) => !open && onClose()} title="Message info">
      {message && (
        <div className="space-y-4">
          <p className="rounded-xl bg-surface-hover px-3 py-2 text-sm text-content-primary">
            {message.body || "Attachment"}
          </p>

          <dl className="flex justify-between text-sm">
            <dt className="text-content-secondary">Sent</dt>
            <dd className="text-content-primary">
              {format(new Date(message.created_at), "d MMM yyyy, HH:mm")}
            </dd>
          </dl>

          {isLoading && <p className="text-sm text-content-secondary">Loading…</p>}
          {isError && (
            <p className="text-sm text-signal-red">Delivery details could not be loaded.</p>
          )}

          {data && (
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-content-tertiary">
                {data.recipients.length === 1 ? "Recipient" : "Recipients"}
              </p>
              {data.recipients.map((recipient) => (
                <div key={recipient.user.id} className="flex items-center gap-3">
                  <Avatar
                    name={recipient.user.display_name}
                    color={recipient.user.avatar_color}
                    src={recipient.user.avatar_url}
                    size="sm"
                  />
                  <span className="min-w-0 flex-1 truncate text-sm text-content-primary">
                    {recipient.user.display_name}
                  </span>
                  <span className="text-right text-xs text-content-secondary">
                    {recipient.read_at ? (
                      <>Read {format(new Date(recipient.read_at), "HH:mm")}</>
                    ) : recipient.delivered_at ? (
                      <>Delivered {format(new Date(recipient.delivered_at), "HH:mm")}</>
                    ) : (
                      "Not delivered yet"
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
