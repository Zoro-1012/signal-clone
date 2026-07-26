/**
 * Date and time formatting, matching Signal's conventions.
 */

import { format, isThisYear, isToday, isYesterday } from "date-fns";

/** Timestamp shown inside a message bubble: always a clock time. */
export function messageTime(iso: string): string {
  return format(new Date(iso), "h:mm a");
}

/**
 * Timestamp in the conversation list.
 *
 * Signal degrades gracefully with age: a clock time today, "Yesterday", a
 * weekday within the last week, then a date. The point is that the most recent
 * conversations carry the most precise information.
 */
export function conversationTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (isToday(date)) return format(date, "h:mm a");
  if (isYesterday(date)) return "Yesterday";
  const ageInDays = (Date.now() - date.getTime()) / 86_400_000;
  if (ageInDays < 7) return format(date, "EEE");
  return isThisYear(date) ? format(date, "d MMM") : format(date, "dd/MM/yy");
}

/** Divider text between days in a transcript. */
export function dayDivider(iso: string): string {
  const date = new Date(iso);
  if (isToday(date)) return "Today";
  if (isYesterday(date)) return "Yesterday";
  return isThisYear(date) ? format(date, "EEEE, d MMMM") : format(date, "d MMMM yyyy");
}

/** Presence line in a chat header. */
export function lastSeen(iso: string | null, isOnline: boolean): string {
  if (isOnline) return "Online";
  if (!iso) return "";
  const date = new Date(iso);
  if (isToday(date)) return `Last seen today at ${format(date, "h:mm a")}`;
  if (isYesterday(date)) return `Last seen yesterday at ${format(date, "h:mm a")}`;
  return `Last seen ${format(date, "d MMM")}`;
}

/** Human-readable file size for attachment cards. */
export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Whether two consecutive messages should be visually grouped.
 *
 * Signal collapses a run from the same sender within a few minutes into one
 * block, showing the avatar and timestamp once. Without this a rapid exchange
 * turns into a wall of repeated avatars.
 */
export function shouldGroup(
  previousSenderId: string | null | undefined,
  currentSenderId: string | null | undefined,
  previousIso: string | undefined,
  currentIso: string,
): boolean {
  if (!previousSenderId || !currentSenderId || !previousIso) return false;
  if (previousSenderId !== currentSenderId) return false;
  const gapMinutes =
    (new Date(currentIso).getTime() - new Date(previousIso).getTime()) / 60_000;
  return gapMinutes < 5;
}
