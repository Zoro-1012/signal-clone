"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Timer, TimerOff } from "lucide-react";

import { useToast } from "@/components/ui/Toast";
import { conversationKeys } from "@/features/conversations/queries";
import { messageKeys } from "@/features/messages/queries";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Conversation } from "@/lib/types";

/** Signal's own set of durations, in seconds. `0` means off. */
const DURATIONS: ReadonlyArray<{ label: string; seconds: number }> = [
  { label: "Off", seconds: 0 },
  { label: "30 seconds", seconds: 30 },
  { label: "5 minutes", seconds: 5 * 60 },
  { label: "1 hour", seconds: 60 * 60 },
  { label: "8 hours", seconds: 8 * 60 * 60 },
  { label: "1 day", seconds: 24 * 60 * 60 },
  { label: "1 week", seconds: 7 * 24 * 60 * 60 },
];

export function timerLabel(seconds: number): string {
  return DURATIONS.find((option) => option.seconds === seconds)?.label ?? `${seconds}s`;
}

/**
 * Sets the shared disappearing-message timer for a conversation.
 *
 * The timer is a property of the conversation, not of the sender, so it is set
 * once and applies to everyone's subsequent messages — which is why the change
 * is announced as a system event rather than applied silently.
 *
 * Groups restrict this to admins; the server enforces that, and the trigger is
 * hidden for non-admins so the affordance never lies about what it will do.
 */
export function DisappearingTimerMenu({ conversation }: { conversation: Conversation }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const active = conversation.disappearing_seconds > 0;

  const update = useMutation({
    mutationFn: (seconds: number) =>
      api.patch<Conversation>(`/conversations/${conversation.id}`, {
        disappearing_seconds: seconds,
      }),
    onSuccess: (_data, seconds) => {
      void queryClient.invalidateQueries({ queryKey: conversationKeys.all });
      // The server writes a system message announcing the change; refetch the
      // thread so it appears without waiting for the next socket frame.
      void queryClient.invalidateQueries({ queryKey: messageKeys.thread(conversation.id) });
      toast.success(
        seconds === 0
          ? "Disappearing messages turned off."
          : `New messages will disappear after ${timerLabel(seconds).toLowerCase()}.`,
      );
    },
    onError: () => toast.error("Could not update the disappearing message timer."),
  });

  if (!conversation.is_active_member) return null;
  if (conversation.type === "group" && conversation.my_role !== "admin") return null;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          aria-label="Disappearing messages"
          title={
            active
              ? `Disappearing messages: ${timerLabel(conversation.disappearing_seconds)}`
              : "Disappearing messages"
          }
          className={cn(
            "rounded-full p-2 transition-colors hover:bg-surface-hover",
            active ? "text-accent" : "hover:text-content-primary",
          )}
        >
          {active ? (
            <Timer className="h-5 w-5" strokeWidth={1.75} />
          ) : (
            <TimerOff className="h-5 w-5" strokeWidth={1.75} />
          )}
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-modal min-w-52 rounded-xl border border-edge-subtle bg-surface-panel p-1 shadow-elevated animate-fade-in"
        >
          <DropdownMenu.Label className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-content-tertiary">
            Disappearing messages
          </DropdownMenu.Label>
          {DURATIONS.map((option) => (
            <DropdownMenu.Item
              key={option.seconds}
              onSelect={() => update.mutate(option.seconds)}
              className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm text-content-primary outline-none data-[highlighted]:bg-surface-hover"
            >
              {option.label}
              {conversation.disappearing_seconds === option.seconds && (
                <Check className="h-4 w-4 text-accent" />
              )}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
