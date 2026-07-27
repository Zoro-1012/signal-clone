"use client";

import { useMemo, useState } from "react";

import { ConversationList } from "@/features/conversations/ConversationList";
import { ChatPane } from "@/features/messages/ChatPane";
import { NewChatModal } from "@/features/conversations/NewChatModal";
import { SettingsPane } from "@/features/settings/SettingsPane";
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
  const [newChatOpen, setNewChatOpen] = useState(false);

  useConversationRealtime();

  const { data } = useConversations("");
  const conversations = useMemo(() => data ?? [], [data]);

  const unreadTotal = useMemo(
    () => conversations.reduce((total, conversation) => total + conversation.unread_count, 0),
    [conversations],
  );

  // Resolved from the same cached list the sidebar renders, so the header and
  // the row can never disagree about a conversation's name or membership.
  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? null,
    [conversations, activeId],
  );

  return (
    <div className="flex h-dvh overflow-hidden bg-surface-base">
      <NavRail user={user} unreadTotal={unreadTotal} />

      {navTab === "chats" ? (
        <>
          <div
            className={cn(
              // w-full is for mobile, where the list is the whole screen. It must
              // be released at md, or the list occupies 100% of the row and the
              // flex-1 chat pane is pushed entirely off the viewport.
              "h-full w-full shrink-0 md:block md:w-auto",
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
            {activeConversation ? (
              <ChatPane conversation={activeConversation} user={user} />
            ) : (
              <EmptyChatPane />
            )}
          </div>
        </>
      ) : navTab === "settings" ? (
        <SettingsPane user={user} />
      ) : (
        <ComingSoon tab={navTab} />
      )}

      <NewChatModal open={newChatOpen} onOpenChange={setNewChatOpen} />
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
