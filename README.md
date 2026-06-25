# tauri_py

A **desktop browser-automation studio**. It drives real Chrome sessions to run
long-lived scraping/automation jobs (e.g. a LinkedIn post scraper), tracks every
run in a local SQLite database, and streams live progress into a React UI — with
cooperative **pause / resume / stop** and automatic recovery from browser
crashes.

It is built as three cooperating layers wired over a single IPC bus:

| Layer | Role | Tech |
|-------|------|------|
| **Frontend** | UI, routing, run dashboards, live log/results | React 19 + Vite + Tailwind + shadcn/Base UI (WebView) |
| **Rust host** | Orchestration, route registry, SQLite, sidecar lifecycle, pushes events to the UI | Tauri 2, `sqlx` |
| **Python sidecar** | Playwright/Chrome automation, the task framework, session cookies | Python + Playwright (child process) |

### What it does

- **Sessions** — create named, persistent browser profiles per platform; log in
  once (cookies/storage are saved to disk), check login status, or seed from your
  system Chrome profile. A session can be reused across many runs.
- **Runs** — start a task against one or more **inputs** (e.g. profile URLs). Each
  run is persisted: config (`params`), input rows, scraped result items, log, and
  status. Results de-duplicate by key, so a paused or crashed run **resumes from a
  checkpoint** without re-emitting what it already collected.
- **Live UI** — a runtime drawer shows per-run tabs with a streaming log, progress
  metrics, results, and lifecycle controls. On app startup, runs left `running`
  are marked `shutdown` and are resumable.
- **Resilience** — the task framework owns the Chrome lifecycle; if the browser
  dies mid-scrape it relaunches, re-navigates to the last URL, and retries the
  operation once, transparently to the task.

> 📐 Architecture, module boundaries, and contribution rules live in
> [`context.md`](./context.md). This README focuses on **what it does** and the
> two public-facing APIs: **IPC** and the **scraper/task API**.

---

## Getting started

```bash
pnpm install              # JS deps
uv sync                   # Python deps (Playwright sidecar)
pnpm dev                  # run the Tauri app (spawns the Python sidecar)
```

| Script | Purpose |
|--------|---------|
| `pnpm dev` | Run the full Tauri app (host + UI + sidecar). |
| `pnpm dev:ui` | Vite dev server for the UI only. |
| `pnpm build:daemon` | PyInstaller-bundle the Python sidecar into `src-tauri/resources/sidecar/`. |
| `pnpm build` | Build the distributable Tauri app (run `build:daemon` first). |

In **dev**, the host spawns the sidecar with `uv run python py-sidecar/main.py`;
in a **packaged** build it runs the bundled `tauri-py-daemon` binary.

---

## IPC communication API

There are **three message paths**. The frontend never talks to Python directly —
everything goes Frontend → Rust → (optionally) Python.

```
 React UI  --invoke(handle_frontend_request)-->  Rust host
 React UI  <--Tauri event: daemon://{channel}--  Rust host
 Rust host <----- BusMessage over stdin/stdout ----->  Python sidecar
```

### 1. Frontend → Rust (request/response RPC)

The UI calls a single Tauri command, `handle_frontend_request`, with a
`{ route, payload }` envelope. The Rust host dispatches `route` to a handler
registered via `app.route(...)`.

```ts
// src/lib/api.ts
Backend.request<T>(route, payload?)
  // → invoke("handle_frontend_request", { req: { route, payload } })
```

Routes are dot-separated `{domain}.{verb}`. The handler returns a JSON result or
an error string.

| Route | Payload | Does |
|-------|---------|------|
| `sessions.list` | `{ platform }` | List sessions for a platform. |
| `sessions.create` | `{ platform, name }` | Create a persistent session profile. |
| `sessions.create_default` | `{ platform }` | Create + sync the "Default Chrome" session from the system profile. |
| `sessions.launch` | `{ session_id, platform?, fresh? }` | Open a visible Chrome for a session (proxies `session.launch`). |
| `sessions.check` | `{ session_id, platform? }` | Verify the session is logged in. |
| `sessions.sync` | `{ session_id }` | Copy cookies/state from the system Chrome profile (Default Chrome only). |
| `sessions.stop` | `{ session_id, platform? }` | Close a session's browser. |
| `sessions.status` | `{ platform }` | Sessions + live running instances. |
| `sessions.cookies` | `{ session_id }` | Read stored cookies from `storage_state.json`. |
| `sessions.delete` | `{ session_id, platform? }` | Stop and delete a session. |
| `runs.list` | `{ platform? }` | List runs. |
| `runs.get` | `{ run_id }` | One run with status/counts. |
| `runs.inputs` | `{ run_id }` | Input rows (targets) for a run. |
| `runs.items` | `{ run_id, input_id? }` | Scraped result items. |
| `runs.start` | `{ platform, task, params, inputs }` | Create a run and start it (proxies `tasks.start`). |
| `runs.control` | `{ run_id, action }` | `pause` / `resume` / `stop` a run (resume restarts from checkpoint if the task is no longer live). |
| `runs.restart` | `{ run_id }` | Re-run from the saved checkpoint. |
| `runs.delete` | `{ run_id }` | Stop and delete a run. |
| `browser.launch` / `browser.stop` / `browser.status` / `browser.recover` / `browser.control` | `{ run_id?, headless?, action? }` | Ad-hoc browser instances (proxy to the sidecar). |
| `browser.install.status` / `browser.install.run` | `{}` | Check / install the Chrome the sidecar drives. |
| `log.lines` | `{}` | Recent sidecar stderr log lines (ring buffer). |

