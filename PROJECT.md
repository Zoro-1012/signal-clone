# PROJECT.md — Secure Messaging Platform (Signal Clone)

> Engineering spec sheet. Written **before** any implementation code, and treated as the
> single source of truth for scope, architecture and delivery for the rest of the build.

---

## 0. Submission Details

| Field | Value |
|---|---|
| **Assignment** | Scaler SDE Fullstack Assignment — Secure Messaging Platform (Signal Clone) |
| **Candidate** | Nipurn |
| **Repository** | `<github-url>` — public, contains `frontend/` and `backend/` |
| **Live demo** | `<vercel-url>` (frontend) · `<render-url>` (API) |
| **Estimated effort (per brief)** | ~24 hours |
| **Started** | 26 July 2026 |

> The three `< >` placeholders above are filled in the moment the repo is created and the
> services are deployed. Nothing else in this document is provisional.

---

## 1. What the Assignment Actually Asks For

A functional clone of Signal Messenger that **replicates Signal's design, UX and core
messaging workflows**. Users register, manage contacts, hold 1:1 and group conversations,
and send/receive messages in real time — inside Signal's clean, privacy-focused interface.

Two framing statements from the brief that drive every decision below:

1. *"The focus is on recreating the Signal user experience and core messaging workflows
   rather than implementing real end-to-end cryptographic protocols — encryption can be
   mocked or simulated."*
   → Effort goes into **UX fidelity and correct messaging semantics**, not crypto. We still
   model an encryption *envelope* so the data flow is honest about where crypto would sit.

2. *"Your application should totally resemble Signal's design."*
   → This is an explicit, weighted evaluation criterion. The UI is not "a chat app with blue
   bubbles"; it is a deliberate reconstruction of Signal Desktop's layout, spacing, type
   scale, colour tokens and interaction patterns.

### 1.1 Mandated Technical Stack

| Layer | Required | Chosen | Why |
|---|---|---|---|
| Frontend | Next.js (TypeScript) | Next.js 15 App Router, TS strict | Required. App Router for layout-driven UI, RSC for the shell, client components for the live surfaces. |
| Backend | Python — FastAPI **or** Django | **FastAPI** | Required (choice). Rationale in §3.1. |
| Database | SQLite, own schema | SQLite + SQLAlchemy 2.0 + Alembic | Required. Schema design is explicitly graded, so it is migration-managed rather than auto-created. |
| Real-time | WebSockets or equivalent | Native FastAPI WebSockets | Required. No broker dependency for a single-process deployment; see §3.4 for the scale-out path. |

---

## 2. Requirement Matrix

Every line item from the brief, tracked to the module that satisfies it. This table is the
build checklist and gets status-updated as the project progresses.

### 2.1 Core — Must Have

**1. Authentication / Onboarding**

| # | Requirement | Implementation |
|---|---|---|
| A1 | Register with phone number or username | `POST /auth/register` — E.164 phone as primary identity, unique username as handle |
| A2 | Mocked verification with a fixed OTP | `POST /auth/verify` — fixed dev OTP `123456`, rate-limited, single-use challenge rows |
| A3 | Set display name and profile avatar | `PATCH /users/me` + avatar upload; Signal-style colour-seeded initials fallback |
| A4 | Login / Logout | `POST /auth/login`, `POST /auth/logout` (refresh-token revocation) |
| A5 | Session persistence | JWT access (short-lived) + rotating refresh token in httpOnly cookie; survives reload |

**2. Contacts & Conversation List**

| # | Requirement | Implementation |
|---|---|---|
| C1 | Conversations sorted by most recent activity | `GET /conversations` ordered by `last_message_at DESC`, denormalised for index-only sort |
| C2 | Search conversations and contacts | Debounced client search over a single `GET /search` endpoint (conversations + contacts + messages) |
| C3 | Add a new contact | `POST /contacts` by phone or username, with a "not on Signal" empty state |
| C4 | Unread indicators + last-message preview | Per-participant `last_read_message_id` → computed unread count; preview includes status glyph and sender prefix in groups |
| C5 | Online / last-seen indicators | Presence tracked by live WS connections; `last_seen_at` persisted on disconnect |

