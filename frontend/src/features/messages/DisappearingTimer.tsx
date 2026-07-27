"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Timer, TimerOff } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
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

/** The server caps the timer at one week; mirror it so the field agrees. */
const MAX_TIMER_SECONDS = 7 * 24 * 60 * 60;

const UNITS: ReadonlyArray<{ id: string; label: string; seconds: number }> = [
  { id: "seconds", label: "seconds", seconds: 1 },
  { id: "minutes", label: "minutes", seconds: 60 },
  { id: "hours", label: "hours", seconds: 60 * 60 },
  { id: "days", label: "days", seconds: 24 * 60 * 60 },
  { id: "weeks", label: "weeks", seconds: 7 * 24 * 60 * 60 },
];

/**
 * Describe a duration in the largest unit that divides it exactly.
 *
 * A custom timer will not match a preset, and "604800s" is not a duration
 * anyone reads — so the label is derived rather than looked up.
 */
export function timerLabel(seconds: number): string {
  const preset = DURATIONS.find((option) => option.seconds === seconds);
  if (preset) return preset.label;
  if (seconds <= 0) return "Off";

  for (const unit of [...UNITS].reverse()) {
    if (seconds % unit.seconds === 0) {
      const count = seconds / unit.seconds;
      return `${count} ${count === 1 ? unit.label.replace(/s$/, "") : unit.label}`;
    }
  }
  return `${seconds} seconds`;
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
  const [customOpen, setCustomOpen] = useState(false);
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

  const isCustom =
    conversation.disappearing_seconds > 0 &&
    !DURATIONS.some((option) => option.seconds === conversation.disappearing_seconds);

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

          <DropdownMenu.Separator className="my-1 h-px bg-edge-subtle" />
          <DropdownMenu.Item
            onSelect={() => setCustomOpen(true)}
            className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm text-content-primary outline-none data-[highlighted]:bg-surface-hover"
          >
            Custom time…
            {isCustom && <Check className="h-4 w-4 text-accent" />}
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>

      <CustomTimerModal
        open={customOpen}
        current={conversation.disappearing_seconds}
        onOpenChange={setCustomOpen}
        onSubmit={(seconds) => update.mutate(seconds)}
      />
    </DropdownMenu.Root>
  );
}

/** Free-form duration entry, for a window none of the presets covers. */
function CustomTimerModal({
  open,
  current,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  current: number;
  onOpenChange: (open: boolean) => void;
  onSubmit: (seconds: number) => void;
}) {
  const [amount, setAmount] = useState("1");
  const [unitId, setUnitId] = useState("hours");

  const unit = UNITS.find((candidate) => candidate.id === unitId) ?? UNITS[2]!;
  const parsed = Number(amount);
  const seconds = Number.isFinite(parsed) ? Math.round(parsed) * unit.seconds : 0;
  const tooLong = seconds > MAX_TIMER_SECONDS;
  const valid = Number.isInteger(parsed) && parsed > 0 && !tooLong && seconds !== current;

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Custom timer"
      description="Choose how long new messages stay before they disappear."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={!valid}
            onClick={() => {
              onSubmit(seconds);
              onOpenChange(false);
            }}
          >
            Set
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="flex gap-2">
          <Input
            type="number"
            min={1}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            aria-label="Duration"
            className="flex-1"
          />
          <select
            value={unitId}
            onChange={(event) => setUnitId(event.target.value)}
            aria-label="Unit"
            className="rounded-xl bg-surface-hover px-3 text-sm text-content-primary outline-none ring-accent focus:ring-2"
          >
            {UNITS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <p className={cn("text-sm", tooLong ? "text-signal-red" : "text-content-secondary")}>
          {tooLong
            ? "One week is the longest timer allowed."
            : seconds > 0
              ? `New messages will disappear after ${timerLabel(seconds).toLowerCase()}.`
              : "Enter a whole number greater than zero."}
        </p>
      </div>
    </Modal>
  );
}