### 2. Rust → Frontend (push events)

The host pushes structured events to the UI over Tauri events named
`daemon://{channel}`. The payload is always `{ route, payload }` (`DaemonEvent`).

```ts
// src/lib/api.ts
Backend.subscribeDaemon<T>(channel, (evt) => { evt.route; evt.payload; });
Backend.unsubscribeDaemon(cb);
```

The **channel is the first segment of the route** (`task.item` → `daemon://runs`
for run events; `session.closed` → `daemon://session`). Common pushes:

| Channel | Routes | When |
|---------|--------|------|
| `runs` | `task.status`, `task.item`, `task.input_status`, `task.log`, `task.progress` | A task reports progress/results. The host persists then forwards. |
| `session` | `session.closed`, `session.updated` | A session's browser closed/changed. |
| `browser` | `browser.closed`, `browser.updated`, `browser.install.progress` | Ad-hoc instance + Chrome install progress. |
| `log` | `log.line` | A new sidecar stderr line. |

### 3. Rust ↔ Python (the sidecar bus)

Newline-delimited JSON `BusMessage` over the child process's stdin/stdout:

```jsonc
{ "kind": "request" | "response" | "event", "id": "<corr-id>", "route": "tasks.start", "payload": { } }
```

- **Rust → Python request:** `facade.request_with_timeout(route, payload, timeout)`
  → a Python handler registered with `Daemon.route(route, handler)`. The handler's
  return value comes back as a `response` with the same `id`.
- **Python → Rust event:** `Tauri.dispatch(event, payload)` → a Rust handler
  registered with `app.on_event(event, handler)`.
- **Python → Rust request:** `await Tauri.request(route, payload)` (responses
  correlated by `id`) — used for callbacks into the host.

Sidecar routes the host calls:

| Route | Purpose |
|-------|---------|
| `tasks.start` | Start a task: `{ run_id, task, params, inputs, resume }`. |
| `tasks.control` | `{ run_id, action: pause\|resume\|stop }`. |
| `session.launch` / `session.stop` / `session.check` / `session.sync` / `session.status` | Persistent session control. |
| `browser.launch` / `browser.stop` / `browser.status` / `browser.recover` / `browser.control` | Ad-hoc browser instances. |
| `browser.install.status` / `browser.install.run` | Manage the bundled Chrome. |

Events the sidecar emits back (see the push table above): `task.*`, `session.*`,
`browser.*`.

#### Registering an IPC handler

```python
# py-sidecar/modules/<domain>/routes.py
from runtime import Daemon, Tauri

async def my_handler(payload: dict) -> dict:
    Tauri.dispatch("my.progress", {"pct": 50})   # push an event to the host
    return {"ok": True}

Daemon.route("my.verb", my_handler)
```

```rust
// src-tauri/src/modules/<domain>/routes.rs
app.route("my.verb", move |facade, req: MyReq| async move {
    facade.request_with_timeout("my.verb", payload, timeout).await   // proxy to Python
});
app.on_event("my.progress", |facade, payload: Value| async move {
    facade.push_ui_route("my.progress", payload);                    // forward to the UI
});
```

---

## Scraper / Task API

A **task** is the unit of automation. The framework (`modules/tasks/`) owns the
hard parts — launching Chrome from the run's session, recovering from crashes,
looping over input rows, reporting status, and de-duplicating results — so a task
only writes domain logic. Tasks are identified by a `{platform}.{task}` key
(e.g. `linkedin.posts_scraper`) registered on all three layers with the same key.

### Authoring a task

Subclass `BaseTask` and implement `run(page)` (plus optional `resume(checkpoint)`).
The framework calls `run` **once per input row** with a ready
[`ScrapedPage`](./py-sidecar/browser/page.py) (a Playwright `Page` wrapper that
auto-recovers from browser crashes):

