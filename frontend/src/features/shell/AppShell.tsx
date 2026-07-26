"use client";

import { useMemo, useState } from "react";

import { ConversationList } from "@/features/conversations/ConversationList";
import {
  useConversationRealtime,
  useConversations,
} from "@/features/conversations/queries";
import { cn } from "@/lib/cn";
import type { UserPrivate } from "@/lib/types";
import { useUi } from "@/stores/ui";

import { ComingSoon } from "./ComingSoon";
import { NavRail } from "./NavRail";

interface AppShellProps {
  user: UserPrivate;
}

/**
 * The three-pane Signal Desktop layout.
 *
 * Desktop shows rail, list and chat side by side. Below `md` only one pane can
 * fit, so the list and chat swap — which is how Signal behaves on a phone.
 */
export function AppShell({ user }: AppShellProps) {
  const navTab = useUi((s) => s.navTab);
  const mobilePane = useUi((s) => s.mobilePane);
  const activeId = useUi((s) => s.activeConversationId);
  const [, setNewChatOpen] = useState(false);

  useConversationRealtime();

  const { data } = useConversations("");
  const unreadTotal = useMemo(
    () => (data ?? []).reduce((total, conversation) => total + conversation.unread_count, 0),
    [data],
  );

  return (
    <div className="flex h-dvh overflow-hidden bg-surface-base">
      <NavRail user={user} unreadTotal={unreadTotal} />

      {navTab === "chats" ? (
        <>
          <div
            className={cn(
              "h-full w-full md:block",
              mobilePane === "chat" ? "hidden" : "block",
            )}
          >
            <ConversationList user={user} onNewChat={() => setNewChatOpen(true)} />
          </div>

          <div
            className={cn(
              "h-full min-w-0 flex-1 md:block",
              mobilePane === "chat" ? "block" : "hidden",
            )}
          >
            {activeId ? (
              <div className="flex h-full items-center justify-center text-content-secondary">
                Conversation {activeId.slice(0, 8)}
              </div>
            ) : (
              <EmptyChatPane />
            )}
          </div>
        </>
      ) : (
        <ComingSoon tab={navTab} />
      )}
    </div>
  );
}

/** Shown before any conversation is opened, mirroring Signal's welcome pane. */
function EmptyChatPane() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <svg viewBox="0 0 48 48" className="h-20 w-20" aria-hidden="true">
        <path
          d="M24 4C12.4 4 3 12.5 3 23c0 5.6 2.7 10.6 7 14l-2 6.5 7-3.4c2.8 1.2 5.9 1.9 9 1.9 11.6 0 21-8.5 21-19S35.6 4 24 4Z"
          fill="var(--accent)"
        />
      </svg>
      <h2 className="text-xl font-semibold text-content-primary">Welcome to Signal</h2>
      <p className="max-w-xs text-sm text-content-secondary">
        Select a chat to start messaging, or begin a new conversation.
      </p>
    </div>
  );
}
