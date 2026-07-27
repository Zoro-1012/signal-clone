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
 * Primary navigation: an icon rail down the left edge on desktop, a bottom bar
 * on a phone.
 *
 * It used to be `hidden md:flex`, which left a phone with no navigation at all
 * — Settings, Calls and Stories were unreachable, and the only reason it was
 * not obviously broken is that the app opens on Chats. A narrow screen cannot
 * spare 80px of width, so the same tablist reflows to the bottom edge instead
 * of disappearing.
 *
 * Rendered as a tablist so arrow keys move between tabs and a screen reader
 * announces the selected one — a row of plain buttons would give neither.
 */
export function NavRail({ user, unreadTotal }: NavRailProps) {
  const navTab = useUi((s) => s.navTab);
  const setNavTab = useUi((s) => s.setNavTab);
  const mobilePane = useUi((s) => s.mobilePane);

  // Inside a conversation on a phone the bar would sit between the composer and
  // the edge of the screen, competing with the keyboard for the scarcest space
  // on the display. Signal hides it there too; the back arrow is the way out.
  const hiddenOnMobile = mobilePane === "chat" && navTab === "chats";

  return (
    <nav
      role="tablist"
      aria-orientation="vertical"
      aria-label="Main navigation"
      className={cn(
        "order-last flex w-full shrink-0 flex-row items-center justify-around gap-1",
        "border-t border-edge-subtle bg-surface-panel px-2 py-1.5",
        // Desktop: back to a vertical rail on the left.
        "md:order-none md:w-rail md:flex-col md:justify-start md:border-r md:border-t-0 md:px-0 md:py-3",
        hiddenOnMobile && "hidden md:flex",
      )}
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
              // Signal marks the selected tab with a rounded pill and a solid
              // glyph. Two signals rather than one: the fill survives at a glance
              // and in high contrast, where a subtle background does not.
              "relative flex h-12 w-12 items-center justify-center rounded-2xl transition-colors",
              active
                ? "bg-surface-active text-content-primary"
                : "text-content-secondary hover:bg-surface-hover",
            )}
          >
            <Icon
              className="h-6 w-6"
              strokeWidth={active ? 2 : 1.75}
              fill={active ? "currentColor" : "none"}
            />
            {badge > 0 && (
              <span className="absolute right-1.5 top-1.5 min-w-[18px] rounded-full bg-signal-red px-1 text-[11px] font-semibold leading-[18px] text-white">
                {badge > 99 ? "99+" : badge}
              </span>
            )}
          </button>
        );
      })}

      <div className="hidden flex-1 md:block" />

      <button
        role="tab"
        aria-selected={navTab === "settings"}
        aria-label="Settings"
        title="Settings"
        onClick={() => setNavTab("settings")}
        className={cn(
          "flex h-12 w-12 items-center justify-center rounded-2xl transition-colors",
          navTab === "settings"
            ? "bg-surface-active text-content-primary"
            : "text-content-secondary hover:bg-surface-hover",
        )}
      >
        <Settings
          className="h-6 w-6"
          strokeWidth={navTab === "settings" ? 2 : 1.75}
          fill={navTab === "settings" ? "currentColor" : "none"}
        />
      </button>

      <button
        onClick={() => setNavTab("settings")}
        aria-label="Your profile"
        title={user.display_name}
        className="hidden rounded-full md:mt-1 md:block"
      >
        <Avatar name={user.display_name} color={user.avatar_color} src={user.avatar_url} size="sm" />
      </button>
    </nav>
  );
}
