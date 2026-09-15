# Persistent Chat History (ChatGPT-style New Chat + History)

Status: approved 2026-09-15. Implemented same day.

## Problem

The "PDF Sohbet" (PDF Chat) feature (`backend/services/chat_service.py`,
`backend/routers/chat_router.py`, `frontend/src/pages/Chat/Chat.jsx`) keeps
the entire conversation in React state only. Nothing is persisted — not
even `localStorage`. Consequences:

- There is no way to see or return to a past conversation.
- Any remount of the `Chat` component (a real page reload, a route
  change, or anything else that unmounts it) silently wipes the
  conversation with no recovery path.

## Goals

1. Conversations are persisted server-side (Postgres), per user.
2. A ChatGPT-style "New Chat" + conversation list lets the user start a
   fresh conversation and switch back to previous ones.
3. Whatever was causing messages to disappear "on their own" is fixed by
   construction: the active conversation id is restored from
   `localStorage` on mount and its messages re-fetched from the server,
   so no client-side-only state loss is possible.
4. Each conversation remembers which PDFs it was scoped to (the "Belgeler"
   selection) and restores that scope when reopened.
5. Conversations can be deleted from the list.

## Non-goals

- Renaming conversation titles (title is auto-generated only).
- Editing/regenerating past messages.
- Sharing conversations between users.
- Pagination of the conversation list (a user's list is expected to stay
  small; a simple `LIMIT` is enough for now).

## Data model

New tables (Postgres, via Alembic migration `3e7fcd3cc5cd`, following
`378a33e7b67e` head):

```sql
CREATE TABLE chat_conversations (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    pdf_names   JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_chat_conversations_user_updated
    ON chat_conversations(user_id, updated_at DESC);

CREATE TABLE chat_messages (
    id              SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    sources         JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_chat_messages_conversation
    ON chat_messages(conversation_id, created_at);
```

`pdf_names` and `sources` are stored as JSONB rather than normalized
tables — both are small, always read/written as a whole, and never
queried by content, so JSONB keeps this simple without a real cost.

## Title generation

Per user decision: `"<gün> <ay kısaltması> <SS:DD> — <ilk seçili PDF adı>"`,
e.g. `15 Eyl 14:30 — dron_projesi.pdf`. If no PDF is selected:
`15 Eyl 14:30 — Genel Sohbet`. Generated once, at conversation creation,
in `services/chat_service.py`; never regenerated.

## Backend API (`routers/chat_router.py`)

All endpoints require auth (`get_current_user`) and are scoped to
`user_id`; accessing another user's conversation is a 404 (not 403 — to
avoid confirming the id exists).

- `GET /chat/conversations` → `{ conversations: [{id, title, updated_at}] }`,
  ordered by `updated_at DESC`, `LIMIT 200`.
- `GET /chat/conversations/{id}` → `{ id, title, pdf_names, messages: [{role, content, sources, created_at}] }`.
  404 if missing or not owned.
- `DELETE /chat/conversations/{id}` → `{ success: true }`. 404 if missing
  or not owned. Cascades to `chat_messages`.
- `POST /chat/message` — body becomes
  `{ message, pdf_names: string[], conversation_id?: int|null }`
  (the `history` field is **removed** — the server now sources
  conversation history from `chat_messages` itself, which is the single
  source of truth and can't drift from what's actually stored).
  - `conversation_id` omitted/null → a new conversation is created (title
    generated as above, `pdf_names` stored as given).
  - `conversation_id` given → ownership verified (404 if not owned); the
    conversation's `pdf_names` is overwritten with the current selection
    (scope can drift within a conversation — last selection wins) and
    `updated_at` is bumped.
  - Response gains `conversation_id` (so a newly created conversation's
    id reaches the client) and `title` (only present when a conversation
    was just created, so the client can insert it into the sidebar list
    without a second round trip).
  - Both the user message and the assistant reply are persisted (with
    `sources`) after the LLM call succeeds. If the LLM call fails, only
    nothing is persisted for that turn (no partial assistant message).

## Backend service changes

`services/chat_service.py`:
- `run_chat` signature changes from `(user_id, message, pdf_names, history)`
  to `(user_id, message, pdf_names, conversation_id)`. It now loads the
  last `MAX_HISTORY_TURNS` messages for `conversation_id` from Postgres
  itself (new `pg_get_recent_messages`) instead of trusting a
  client-supplied list.
- Conversation creation, title generation, and message persistence live
  in `chat_router.py` (thin orchestration) calling new
  `services/database/postgres_service.py` functions:
  `pg_create_conversation`, `pg_list_conversations`,
  `pg_get_conversation`, `pg_get_conversation_messages`,
  `pg_delete_conversation`, `pg_add_message`, `pg_touch_conversation`
  (updates `pdf_names` + `updated_at`), `pg_get_recent_messages`.

## Frontend (`frontend/src/pages/Chat/Chat.jsx`)

- New `services/service.js` functions: `listConversations`,
  `getConversation`, `deleteConversation`; `sendChatMessage` gains a
  `conversationId` param and no longer sends `history`.
- A new history rail is added to the existing sidebar (which currently
  only lists PDFs to scope to): a "Yeni Sohbet" button at the top and the
  conversation list below it, each row showing the title and a delete
  (trash) icon on hover. The existing PDF-selection panel is unchanged
  in behavior, just visually grouped under this.
- State: `activeConversationId` (nullable). Persisted to
  `localStorage` under a per-feature key so it survives reloads.
  - On mount: read from `localStorage`; if present, call
    `GET /chat/conversations/{id}`. On success, populate `messages` and
    `selected` (PDF scope) from the response. On 404 (deleted/foreign),
    clear the stored id and fall back to the empty "new chat" state.
  - Conversation list is fetched independently on mount for the sidebar.
- Sending a message: unchanged UX, but `send()` now passes
  `activeConversationId`. If the response includes a new
  `conversation_id` (i.e., this was the first message of a new chat),
  the component adopts it as `activeConversationId`, writes it to
  `localStorage`, and prepends `{id, title, updated_at: now}` to the
  sidebar list using the returned `title`.
- "Yeni Sohbet" button: clears `messages`, `selected`, and
  `activeConversationId` (and the `localStorage` key) — no DB row is
  created until the next message is actually sent.
- Clicking a past conversation in the list: if it's already active,
  no-op; otherwise fetch it the same way as the mount path.
- Deleting a conversation: calls `DELETE`, removes it from the list; if
  it was the active one, resets to the empty "new chat" state (same as
  clicking "Yeni Sohbet").

## Error handling

- Any conversation-list/get/delete failure shows a small inline error in
  the sidebar (existing app has no toast system) and does not block
  message sending.
- `POST /chat/message` failure behavior is unchanged from today (error
  bubble in the message list).

## Testing

The codebase has no automated test suite today. Verification is manual,
run after implementation:

1. Start a new chat, send a message with no PDF selected → conversation
   appears in the sidebar with a "Genel Sohbet" title.
2. Select a PDF, send a message in a new chat → title includes that PDF's
   name.
3. Reload the page → the same conversation and its messages reappear
   (this is the direct regression test for the reported bug).
4. Start a second new chat, switch back to the first via the sidebar →
   correct messages and PDF scope reload.
5. Delete the active conversation → falls back to empty state; delete a
   non-active one → just disappears from the list.
6. Try to fetch/delete another user's conversation id directly (e.g. via
   the API) → 404.
