"use client";

import Image from "next/image";
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
    // Column on a phone so the nav bar can take the bottom edge; row on
    // desktop so the rail takes the left.
    <div className="flex h-dvh flex-col overflow-hidden bg-surface-base md:flex-row">
      <NavRail user={user} unreadTotal={unreadTotal} />

      {navTab === "chats" ? (
        <>
          <div
            className={cn(
              // w-full is for mobile, where the list is the whole screen. It must
              // be released at md, or the list occupies 100% of the row and the
              // flex-1 chat pane is pushed entirely off the viewport.
              // min-h-0 lets it shrink beside the bottom bar rather than
              // overflowing the column and pushing the bar off-screen.
              "min-h-0 w-full flex-1 shrink-0 md:block md:h-full md:w-auto md:flex-none",
              mobilePane === "chat" ? "hidden" : "block",
            )}
          >
            <ConversationList user={user} onNewChat={() => setNewChatOpen(true)} />
          </div>

          <div
            className={cn(
              "min-h-0 min-w-0 flex-1 md:block md:h-full",
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
        <div className="min-h-0 flex-1 md:contents">
          <SettingsPane user={user} />
        </div>
      ) : (
        <div className="min-h-0 flex-1 md:contents">
          <ComingSoon tab={navTab} />
        </div>
      )}

      <NewChatModal open={newChatOpen} onOpenChange={setNewChatOpen} />
    </div>
  );
}

/** Shown before any conversation is opened, mirroring Signal's welcome pane. */
function EmptyChatPane() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <Image src="/signal-logo.svg" alt="" width={80} height={80} className="h-20 w-20" />
      <h2 className="text-xl font-semibold text-content-primary">Welcome to Signal</h2>
      <p className="max-w-xs text-sm text-content-secondary">
        Select a chat to start messaging, or begin a new conversation.
      </p>
    </div>
  );
}