**3. One-on-One Messaging**

| # | Requirement | Implementation |
|---|---|---|
| M1 | Real-time send/receive | WS `message.new` fan-out to all participant connections + optimistic local echo |
| M2 | Message timestamps | Stored UTC, rendered in viewer's locale/timezone with Signal's date-divider grouping |
| M3 | Delivery / read receipts (single/double check) | `message_receipts` table, one row per (message, user); glyph derived from aggregate state |
| M4 | Typing indicators | Ephemeral WS `typing.start` / `typing.stop`, never persisted, auto-expiring after idle |
| M5 | Status: sending → sent → delivered → read | Explicit state machine, client-side `sending` + three server-authoritative states |
| M6 | All messages persist in the database | Every message written before the WS broadcast; broadcast is a cache-warm, never the source of truth |

**4. Group Messaging**

| # | Requirement | Implementation |
|---|---|---|
| G1 | Create group with name + members | `POST /conversations` with `type=group`, creator auto-assigned `admin` |
| G2 | Send/receive group messages | Same message pipeline; fan-out to N participants |
| G3 | View group members | Group info panel with roles, join dates, presence |
| G4 | Add / remove members (admin controls) | `POST/DELETE /conversations/{id}/participants`, admin-only, enforced server-side and reflected in the UI |
| G5 | Group data + messages persist | Membership changes emit persisted system messages ("Sneha added Ravi") |

**5. Signal Experience**

| # | Requirement | Implementation |
|---|---|---|
| S1 | Navigation and layout | Three-pane Signal Desktop shell: nav rail → conversation list → chat pane |
| S2 | Message bubbles and threading | Tailed bubbles, consecutive-message grouping, quoted replies, system messages |
| S3 | Forms, modals, search, filters | Accessible modal primitives, new chat / new group / contact / group info / settings |
| S4 | Notifications / toasts | Toast system for sends, failures, membership changes, connection loss/restore |
| S5 | Settings placeholders | Privacy, Notifications, Appearance, Linked Devices — real appearance controls, rest stubbed |

**Mocked / Placeholder (explicitly permitted)**

Voice & video calls · Stories · Linked devices · Real E2E encryption.
Each rendered as a designed "Coming Soon" surface rather than a dead link — a broken-looking
placeholder reads as an unfinished feature, a designed one reads as a scoped decision.

### 2.2 Bonus — All In Scope

| Bonus | Approach |
|---|---|
| Attachments (images / files) | Local disk (dev) / mounted volume (prod) behind a storage interface; thumbnails, lightbox, non-image file cards |
| Message reactions (emoji) | `message_reactions` table, unique per (message, user, emoji); hover picker + aggregated pills |
| Reply-to / quoted messages | Self-referential `reply_to_message_id`; quote preview in composer and bubble, click-to-scroll to original |
| Disappearing messages (functional) | Per-conversation TTL; `expires_at` set on delivery, background sweeper purges, countdown ring in the UI |
| Dark mode | Signal's actual dark palette as CSS custom properties; system / light / dark, no flash on load |
| Responsive design | Mobile (single pane + back navigation), tablet (two pane), desktop (three pane) |
| Keyboard shortcuts | `⌘K` search, `⌘N` new chat, `Esc` close, `↑` edit-intent, arrow navigation of the list, `?` shortcut sheet |

---

## 3. Architecture

### 3.1 Why FastAPI over Django

Both were permitted. FastAPI was chosen deliberately, and the reasoning is interview-defensible:

- **Real-time is the centre of this assignment.** FastAPI speaks WebSockets natively on the
  same ASGI app as the REST API — one process, one auth path, one deployment unit. Django
  needs Channels plus a channel layer (Redis in any real setup), which adds an
  infrastructure dependency for a free-tier demo deploy without buying anything here.
- **Schema-first contracts.** Pydantic v2 models are the request/response contract *and* the
  OpenAPI spec *and* the source for generated frontend types. One definition, no drift.
