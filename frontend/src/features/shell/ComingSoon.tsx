"use client";

import { Phone, Settings, SquareStack } from "lucide-react";

import type { NavTab } from "@/stores/ui";

const CONTENT: Record<
  Exclude<NavTab, "chats">,
  { title: string; body: string; Icon: typeof Phone }
> = {
  calls: {
    title: "Calls",
    body: "Voice and video calling is not part of this build. The brief scopes it as a placeholder.",
    Icon: Phone,
  },
  stories: {
    title: "Stories",
    body: "Stories are not part of this build. The brief scopes them as a placeholder.",
    Icon: SquareStack,
  },
  settings: {
    title: "Settings",
    body: "Appearance, privacy and notification settings are coming next.",
    Icon: Settings,
  },
};

/**
 * Designed placeholder for the surfaces the brief explicitly permits stubbing.
 *
 * Deliberately not a blank pane or a dead link: an unstyled gap reads as an
 * unfinished feature, whereas this reads as a scoped decision.
 */
export function ComingSoon({ tab }: { tab: Exclude<NavTab, "chats"> }) {
  const { title, body, Icon } = CONTENT[tab];
  return (
    <div className="flex h-full flex-1 flex-col items-center justify-center gap-3 px-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-surface-hover">
        <Icon className="h-8 w-8 text-content-tertiary" strokeWidth={1.5} />
      </div>
      <h2 className="text-xl font-semibold text-content-primary">{title}</h2>
      <p className="max-w-sm text-sm text-content-secondary">{body}</p>
      <span className="mt-2 rounded-full bg-surface-hover px-3 py-1 text-xs font-medium text-content-secondary">
        Coming soon
      </span>
    </div>
  );
}
