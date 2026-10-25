# BookLeaf Author Support & Communication Portal

A web application where BookLeaf authors raise support tickets and BookLeaf's operations team triages, answers and tracks them, with AI assistance that **suggests and never sends**.

- **Live demo:** [frontend URL] · **API docs (Swagger):** [backend URL]/docs
- **Test accounts:** see [Demo credentials](#demo-credentials)

## Features

**Author portal**
- Email/password login; every query is scoped to the signed-in author.
- Dashboard (books, royalty earned / paid / pending, ticket counts), My Books (search, filter, sort; books in production show "Not yet published" and "—", never fake zeros), Submit a Query, My Tickets with a live conversation view.
- Replies and status changes appear without a page refresh.

**Admin portal**
- Operations dashboard (live metrics, "needs attention first" and "waiting longest" lists).
- Ticket queue: filter by status, priority, category, assignee and date range; search by ticket number, subject, author name or email; urgency-first sorting; filters live in the URL.
- Ticket workspace: author and book context, conversation, internal notes (visually distinct and never visible to authors), category/priority overrides, status and assignment controls, audit history.
- AI: automatic category and priority on every new ticket, and an editable AI draft reply on demand.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, React Router |
| Backend | Python, FastAPI, Pydantic v2, async PyMongo |
| Database | MongoDB (Atlas) |
| Auth | JWT (HS256) bearer tokens, bcrypt password hashes |
| AI | `openai/gpt-oss-120b` on Groq, through the OpenAI-compatible API |
| Real-time | WebSocket, with polling fallback |
| Tests | pytest (backend, 208 tests) |

## Architecture

```
React SPA ──REST + WebSocket──▶ FastAPI
 /author/*  /admin/*             ├─ api/        routers, auth + role dependencies, WebSocket endpoint
                                 ├─ schemas/    request/response models (author and admin shapes are separate)
                                 ├─ services/   business rules: tickets, books, admin actions, AI orchestration
                                 ├─ ai/         provider adapter, knowledge base, prompts, triage, drafting, guardrails
                                 ├─ realtime/   connection hub + event publishers
                                 └─ db/         Mongo connection, indexes, money helpers
                                       │
                                  MongoDB (users, authors, books, tickets, ticket_messages,
                                           audit_events, ai_calls, counters)
```

Key decisions:

- **Routes stay thin; rules live in services.** The AI layer has no web or database imports (`ai/` works on plain dataclasses), which is what makes it testable with a fake provider.
- **Ownership is part of every query.** Author lookups filter on `{_id, author_id}` in one query, and a miss returns 404 (not 403), so IDs can't be probed. The author's identity always comes from the token. Request bodies have no `author_id`, and schemas reject unknown fields (`extra="forbid"`).
- **Internal notes are structurally separate.** Public replies and notes live in one collection with a `kind` field. Author endpoints go through a single query function that hard-codes `kind = public`, and the realtime layer never notifies authors about notes.
- **The AI recommendation is stored apart from the final value** (`ai_category` vs `category`, plus `category_overridden`). An admin's choice is never overwritten, even by an AI call that finishes after the override (the write is conditional on the flag).
- **Authorization is checked against the database on every request** (role and active flag are re-read), so a forged role claim or a deactivated user gets nothing.
- **Money is stored as `Decimal128`**, never floats.
- **No migration tool.** MongoDB has no schema to migrate. Structure is enforced by Pydantic at the API boundary, and indexes are created idempotently at startup (`db/mongo.py: ensure_indexes`).

## Local setup

**Prerequisites:** Python 3.10+, Node 20.19+, a MongoDB database (Atlas free tier or local), and an API key for an OpenAI-compatible LLM (optional: without it, tickets and manual replies work and AI features report "not configured").

```bash
# 1. Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows: Copy-Item .env.example .env
# edit .env: MONGODB_URI, JWT_SECRET, LLM_API_KEY, SEED_AUTHOR_PASSWORD, SEED_ADMIN_PASSWORD

python -m app.scripts.seed         # 10 authors, 18 books, 12 users (idempotent)
python -m app.scripts.seed_demo    # 10 demo tickets (idempotent; uses real AI triage if a key is set)
uvicorn app.main:app --reload      # http://localhost:8000  (Swagger: /docs)

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173  (use "localhost", not 127.0.0.1)
```

In development Vite proxies `/api` (including the WebSocket) to port 8000, so no CORS configuration is needed. Run the backend as a single process (see Limitations).

### Environment variables

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` or `production`. Production refuses to start with a JWT secret under 32 characters or a `localhost` CORS origin |
| `MONGODB_URI`, `MONGODB_DB` | Database connection and name |
| `JWT_SECRET`, `ACCESS_TOKEN_MINUTES` | Token signing key and lifetime (default 60) |
| `CORS_ORIGINS` | Comma-separated allowed origins; also validated on WebSocket connections |
| `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS` | Any OpenAI-compatible endpoint. `LLM_PROVIDER` is an informational label |
| `SEED_AUTHOR_PASSWORD`, `SEED_ADMIN_PASSWORD` | Passwords given to seeded demo accounts (set only on first creation) |
| `VITE_API_URL` (frontend) | API origin in production; empty in development |

`.env` files are git-ignored; only `.env.example` (placeholders) is committed.

### Database setup and seeding

The seed script reads `backend/data/bookleaf_sample_data.json` (the supplied dataset: 10 authors, 18 books). It upserts by `email`, `author_code` and `book_code`, so it can be re-run safely. It verifies the dataset's own arithmetic (`copies × rate = earned`, `paid + pending = earned`) and reports any mismatch. Nothing is recomputed or invented. Fields that are null in the data (for example MRP of a book in production) stay null.

### Tests

```bash
cd backend
pytest -q          # 208 tests; uses a separate `bookleaf_test` database that it creates and drops
```

The tests need a reachable MongoDB but never call a real LLM (the provider is replaced by a fake in every test). They cover: authentication and token forgery; cross-author access (author A gets 404 on author B's books and tickets); admin-only routes; internal-note privacy; status transitions; AI overrides surviving later AI runs, including a race; AI failure modes (rate limit, timeout, malformed output, missing key) never blocking ticket creation or manual replies; realtime event scoping; and the evaluation harness. The frontend has no automated tests; it was verified by hand (see Limitations).

## API

Base path `/api/v1`. Interactive documentation is generated by FastAPI at `/docs`. All routes except login require `Authorization: Bearer <token>`.

| Method & path | Role | Purpose |
|---|---|---|
| `POST /auth/login` | public | Email + password → JWT and user |
| `GET /auth/me` | any | Current user |
| `GET /author/dashboard` | author | Book and royalty totals, ticket counts |
| `GET /author/books` | author | Own books; query: `q`, `published`, `sort`, `order` |
| `GET /author/books/{book_id}` | author | One own book (404 if not theirs) |
| `POST /author/tickets` | author | Create ticket (`book_id` or null for General) |
| `GET /author/tickets` | author | Own tickets; query: `status`, `page`, `page_size` |
| `GET /author/tickets/{n}` | author | Own ticket with **public** replies only |
| `GET /admin/metrics` | admin | Dashboard metrics and urgent / longest-waiting lists |
| `GET /admin/admins` | admin | Active admins (assignee dropdown) |
| `GET /admin/tickets` | admin | Queue; query: `status`, `category`, `priority` (repeatable), `assignee`, `date_from`, `date_to`, `q`, `sort`, `page`, `page_size` |
| `GET /admin/tickets/{n}` | admin | Ticket + author, book, AI fields, all messages, audit trail |
| `PATCH /admin/tickets/{n}` | admin | Change `status`, `category`, `priority`, `assignee_id` |
| `POST /admin/tickets/{n}/notes` | admin | Internal note (never shown to the author) |
| `POST /admin/tickets/{n}/replies` | admin | Public reply (idempotent via `client_msg_id`; optional `set_status`) |
| `POST /admin/tickets/{n}/draft` | admin | AI draft. Nothing is stored or sent |
| `POST /admin/tickets/{n}/triage` | admin | Re-run AI classification |
| `GET /health` | public | Liveness + DB check |
| `WS /ws` | any | Realtime events; first message `{"type":"auth","token":"..."}` |

Status transitions are enforced by the server: Open → In Progress / Resolved / Closed; In Progress → Open / Resolved / Closed; Resolved → In Progress / Closed; Closed is final. A concurrent edit returns `409`.

**Errors** always use one shape: `{"error": {"code": "...", "message": "...", "details": [{"field": "...", "message": "..."}]}}`. Status codes: 401 not authenticated, 403 wrong role, 404 not found (including other people's resources), 409 conflict or invalid transition, 422 validation, 429 and 5xx for AI problems with a safe message. Unhandled exceptions return a generic 500 and are logged server-side only.

**WebSocket events** carry identifiers only, for example `{"type":"ticket.updated","ticket_number":1003,"reason":"reply","at":"..."}`. They never contain message text or notes, so a client reacts by refetching through the normal (authorised) REST API. Authors receive events about their own tickets only, and never about internal notes or assignment.

## AI integration

### What the AI does

| Feature | When | Output |
|---|---|---|
| Triage | Automatically after a ticket is created (background task) | Category (one of six), priority (Critical/High/Medium/Low), one-sentence rationale |
| Draft reply | When an admin clicks "Draft with AI" | Editable text, a short "worth confirming" list, guardrail warnings |

The AI never sends anything. A draft only becomes a message when an admin edits it and presses Send, and the stored message records only that it started from a draft.

### Prompt strategy

- **Triage:** one call returns category and priority as JSON. The system prompt defines each category and gives severity guidance (money owed, wrong ISBN on a live book, severe print defect → High or Critical; bio and metadata changes → Low). It receives the ticket text plus the linked book's stored facts, **not** the author's name or email.
- **Draft:** the system prompt holds hard rules (use only stated facts; never claim an action has happened; quote stored money figures exactly and never calculate entitlements; do not infer production stage from elapsed time; commit only to investigating, escalating and giving a timeline), the style rules from the tone guide, and the relevant policy text. The user message holds the ticket, a labelled `<facts>` block (book record, today's date, a note that no verification, reprint, re-sync, escalation or payout is recorded), and the last six *public* replies.
- **Computed facts instead of inference:** policy checks that depend on dates are calculated in code and passed as facts. For example, "published for N months, nothing paid, balance above the ₹1,000 minimum → appears overdue; own it and escalate within 48 hours". The model is never asked to do date arithmetic.
- **Untrusted text:** ticket and reply text is wrapped in delimiter tags, with closing tags neutralised, and the prompt states that it is data, not instructions.

### Knowledge base use and cost control

- The knowledge base (`ai/knowledge_base.py`) is structured by topic. A draft receives only the sections for the ticket's category plus the tone guide. If a ticket's category is unconfirmed (triage failed and no admin set it), the full knowledge base is sent and the prompt says so.
- Only the current ticket, its book and the last six public replies are sent. Internal notes are never included.
- Triage runs once per ticket (skipped if already classified). A forced re-run is an explicit admin action.
- Drafts are generated on demand, never cached across tickets or authors, and limited to 10 per ticket per hour.
- Output is capped (1,000 tokens for triage, 2,500 for drafts, since this reasoning model's hidden reasoning counts toward the cap, which is run at `low` / `medium` effort).
- Every call writes an `ai_calls` row with purpose, model, latency, token counts and error code (no prompts, responses or secrets).
- **Measured:** triage uses about 730 input and 80 output tokens per ticket (about 0.8M tokens per 1,000 tickets); a draft uses about 1,400 input and 450–520 output tokens.

### Validation and guardrails

Model output is parsed as JSON and validated against a Pydantic schema (allowed enum values, confidence in range, length limits). Case differences and code fences are tolerated; anything else triggers **one** repair retry whose hint contains field names only, never the model's output. After that the call fails cleanly.

Drafts are also scanned by deterministic checks that **warn the admin** (they never block or silently edit): rupee amounts not present in the ticket's data, placeholders such as `[Name]`, claims that an action "has been verified / triggered / reprinted…", and promises of payment. These checks are advisory and do not catch every kind of over-promising, which is why an admin must review every draft.

### Error handling and graceful degradation

| Situation | What happens |
|---|---|
| No API key | AI calls return `503 ai_not_configured` ("You can still reply manually") |
| Rate limit | `429` with `Retry-After`; ticket creation unaffected |
| Timeout / provider outage | `504` / `503`; one SDK retry first |
| Invalid or empty model output | One repair retry, then `502 ai_bad_output` |
| Triage fails after ticket creation | Ticket exists with placeholder category/priority, `classification_status = failed` and the error code. The queue flags it ("AI failed: set manually") and an admin can set values or re-run |

Provider details, keys and stack traces never reach the client. The manual reply editor is always available, and a failed re-run never downgrades an earlier successful classification.

### Model choice

`openai/gpt-oss-120b` on Groq: an open-weight model with an OpenAI-compatible API, JSON mode, low cost and sub-second to ~2 s latency (measured), which suits short structured tasks and interactive drafting. The adapter (`ai/provider.py`) is provider-agnostic: switching to OpenAI, Anthropic's compatible endpoint or another host means changing `LLM_MODEL`, `LLM_BASE_URL` and `LLM_API_KEY`, not code. Trade-off: as a reasoning model it spends hidden tokens, so output caps are generous and reasoning effort is set low.

### Evaluation

28 hand-labelled tickets built on the real sample dataset (easy, ambiguous and adversarial cases, including a prompt-injection attempt, Hinglish, a vague ticket, a multi-issue ticket and a thank-you that mentions "print quality"). Run with `python -m app.scripts.ai_eval`; the full report is `backend/eval/RESULTS.md`.

| Metric (28 tickets, model `openai/gpt-oss-120b`) | Result |
|---|---|
| Category in the accepted set | 28/28 (95% CI 88–100%) |
| Category equals the primary label | 27/28 |
| Priority within accepted levels | 26/28 (95% CI 77–98%) |
| Urgent tickets (Critical/High) caught | 10/10 |
| Under-triaged / over-triaged | 0 / 2 |

The two misses were both over-triage. One shows a real gap: the triage prompt does not include the ₹1,000 minimum-payout rule, so an author with ₹850 pending was rated High (the drafting prompt does contain the rule). The model's self-reported confidence was 0.98 when right and 0.99 when wrong, so it carries no information and the UI deliberately does not show it.

**Caveats:** 28 tickets is a small sample (hence the intervals); the labels and the prompt were written by the same person, so the figures are likely optimistic; one run was measured, so run-to-run variation is unknown; the prompt was not tuned after seeing results.

## Real-time updates

A WebSocket (`/api/v1/ws`) carries content-free events. Authentication is the first message (not the URL, so tokens stay out of logs), the `Origin` header is checked against `CORS_ORIGINS`, and the connection closes when the token expires. The browser refetches through REST on each event, reconnects with exponential backoff (1 s up to 30 s), does a full refetch after reconnecting (missed events are not replayed), and polls every 10 s while disconnected. Retried replies cannot duplicate (unique `client_msg_id` per ticket).

## Security

- bcrypt password hashes (run off the event loop); identical error for unknown email and wrong password; dummy hash check so timing doesn't reveal accounts.
- Authorization enforced on the server (role dependencies on every router, ownership in every author query); frontend route guards are UX only.
- Secrets only in environment variables; `.env` ignored by git; `.env.example` has placeholders; the LLM key is used server-side only.
- User-supplied search text is regex-escaped; all request bodies are validated and reject unknown fields; React escapes all rendered text and `dangerouslySetInnerHTML` is not used.
- CORS lists explicit origins (never `*`); production mode refuses weak secrets.
- Not claimed: this has not had an independent security review.

## Deployment

[Fill after Step 14: hosting, environment variables set, build and start commands, and the date you verified the live URL.]

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Admin | `admin@bookleaf.test` (also `support@bookleaf.test`) | [demo admin password] |
| Author (any of the 10 seeded) | `priya.sharma@email.com`, `ananya.reddy@email.com`, `sneha.kulkarni@email.com`, `rohit.kapoor@email.com`, `meera.nair@email.com`, `vikram.joshi@email.com`, `arjun.malhotra@email.com`, `farhan.sheikh@email.com`, `kavita.deshmukh@email.com`, `diya.chatterjee@email.com` | [demo author password] |

These are demo-only credentials for this deployment.

Good accounts to try: **Ananya** (a book that has never been paid, with a royalty ticket), **Sneha** (a book still in cover design, which shows the "not yet published" handling), **Priya** (typical live books with partial payouts).

## Known limitations

- **Background triage runs in the web process.** If the server restarts mid-task, that ticket stays pending/failed until an admin presses "Re-run AI triage". Production fix: a durable job queue with retries.
- **Single-process realtime.** The connection hub is in memory, so run one worker. Scaling out needs Redis pub/sub.
- **Sessions:** JWTs live in `localStorage` (XSS rather than CSRF exposure), there is no refresh token, no server-side logout/revocation, and a WebSocket stays open until its token expires even if the user is deactivated meanwhile. Production fix: httpOnly cookies with CSRF protection, short-lived access tokens plus refresh, a revocation list.
- **No login rate limiting or account lockout; no password reset or registration flow** (accounts come from the seed).
- **Attachments are not implemented.** The field is shown disabled with a note.
- **Authors cannot reply inside a ticket thread**, only read replies and open a follow-up ticket.
- **No email notifications.** Authors are told about replies in the portal only.
- **Queue ordering** is priority-then-age; it does not promote an old low-priority ticket above a newer high-priority one.
- **Triage prompt gap** (the ₹1,000 payout threshold), described under Evaluation.
- **Frontend has no automated tests**; the backend suite is the safety net. A browser end-to-end suite (Playwright) is the next addition.
- **AI guardrails are advisory** and heuristic; human review of every draft is part of the design.
- **Passwords are capped at 72 characters** (bcrypt's limit).