- **Explicit layering.** Django's conventions encourage fat models and view-level business
  logic. FastAPI imposes no structure, so the router → service → repository separation is a
  visible, defensible design decision rather than an inherited default — which matters when
  "Code Modularity" and "Backend / API Design" are graded criteria.

Trade-off honestly noted: we give up Django's admin, built-in auth and ORM-batteries, so
those are hand-rolled (deliberately, and covered by tests).

### 3.2 Backend Layering

```
app/
├── api/            HTTP + WS routers. Parse, authorise, delegate. No business logic.
│   ├── deps.py         shared dependencies (current user, db session, pagination)
│   ├── v1/             versioned REST routers
│   └── ws/             websocket endpoint + event dispatch
├── services/       Business rules. Transaction boundaries live here.
├── repositories/   All SQLAlchemy query construction. The only layer that knows SQL.
├── models/         SQLAlchemy ORM entities.
├── schemas/        Pydantic request/response DTOs. Never leak ORM objects to the wire.
├── core/           config, security, logging, exceptions, lifespan
├── realtime/       connection manager, event bus, presence registry, typing registry
└── db/             engine, session factory, base, Alembic migrations, seeds
```

Rules enforced throughout:

- Routers never import repositories. Services never import FastAPI. Repositories never
  import services. Dependencies point strictly inward.
- ORM entities never cross the API boundary — every response is a Pydantic schema.
- One transaction per request, opened and committed at the service boundary.
- Domain errors are typed exceptions mapped centrally to HTTP status codes; no `HTTPException`
  raised from inside business logic.

### 3.3 Frontend Layering

```
src/
├── app/            Next.js App Router — routes, layouts, loading/error boundaries
├── features/       Vertical slices: auth, conversations, messages, contacts, groups, settings
│   └── <feature>/  components · hooks · api · types  (a feature owns its whole stack)
├── components/     Cross-feature UI primitives (Button, Modal, Avatar, Toast, …)
├── lib/            api client, websocket client, query client, formatters, cn()
├── stores/         Zustand — session, UI/theme, presence, typing, draft state
└── styles/         design tokens, Tailwind theme extension
```

- **Server state** (conversations, messages, contacts) → TanStack Query, with the WS layer
  writing directly into the query cache so live updates and fetched data share one store.
- **Client state** (theme, open modals, drafts, presence, typing) → Zustand.
- No component reaches for `fetch` directly; every call goes through a typed feature API module.

### 3.4 Real-Time Design

Single authenticated WebSocket per browser tab, multiplexing all conversations.

```
client                          server
  │  connect (?token=JWT)         │
  ├──────────────────────────────►│  authenticate → register connection
  │                               │  mark user online → broadcast presence.update
  │  {type:"typing.start", …}     │
  ├──────────────────────────────►│  fan-out to other participants (not persisted)
  │                               │
  │      REST POST /messages      │  persist message  ──► authoritative
  │                               │  broadcast message.new to participant connections
  │◄──────────────────────────────┤
  │  {type:"receipt.read", …}     │
  ├──────────────────────────────►│  persist receipts → broadcast message.status
```

Deliberate decisions:

- **Sends go over REST, not the socket.** The socket is a delivery channel, not the write
  path. This gives every message a real HTTP status code, natural retries, and a system that
  degrades to polling instead of breaking when the socket drops.
- **Persist-then-broadcast, always.** The database is the source of truth; the socket only
  ever accelerates something already committed.
- **Typing and presence are never persisted** (except `last_seen_at` on disconnect) — they are
  ephemeral by nature and writing them would be a wasteful write per keystroke.
- **Scale-out path:** the `ConnectionManager` sits behind an interface, so the in-memory
  registry can be swapped for a Redis pub/sub backend for multi-worker deployment without
  touching any service code. Documented, not built — single-process is correct for this demo.

### 3.5 Simulated Encryption

Real E2EE is explicitly out of scope. Rather than ignore it, message bodies pass through an
`EncryptionEnvelope` abstraction on write and read, with a `MockCipher` implementation. It
records `algorithm`, `key_id` and `ciphertext` fields on every message row.

