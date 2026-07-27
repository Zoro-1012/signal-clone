"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Copy, Forward, Info, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import type { ReactNode } from "react";

import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/cn";
import type { Message } from "@/lib/types";

export interface MessageActionHandlers {
  onForward: (message: Message) => void;
  onEdit: (message: Message) => void;
  onInfo: (message: Message) => void;
  onDelete?: (messageId: string) => void;
}

interface Item {
  key: string;
  label: string;
  icon: ReactNode;
  run: () => void;
  danger?: boolean;
}

/**
 * The overflow menu behind a message's "…" affordance.
 *
 * Signal's own menu also offers Select and Pin. Both are omitted rather than
 * rendered inert: an action that looks available and does nothing is worse than
 * one that is absent, and neither has anything behind it here. Everything listed
 * below performs a real operation.
 */
export function MessageActions({
  message,
  isOwn,
  handlers,
}: {
  message: Message;
  isOwn: boolean;
  handlers: MessageActionHandlers;
}) {
  const toast = useToast();

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.body ?? "");
      toast.success("Copied to clipboard.");
    } catch {
      // Clipboard access is denied outside a secure context, and on http:// the
      // API is simply absent — worth saying so rather than failing silently.
      toast.error("Your browser would not allow copying.");
    }
  }

  const items: Item[] = [];

  // Forwarding re-sends the text into another conversation. A media-only
  // message has none, and the attachment belongs to the message that claimed
  // it, so there is nothing to forward — the item is omitted rather than
  // offered and ignored.
  if (message.body) {
    items.push({
      key: "forward",
      label: "Forward",
      icon: <Forward className="h-4 w-4" />,
      run: () => handlers.onForward(message),
    });
  }

  // Editing and delivery detail are only meaningful for your own messages, and
  // the server rejects both for anyone else's.
  if (isOwn && message.body) {
    items.push({
      key: "edit",
      label: "Edit",
      icon: <Pencil className="h-4 w-4" />,
      run: () => handlers.onEdit(message),
    });
  }
  if (message.body) {
    items.push({
      key: "copy",
      label: "Copy text",
      icon: <Copy className="h-4 w-4" />,
      run: () => void copy(),
    });
  }
  if (isOwn) {
    items.push({
      key: "info",
      label: "Info",
      icon: <Info className="h-4 w-4" />,
      run: () => handlers.onInfo(message),
    });
  }
  if (isOwn && handlers.onDelete) {
    items.push({
      key: "delete",
      label: "Delete",
      icon: <Trash2 className="h-4 w-4" />,
      run: () => handlers.onDelete?.(message.id),
      danger: true,
    });
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          aria-label="More options"
          title="More options"
          className="rounded-full p-1.5 text-content-tertiary transition-colors hover:bg-surface-hover hover:text-content-primary"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align={isOwn ? "end" : "start"}
          sideOffset={6}
          className="z-context-menu min-w-44 rounded-2xl border border-edge-subtle bg-surface-raised p-1.5 shadow-lg animate-fade-in"
        >
          {items.map((item) => (
            <DropdownMenu.Item
              key={item.key}
              onSelect={item.run}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm outline-none",
                "data-[highlighted]:bg-surface-hover",
                item.danger ? "text-signal-red" : "text-content-primary",
              )}
            >
              {item.icon}
              {item.label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
