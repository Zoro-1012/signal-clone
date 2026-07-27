"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import type { Message } from "@/lib/types";

import { useEditMessage } from "./queries";

/** Rewrite a message you sent. The transcript marks the result as edited. */
export function EditMessageModal({
  message,
  onClose,
}: {
  message: Message | null;
  onClose: () => void;
}) {
  const [body, setBody] = useState("");
  const edit = useEditMessage();
  const toast = useToast();

  useEffect(() => {
    if (message) setBody(message.body ?? "");
  }, [message]);

  function save() {
    const trimmed = body.trim();
    if (!message || !trimmed || trimmed === message.body) return onClose();
    edit.mutate(
      { messageId: message.id, body: trimmed },
      {
        onSuccess: () => {
          toast.success("Message edited.");
          onClose();
        },
        onError: () => toast.error("Could not edit that message."),
      },
    );
  }

  return (
    <Modal
      open={message !== null}
      onOpenChange={(open) => !open && onClose()}
      title="Edit message"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!body.trim() || edit.isPending}>
            {edit.isPending ? "Saving…" : "Save"}
          </Button>
        </>
      }
    >
      <textarea
        value={body}
        onChange={(event) => setBody(event.target.value)}
        rows={3}
        aria-label="Message text"
        autoFocus
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            save();
          }
        }}
        className="w-full resize-none rounded-xl bg-surface-hover px-3 py-2 text-[15px] text-content-primary outline-none ring-accent focus:ring-2"
      />
    </Modal>
  );
}