This means: the data model and call sites are shaped correctly for real crypto, the UI can
honestly display "end-to-end encrypted" affordances, and swapping in a real implementation is
a single-class change. The README states plainly that this is simulated, not secure — an
honest mock is worth more than a fake claim.

---

## 4. Database Schema

SQLite, designed by hand, migration-managed with Alembic. Entities:

| Table | Purpose | Notable columns |
|---|---|---|
| `users` | Identity + profile | `phone_number` (unique), `username` (unique), `display_name`, `avatar_url`, `avatar_color`, `about`, `last_seen_at`, `is_online`, `is_active` |
| `verification_codes` | Mocked OTP challenges | `user_id`, `code`, `expires_at`, `consumed_at`, `attempts` |
| `refresh_tokens` | Session persistence | `user_id`, `token_hash`, `expires_at`, `revoked_at`, `user_agent` |
| `contacts` | Directed contact edges | `owner_id`, `contact_user_id`, `nickname`, unique `(owner_id, contact_user_id)` |
| `conversations` | 1:1 and group threads | `type` (`direct`/`group`), `name`, `avatar_url`, `created_by`, `direct_key` (unique), `disappearing_seconds`, `last_message_at` |
| `conversation_participants` | Membership + per-user state | `role` (`member`/`admin`), `joined_at`, `left_at`, `last_read_message_id`, `is_muted`, `is_pinned` |

| `messages` | Message content | `conversation_id`, `sender_id`, `type` (`text`/`media`/`system`), `ciphertext` + `encryption_key_id` + `encryption_algorithm`, `system_event` + `system_meta`, `reply_to_message_id`, `client_message_id`, `expires_at`, `edited_at`, `deleted_at` |
| `message_receipts` | Per-recipient delivery state | `message_id`, `user_id`, `delivered_at`, `read_at`, unique `(message_id, user_id)` |
| `message_reactions` | Emoji reactions | `message_id`, `user_id`, `emoji`, unique `(message_id, user_id, emoji)` |
| `attachments` | Files and media | `message_id`, `file_name`, `content_type`, `size_bytes`, `width`, `height`, `storage_key` |

Design decisions worth defending:

- **1:1 conversations reuse the group model.** A direct chat is a conversation with exactly
  two participants. One message pipeline, one permission model, no duplicated logic — and a
  deterministic participant-pair key prevents duplicate direct threads.
- **Receipts are rows, not columns.** A `delivered`/`read` boolean on `messages` cannot express
  "read by 3 of 7 group members". Per-recipient rows make group receipts and the single/double
  check UI fall out naturally.
- **`last_read_message_id` instead of an unread counter.** A counter is denormalised state that
  drifts under concurrency; a watermark is idempotent and self-correcting.
- **`conversations.last_message_at` is denormalised on purpose.** The conversation list sorts by
  it on every load; without it, every list render is a correlated subquery over `messages`.
  Written inside the same transaction as the message, so it cannot drift.
- **Soft deletes** (`deleted_at`) on messages so "This message was deleted" tombstones and
  receipt history survive.
- **Message content is stored only as ciphertext.** There is deliberately no plaintext
  column: keeping both would defeat the sealing layer and make the encryption story
  dishonest. The cipher is simulated, but the storage shape is the one real crypto needs.
- **System messages are structured, not pre-rendered.** `system_event` + `system_meta` JSON
  rather than a baked sentence like "Nipurn added Ravi", so wording stays a presentation
  concern and can be translated or restyled without a migration.
- **No `index=True` on UUID primary keys.** SQLite already maintains an implicit index for a
  non-INTEGER primary key; declaring one builds a second identical B-tree that every insert
  must update for no read benefit. Single-column indexes already covered by a composite
  index's leftmost prefix are likewise omitted — this removed 15 redundant indexes.
- Composite indexes on `(conversation_id, created_at)` for message pagination,
  `(user_id, conversation_id)` for membership lookups, and `(user_id, read_at)` for bulk
  read-receipt updates.

