"use client";

import { ArrowLeft, MoreVertical, Phone, Search, Timer, Users, Video } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { dayDivider, lastSeen, shouldGroup } from "@/lib/format";
import type { Conversation, Message, UserPrivate } from "@/lib/types";
import { realtime, type Frame } from "@/lib/ws";
import { useUi } from "@/stores/ui";

import { GroupInfoPanel } from "@/features/groups/GroupInfoPanel";
import { DisappearingTimerMenu, timerLabel } from "./DisappearingTimer";
import { useToast } from "@/components/ui/Toast";

import { Composer } from "./Composer";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import {
  useDeleteMessage,
  useMessageRealtime,
  useMessages,
  useReadReceipts,
  useSendMessage,
  useToggleReaction,
} from "./queries";

interface ChatPaneProps {
  conversation: Conversation;
  user: UserPrivate;
}

function sameDay(a: string, b: string): boolean {
  return new Date(a).toDateString() === new Date(b).toDateString();
}

export function ChatPane({ conversation, user }: ChatPaneProps) {
  const showList = useUi((s) => s.showList);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [typingUserIds, setTypingUserIds] = useState<string[]>([]);
  const [groupInfoOpen, setGroupInfoOpen] = useState(false);
  const toast = useToast();

  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  /** Whether the viewport is near the bottom, which decides autoscroll. */
  const pinnedToBottom = useRef(true);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useMessages(
    conversation.id,
  );
  const messages = useMemo(() => data?.ordered ?? [], [data]);

  useMessageRealtime(conversation.id);
  useReadReceipts(conversation.id, messages.at(-1)?.id);

  const sendMessage = useSendMessage();
  const toggleReaction = useToggleReaction();
  const deleteMessage = useDeleteMessage(conversation.id);

  const isGroup = conversation.type === "group";
  const other = conversation.participants.find((p) => p.user.id !== user.id);

  // Typing indicators, held locally because they are ephemeral and never stored.
  useEffect(() => {
    setTypingUserIds([]);
    return realtime.onFrame((frame: Frame) => {
      const payload = frame.payload as { conversation_id?: string; user_id?: string };
      if (payload.conversation_id !== conversation.id || !payload.user_id) return;
      const userId = payload.user_id;

      if (frame.type === "typing.start") {
        setTypingUserIds((current) =>
          current.includes(userId) ? current : [...current, userId],
        );
      } else if (frame.type === "typing.stop" || frame.type === "message.new") {
        // A message arriving implies the sender stopped typing, so the indicator
        // clears without waiting for a separate stop frame that may never come.
        setTypingUserIds((current) => current.filter((id) => id !== userId));
      }
    });
  }, [conversation.id]);

  // Autoscroll, but only when already at the bottom. Yanking someone back down
  // while they are reading history is one of the most irritating chat bugs.
  useEffect(() => {
    if (pinnedToBottom.current) {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages.length, typingUserIds.length]);

  const handleScroll = useCallback(() => {
    const element = scrollRef.current;
    if (!element) return;

    const distanceFromBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    pinnedToBottom.current = distanceFromBottom < 120;

    // Load older history before the user actually reaches the top, so the
    // scrollbar does not stall while a page loads.
    if (element.scrollTop < 200 && hasNextPage && !isFetchingNextPage) {
      const previousHeight = element.scrollHeight;
      void fetchNextPage().then(() => {
        // Restore the reading position: prepending rows would otherwise jump the
        // viewport by exactly the height of the page just added.
        requestAnimationFrame(() => {
          const el = scrollRef.current;
          if (el) el.scrollTop = el.scrollHeight - previousHeight;
        });
      });
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  const typingNames = typingUserIds
    .map((id) => conversation.participants.find((p) => p.user.id === id)?.user.display_name)
    .filter((name): name is string => Boolean(name));

  function handleSend(body: string, attachmentIds: string[] = []) {
    sendMessage.mutate(
      {
        conversationId: conversation.id,
        body,
        replyToId: replyTo?.id ?? null,
        clientMessageId: crypto.randomUUID(),
        attachmentIds,
      },
      {
        onError: () => toast.error("Message failed to send. Check your connection."),
      },
    );
    setReplyTo(null);
    pinnedToBottom.current = true;
  }

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col bg-surface-base">
      <header className="flex h-header shrink-0 items-center gap-3 border-b border-edge-subtle px-4">
        <button
          onClick={showList}
          aria-label="Back to chats"
          className="-ml-1 rounded-full p-1.5 text-content-primary hover:bg-surface-hover md:hidden"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>

        {/* The whole header identity is the affordance for group info, matching
            Signal, with an explicit members button as a discoverable fallback. */}
        <button
          onClick={() => isGroup && setGroupInfoOpen(true)}
          disabled={!isGroup}
          aria-label={isGroup ? "Group info" : undefined}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg px-1 py-1 text-left enabled:hover:bg-surface-hover"
        >
          <Avatar
            name={conversation.name ?? "Conversation"}
            color={conversation.avatar_color}
            src={conversation.avatar_url}
            size="sm"
          />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium text-content-primary">
              {conversation.name}
            </span>
            <span className="block truncate text-xs text-content-secondary">
              {isGroup
                ? `${conversation.participants.length} members`
                : other
                  ? lastSeen(other.user.last_seen_at, other.user.is_online)
                  : ""}
            </span>
          </span>
        </button>

        <div className="flex items-center gap-1 text-content-secondary">
          {isGroup && (
            <button
              onClick={() => setGroupInfoOpen(true)}
              aria-label="Group members"
              title="Group members"
              className="rounded-full p-2 transition-colors hover:bg-surface-hover hover:text-content-primary"
            >
              <Users className="h-5 w-5" strokeWidth={1.75} />
            </button>
          )}
          <DisappearingTimerMenu conversation={conversation} />
          {[
            { Icon: Video, label: "Video call" },
            { Icon: Phone, label: "Voice call" },
            { Icon: Search, label: "Search in conversation" },
            { Icon: MoreVertical, label: "More options" },
          ].map(({ Icon, label }) => (
            <button
              key={label}
              aria-label={label}
              title={`${label} is not enabled in this build`}
              disabled
              className="rounded-full p-2 disabled:opacity-40"
            >
              <Icon className="h-5 w-5" strokeWidth={1.75} />
            </button>
          ))}
        </div>
      </header>

      {conversation.disappearing_seconds > 0 && (
        <div className="flex shrink-0 items-center justify-center gap-2 border-b border-edge-subtle bg-surface-hover px-4 py-1.5 text-xs text-content-secondary">
          <Timer className="h-3.5 w-3.5" />
          Messages disappear after {timerLabel(conversation.disappearing_seconds).toLowerCase()}
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="min-h-0 flex-1 overflow-y-auto py-4"
        // The transcript updates as messages arrive, so it is announced politely
        // rather than being a silent region.
        aria-live="polite"
        aria-label="Messages"
      >
        {isFetchingNextPage && (
          <p className="pb-2 text-center text-xs text-content-tertiary">Loading earlier messages…</p>
        )}
        {isLoading && <p className="py-8 text-center text-sm text-content-tertiary">Loading…</p>}

        {!isLoading && messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-8 text-center">
            <Avatar
              name={conversation.name ?? "Conversation"}
              color={conversation.avatar_color}
              size="xl"
            />
            <h2 className="mt-3 text-lg font-semibold text-content-primary">
              {conversation.name}
            </h2>
            <p className="max-w-xs text-sm text-content-secondary">
              No messages yet. Say hello.
            </p>
          </div>
        )}

        {messages.map((message, index) => {
          const previous = messages[index - 1];
          const next = messages[index + 1];
          const isOwn = message.sender?.id === user.id;

          if (message.type === "system") {
            return (
              <div key={message.id} className="my-3 px-4 text-center">
                <span className="rounded-full bg-surface-hover px-3 py-1 text-xs text-content-secondary">
                  {systemText(message)}
                </span>
              </div>
            );
          }

          const grouped = shouldGroup(
            previous?.sender?.id,
            message.sender?.id,
            previous?.created_at,
            message.created_at,
          );
          // The tail belongs to the last bubble of a run, so the run reads as one
          // block with a single pointer.
          const tail = !next || !shouldGroup(
            message.sender?.id,
            next.sender?.id,
            message.created_at,
            next.created_at,
          );

          const needsDivider = !previous || !sameDay(previous.created_at, message.created_at);

          return (
            <div key={message.id}>
              {needsDivider && (
                <div className="my-4 flex items-center justify-center">
                  <span className="rounded-full bg-surface-hover px-3 py-1 text-xs font-medium text-content-secondary">
                    {dayDivider(message.created_at)}
                  </span>
                </div>
              )}
              <MessageBubble
                message={message}
                isOwn={isOwn}
                isGroup={isGroup}
                grouped={grouped && !needsDivider}
                tail={tail}
                onReact={(messageId, emoji) => toggleReaction.mutate({ messageId, emoji })}
                onReply={setReplyTo}
                onDelete={(messageId) =>
                  deleteMessage.mutate(messageId, {
                    onSuccess: () => toast.success("Message deleted."),
                    onError: () => toast.error("Could not delete that message."),
                  })
                }
              />
            </div>
          );
        })}

        <div ref={bottomRef} />
      </div>

      <TypingIndicator names={typingNames} />

      <Composer
        conversationId={conversation.id}
        replyTo={replyTo}
        onCancelReply={() => setReplyTo(null)}
        onSend={handleSend}
      />

      {isGroup && (
        <GroupInfoPanel
          conversation={conversation}
          user={user}
          open={groupInfoOpen}
          onOpenChange={setGroupInfoOpen}
        />
      )}
    </div>
  );
}

/** Structured system events, rendered to prose on the client. */
function systemText(message: Message): string {
  switch (message.system_event) {
    case "group_created":
      return `Group "${String(message.system_meta?.name ?? "")}" was created`;
    case "members_added":
      return "Members were added";
    case "member_removed":
      return "A member was removed";
    case "member_left":
      return "A member left";
    case "group_renamed":
      return `Group renamed to "${String(message.system_meta?.name ?? "")}"`;
    case "role_changed":
      return "A member became an admin";
    case "disappearing_timer_changed": {
      const seconds = Number(message.system_meta?.seconds ?? 0);
      return seconds > 0
        ? `Disappearing messages set to ${timerLabel(seconds).toLowerCase()}`
        : "Disappearing messages turned off";
    }
    default:
      return "Conversation updated";
  }
}
