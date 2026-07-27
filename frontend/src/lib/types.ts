/**
 * Wire types.
 *
 * Hand-written to mirror the backend's OpenAPI schema rather than generated,
 * because the generated output for this API is mostly noise (every response
 * wrapped in optional/nullable unions) and these are read on nearly every line
 * of UI code. They are checked against the live spec in CI-adjacent scripts.
 */

export type ConversationType = "direct" | "group";
export type ParticipantRole = "member" | "admin";
export type MessageType = "text" | "media" | "system";
export type MessageStatus = "sending" | "sent" | "delivered" | "read" | "failed";

export interface UserPublic {
  id: string;
  username: string | null;
  display_name: string;
  about: string | null;
  avatar_url: string | null;
  avatar_color: string;
  is_online: boolean;
  last_seen_at: string | null;
}

export interface UserPrivate extends UserPublic {
  phone_number: string;
  created_at: string;
}

export interface Participant {
  user: UserPublic;
  role: ParticipantRole;
  joined_at: string;
  left_at: string | null;
}

export interface LastMessagePreview {
  id: string;
  sender_id: string | null;
  sender_display_name: string | null;
  preview: string;
  type: string;
  created_at: string;
  is_deleted: boolean;
  system_event: string | null;
  system_meta: Record<string, unknown> | null;
}

export interface Conversation {
  id: string;
  type: ConversationType;
  name: string | null;
  avatar_url: string | null;
  avatar_color: string | null;
  disappearing_seconds: number;
  created_at: string;
  last_message_at: string | null;
  participants: Participant[];
  last_message: LastMessagePreview | null;
  unread_count: number;
  is_muted: boolean;
  is_pinned: boolean;
  my_role: ParticipantRole;
  is_active_member: boolean;
}

export interface Attachment {
  id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  url: string;
  thumbnail_url: string | null;
}

export interface ReactionSummary {
  emoji: string;
  count: number;
  user_ids: string[];
  reacted_by_me: boolean;
}

export interface QuotedMessage {
  id: string;
  sender_id: string | null;
  sender_display_name: string | null;
  preview: string;
  type: MessageType;
  is_deleted: boolean;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender: UserPublic | null;
  type: MessageType;
  body: string | null;
  created_at: string;
  edited_at: string | null;
  deleted_at: string | null;
  expires_at: string | null;
  reply_to: QuotedMessage | null;
  attachments: Attachment[];
  reactions: ReactionSummary[];
  system_event: string | null;
  system_meta: Record<string, unknown> | null;
  client_message_id: string | null;
  status: MessageStatus;
  delivered_count: number;
  read_count: number;
  recipient_count: number;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface Contact {
  id: string;
  nickname: string | null;
  created_at: string;
  user: UserPublic;
}

export interface AuthChallenge {
  phone_number: string;
  expires_in_seconds: number;
  dev_code: string | null;
  detail: string;
}

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: UserPrivate;
}

/** The envelope every failed response uses. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: { fields?: { field: string; reason: string }[] };
  };
}


export interface RecipientReceipt {
  user: UserPublic;
  delivered_at: string | null;
  read_at: string | null;
}

/** Per-recipient detail behind a message's single summary tick. */
export interface MessageInfo {
  message_id: string;
  sent_at: string;
  recipients: RecipientReceipt[];
}