A full ER diagram ships in the README.

---

## 5. API Surface

REST under `/api/v1`, WebSocket at `/ws`. Interactive OpenAPI docs at `/docs`.

```
Auth        POST   /auth/register            start registration, issue OTP challenge
            POST   /auth/verify              consume OTP → tokens
            POST   /auth/login               request OTP for existing account
            POST   /auth/refresh             rotate refresh token
            POST   /auth/logout              revoke session

Users       GET    /users/me                 current profile
            PATCH  /users/me                 update display name / about / avatar
            POST   /users/me/avatar          avatar upload

Contacts    GET    /contacts                 list, searchable
            POST   /contacts                 add by phone or username
            DELETE /contacts/{id}            remove

Convos      GET    /conversations            list, sorted, with unread + preview
            POST   /conversations            create direct or group
            GET    /conversations/{id}       detail with participants
            PATCH  /conversations/{id}       rename, avatar, disappearing timer
            POST   /conversations/{id}/participants     add members (admin)
            DELETE /conversations/{id}/participants/{u} remove member (admin)
            POST   /conversations/{id}/read            advance read watermark
            POST   /conversations/{id}/typing          typing signal

Messages    GET    /conversations/{id}/messages   cursor-paginated history
            POST   /conversations/{id}/messages   send
            PATCH  /messages/{id}                 edit
            DELETE /messages/{id}                 delete (tombstone)
            POST   /messages/{id}/reactions       add reaction
            DELETE /messages/{id}/reactions/{e}   remove reaction
            POST   /messages/{id}/attachments     upload

Search      GET    /search                    conversations + contacts + messages
Health      GET    /health                    liveness for the platform probe
```

Conventions: cursor pagination (not offset — offset skips rows when history grows mid-scroll),
`snake_case` JSON, RFC-9457-style typed error bodies, idempotency via a `client_message_id` so a
retried send can never duplicate a message.

### WebSocket Event Protocol

Every frame is `{ "type": string, "payload": object }`, with types shared between backend and
frontend as generated TypeScript.

| Direction | Event | Payload |
|---|---|---|
| ↑ client | `typing.start` / `typing.stop` | `conversation_id` |
| ↑ client | `ping` | — |
| ↓ server | `message.new` | full message DTO |
| ↓ server | `message.status` | `message_id`, `status`, `user_id` |
| ↓ server | `message.updated` / `message.deleted` | message DTO / id |
| ↓ server | `reaction.added` / `reaction.removed` | `message_id`, `user_id`, `emoji` |
| ↓ server | `typing.start` / `typing.stop` | `conversation_id`, `user_id` |
| ↓ server | `presence.update` | `user_id`, `is_online`, `last_seen_at` |
| ↓ server | `conversation.updated` | conversation DTO |

---

## 6. Repository Structure

```
signal-clone/
├── PROJECT.md                  this document
├── README.md                   setup, architecture, schema, API, assumptions
├── docker-compose.yml
├── .github/workflows/ci.yml    lint + typecheck + test on every push
├── backend/
│   ├── app/                    (layering per §3.2)
│   ├── alembic/                migrations
│   ├── tests/                  pytest: unit + API + websocket
│   ├── scripts/seed.py
│   ├── pyproject.toml          ruff · black · mypy · pytest config
│   └── Dockerfile
└── frontend/
    ├── src/                    (layering per §3.3)
    ├── public/
    ├── package.json
    ├── tsconfig.json           strict
    └── Dockerfile
```

---

## 7. Engineering Standards