```python
# py-sidecar/modules/<platform>/<task>/task.py
from browser.page import ScrapedPage
from modules.tasks.base import BaseTask
from modules.tasks.registry import register_task

TASK_KEY = "example.scraper"

class ExampleTask(BaseTask):
    def resume(self, checkpoint: dict) -> None:
        # Seed/restore per-input state. Empty dict on a fresh run; the last
        # cursor on resume. Use checkpoint.get(..., default) for both.
        self._seen = set(self._seen_keys)
        self._next = int(checkpoint.get("resume_from_ordinal") or 0) + 1

    async def run(self, page: ScrapedPage) -> None:
        url = self.input.get("url")                 # current input row's data
        limit = self.params.get("limit")            # run-level params
        await page.visit(url, wait_until="domcontentloaded")

        while not self.stopped:
            if await self.checkpoint(self._cursor()):   # cooperative pause/stop point
                break
            for record in await page.evaluate(EXTRACT_JS):
                self.collect(record, key=record["id"])  # emit a result (deduped by key)
            await self.sleep(1.5)                        # pause-aware sleep

register_task(TASK_KEY, ExampleTask)
```

### `BaseTask` surface

| Member | Purpose |
|--------|---------|
| `run(page)` | **Required.** Called once per input row with a `ScrapedPage`. |
| `resume(checkpoint)` | Restore per-input state before each `run`; receives the last `cursor` (empty on fresh runs). May be async. |
| `self.params` | Run-level config dict (session, headless, limits, …). |
| `self.input` | The current input row's `data` dict. |
| `collect(data, key=None, ordinal=None)` | Emit one result record. De-duplicates by `key` (→ `data["_key"]` → auto-ordinal); already-seen keys are skipped silently. |
| `checkpoint(cursor=None)` | Cooperative pause/stop point; records `cursor` for resume. Returns `True` when the task should exit. Call between units of work. |
| `sleep(seconds)` | Pause-aware sleep; returns `True` if stopped during the wait. |
| `self.stopped` | `True` once a stop was requested — check inside loops. |
| `set_cursor(c)` / `self.cursor` | Record / read the current input's resume cursor. |
| `enqueue/dequeue/has_queue/drain(key)` | Named in-task work queues (e.g. crawl frontiers). |
| `self.ctx` | The `TaskContext` for direct event emission. |

`TaskContext` (also reachable via `self.ctx`) emits the bus events the host turns
into DB writes + UI pushes: `ctx.log(line, level=)`, `ctx.item(...)`,
`ctx.status(...)`, `ctx.input_status(...)`, `ctx.progress(**metrics)`.

### Registering the task on all three layers

The same key must be registered in each layer:

1. **Python** — `register_task("example.scraper", ExampleTask)` (imported via
   `modules/__init__.py`).
2. **Rust** — usually nothing task-specific: the generic `runs` module proxies
   `runs.start` → `tasks.start`. Add a Rust module only for new domain routes/DB.
3. **Frontend** — `registerTaskType({ key, platform, label, icon, capabilities,
   ResultsView, resultsPath })` (`src/lib/tasks.ts`) so the runtime drawer knows
   which controls and results view to render.

### Data model (persisted per run)

| Table | Holds |
|-------|-------|
| `runs` | One execution: `platform`, `task`, `status`, `params`, `log`, `pause_info`, `error`, counts, timestamps. |
| `run_inputs` | Input rows (targets), e.g. profile URLs — `data` JSON + per-input `cursor` checkpoint. |
| `run_items` | Result records, keyed by `item_key` (unique per run) and linked to their `input_id`. |

Resume works because `run_items` keys are fed back as `seen_keys` and the input's
`cursor` is replayed into `resume(checkpoint)` — so a restarted run skips
everything already collected.

### Example: the LinkedIn post scraper

`linkedin.posts_scraper` ([`py-sidecar/modules/linkedin/posts/`](./py-sidecar/modules/linkedin/posts/))
is the reference task.

- **Inputs:** `{ profile_url }` per LinkedIn member/company profile.
- **Params:** `{ session_id, headless, post_count?, start_from?, post_matcher? }`
  — `post_matcher` is an optional JS expression evaluated per post in the page to
  filter matches; `post_count` limits matched posts.
- **Flow:** navigate to the profile's recent-activity feed → verify login →
  snapshot a top-of-feed "anchor" → scroll, expand truncated posts, extract via
  injected JS, run the matcher, and `collect` each post (id, text, author,
  timestamp, reaction/comment/repost counts, media URLs). Anchor + ordinal
  bookkeeping in the cursor means a paused/closed run resumes without
  re-emitting seen posts.

Start it from the UI (the LinkedIn → Post Scraper page) or via the API:

```ts
// src/modules/linkedin/api.ts
LinkedinApi.startPostScrape(
  { session_id, headless: true, post_count: 50, post_matcher: "" },
  ["https://www.linkedin.com/in/jane-doe/"],
);
```

---

## Recommended IDE setup

[VS Code](https://code.visualstudio.com/) +
[Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) +
[rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer),
plus Pyright for the Python sidecar (paths configured in `pyproject.toml`).
