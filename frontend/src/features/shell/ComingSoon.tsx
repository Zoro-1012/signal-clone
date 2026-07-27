"use client";

import { Phone, SquareStack } from "lucide-react";

import type { NavTab } from "@/stores/ui";

type PlaceholderTab = Exclude<NavTab, "chats" | "settings">;

const CONTENT: Record<PlaceholderTab, { title: string; body: string; Icon: typeof Phone }> = {
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
};

/**
 * Designed placeholder for the surfaces the brief explicitly permits stubbing.
 *
 * Deliberately not a blank pane or a dead link: an unstyled gap reads as an
 * unfinished feature, whereas this reads as a scoped decision.
 */
export function ComingSoon({ tab }: { tab: PlaceholderTab }) {
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