**Commits.** [Conventional Commits](https://www.conventionalcommits.org): `feat:`, `fix:`,
`refactor:`, `test:`, `docs:`, `chore:`, `style:`, `perf:`, `ci:`. Every commit is one coherent
unit of work that leaves the tree in a working state — the history should read as a build log
a reviewer can follow commit by commit, not one `initial commit` dump. Work lands via short-lived
feature branches merged with `--no-ff`, so the graph shows discrete features.

**Code quality.** Backend: `ruff` (lint + import order), `black` (format), `mypy --strict` on
`app/`. Frontend: `eslint` (next + typescript-eslint), `prettier`, `tsc --noEmit` with
`strict: true`. All wired into CI; CI must be green on `main`.

**Testing.** `pytest` + `httpx.AsyncClient` for API tests, `fastapi.testclient` for WebSocket
flows, an isolated in-memory SQLite per test, and factory helpers instead of fixtures-by-JSON.
Coverage targets the parts that matter: auth, permissions, message ordering, receipt state
machine, group admin rules.

**Documentation.** Docstrings on every service method explaining *why*, not *what*. Inline
comments reserved for non-obvious decisions. The README is written for someone cloning the repo
cold with no context.

**Accessibility.** Semantic landmarks, focus traps in modals, visible focus rings, `aria-live`
for incoming messages, full keyboard navigability. Signal ships accessible; a clone that
doesn't isn't a faithful clone.

---

## 8. Delivery Plan

| Phase | Work | Commits land as |
|---|---|---|
| 0 | This document, repo scaffold, tooling, CI | `docs:`, `chore:`, `ci:` |
| 1 | Schema, models, migrations | `feat(db):` |
| 2 | Auth + onboarding API | `feat(auth):` |
| 3 | Contacts + conversations API | `feat(conversations):` |
| 4 | Messaging API, receipts, reactions, replies, attachments | `feat(messages):` |
| 5 | WebSocket layer, presence, typing | `feat(realtime):` |
| 6 | Seeds + backend test suite | `feat(seed):`, `test:` |
| 7 | Frontend scaffold + Signal design system | `feat(ui):` |
| 8 | Auth UI, conversation list, chat pane | `feat(auth-ui):`, `feat(chat):` |
| 9 | Groups, settings, placeholders, shortcuts, responsive | `feat(groups):`, `feat(settings):` |
| 10 | Docker, deploy configs, README | `chore(docker):`, `docs:` |
| 11 | Full verification pass, deploy | `test:`, `fix:` |

---

## 9. Assumptions & Scope Boundaries

Stated up front so they read as decisions, not gaps:

1. **Encryption is simulated.** The envelope abstraction and key-id plumbing are real; the
   cipher is not. The app must never claim otherwise in its own UI copy without qualification.
2. **OTP is a fixed development code** (`123456`) with no SMS provider. Rate limiting and
   single-use consumption are still implemented so the flow is realistic.
3. **SQLite is the production database**, as mandated. It is correct for this workload
   (single-writer, modest concurrency) with WAL enabled; the repository layer is
   dialect-agnostic so Postgres is a connection-string change.
4. **Single backend process.** Presence, typing and the connection registry are in-memory.
   Correct at this scale; the Redis path for horizontal scaling is documented in §3.4.
5. **Attachments go to local disk** behind a storage interface, with S3 as the documented
   swap. No object-storage account is assumed to exist.
6. **Signal's visual language is reconstructed from its published design**, not copied from its
   source. No Signal code, assets or trademarks are vendored — original work throughout, per
   the plagiarism clause.
7. **Calls, Stories and Linked Devices are designed placeholders**, exactly as the brief permits.

---

## 10. Notes for the Evaluation Interview

The brief is explicit that every line must be explainable. The questions most likely to come
up, and where the answers live:

- *Why FastAPI over Django?* → §3.1
- *Why do sends go over REST when you have a WebSocket open?* → §3.4
- *How do read receipts work in a group of seven?* → §4, per-recipient receipt rows
- *How is an unread count computed without a counter column?* → §4, read watermark
- *What happens if the socket drops mid-conversation?* → exponential-backoff reconnect, then a
  history refetch that reconciles against the query cache; nothing is lost because the socket
  was never the write path
- *How would this scale to multiple servers?* → §3.4, `ConnectionManager` behind an interface
- *Where would real encryption plug in?* → §3.5, `EncryptionEnvelope` / `MockCipher`
- *Why is `last_message_at` denormalised?* → §4, sort cost on the conversation list
- *How are duplicate messages prevented on retry?* → §5, `client_message_id` idempotency key
