"use client";

import { MessageSquare, Phone, Settings, SquareStack } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";
import { cn } from "@/lib/cn";
import type { UserPrivate } from "@/lib/types";
import { type NavTab, useUi } from "@/stores/ui";

const TABS: { id: NavTab; label: string; Icon: typeof MessageSquare }[] = [
  { id: "chats", label: "Chats", Icon: MessageSquare },
  { id: "calls", label: "Calls", Icon: Phone },
  { id: "stories", label: "Stories", Icon: SquareStack },
];

interface NavRailProps {
  user: UserPrivate;
  unreadTotal: number;
}

/**
 * The 80px icon rail down the left edge.
 *
 * Rendered as a tablist so arrow keys move between tabs and a screen reader
 * announces the selected one — a column of plain buttons would give neither.
 */
export function NavRail({ user, unreadTotal }: NavRailProps) {
  const navTab = useUi((s) => s.navTab);
  const setNavTab = useUi((s) => s.setNavTab);

  return (
    <nav
      role="tablist"
      aria-orientation="vertical"
      aria-label="Main navigation"
      className="hidden w-rail shrink-0 flex-col items-center gap-1 border-r border-edge-subtle bg-surface-panel py-3 md:flex"
    >
      {TABS.map(({ id, label, Icon }) => {
        const active = navTab === id;
        const badge = id === "chats" ? unreadTotal : 0;
        return (
          <button
            key={id}
            role="tab"
            aria-selected={active}
            aria-label={badge > 0 ? `${label}, ${badge} unread` : label}
            title={label}
            onClick={() => setNavTab(id)}
            className={cn(
              "relative flex h-12 w-12 items-center justify-center rounded-xl transition-colors",
              active
                ? "bg-surface-active text-content-primary"
                : "text-content-secondary hover:bg-surface-hover",
            )}
          >
            <Icon className="h-6 w-6" strokeWidth={active ? 2.25 : 1.75} />
            {badge > 0 && (
              <span className="absolute right-1.5 top-1.5 min-w-[18px] rounded-full bg-signal-red px-1 text-[11px] font-semibold leading-[18px] text-white">
                {badge > 99 ? "99+" : badge}
              </span>
            )}
          </button>
        );
      })}

      <div className="flex-1" />

      <button
        role="tab"
        aria-selected={navTab === "settings"}
        aria-label="Settings"
        title="Settings"
        onClick={() => setNavTab("settings")}
        className={cn(
          "flex h-12 w-12 items-center justify-center rounded-xl transition-colors",
          navTab === "settings"
            ? "bg-surface-active text-content-primary"
            : "text-content-secondary hover:bg-surface-hover",
        )}
      >
        <Settings className="h-6 w-6" strokeWidth={1.75} />
      </button>

      <button
        onClick={() => setNavTab("settings")}
        aria-label="Your profile"
        title={user.display_name}
        className="mt-1 rounded-full"
      >
        <Avatar name={user.display_name} color={user.avatar_color} src={user.avatar_url} size="sm" />
      </button>
    </nav>
  );
}
