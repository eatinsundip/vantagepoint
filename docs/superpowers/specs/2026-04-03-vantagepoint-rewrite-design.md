# VantagePoint Rewrite Design

**Date:** 2026-04-03
**Status:** Approved

## Overview

Rewrite the existing Bash-based bug bounty recon toolkit (`bug_hunting-`) as a Python web application living in the `vantagepoint` repo. The goal is a self-hosted "fire and forget" attack surface scanner with a browser UI, scheduled scans, live output streaming, and Discord alerts on new findings.

---

## Architecture

**Stack:**
- **FastAPI** + **Uvicorn** — async HTTP server
- **SQLAlchemy** + **SQLite** — data persistence; SQLAlchemy chosen for easy future migration to Postgres
- **APScheduler** — cron-style scan scheduling, embedded in-process (no Redis/Celery)
- **Jinja2 + HTMX** — server-rendered UI with dynamic updates, no JS framework
- **Server-Sent Events (SSE)** — stream live scan output to the browser
- **Discord webhooks** — direct HTTP POST; `notify` dependency dropped

Go tools (`subfinder`, `httprobe`, `fff`, `nmap`, `nuclei`, etc.) are kept as-is and called via `asyncio.create_subprocess_exec`. Results are identical to the current Bash pipeline.

**Directory layout:**
```
vantagepoint/
├── app/
│   ├── main.py          # FastAPI app, route registration
│   ├── db.py            # SQLAlchemy engine + session setup
│   ├── models.py        # ORM models: Project, ScanRun, Finding, Scope
│   ├── scanner.py       # Async subprocess wrappers per Go tool
│   ├── pipeline.py      # Orchestrates tool chain for a scan run
│   ├── scheduler.py     # APScheduler setup, job CRUD
│   ├── notifier.py      # Discord webhook sender
│   └── templates/       # Jinja2 HTML + HTMX partials
├── setup.sh             # Kept — installs Go tools
├── requirements.txt
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-03-vantagepoint-rewrite-design.md
```

---

## Data Model

### `projects`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | Unique project name |
| discord_webhook_url | TEXT | Per-project Discord channel |
| scan_schedule | TEXT | Cron expression or NULL |
| created_at | DATETIME | |

### `scope`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| project_id | FK → projects | |
| value | TEXT | Domain or IP range |

### `scan_runs`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| project_id | FK → projects | |
| status | TEXT | `running` / `complete` / `failed` |
| triggered_by | TEXT | `manual` / `scheduled` |
| error_message | TEXT | Set on failure |
| started_at | DATETIME | |
| finished_at | DATETIME | |

### `findings`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| project_id | FK → projects | |
| scan_run_id | FK → scan_runs | Run that first discovered this |
| type | TEXT | `subdomain` / `ip` / `web_host` / `nmap_port` |
| value | TEXT | The discovered value |
| first_seen_at | DATETIME | |
| last_seen_at | DATETIME | Updated on each scan |

**Unique constraint:** `(project_id, type, value)` — deduplication happens at insert time. A new unique row triggers a Discord notification.

---

## Scan Pipeline

Steps run sequentially; each feeds into the next. Output is streamed line-by-line — results appear in the UI as they arrive, not buffered to end.

```
scope entries
    → subfinder (subdomain enumeration)
    → host lookups (A record → IPs)
    → httprobe (live web hosts)
    → fff (HTTP headers, depth=1)
    → nmap (top 1000 ports on discovered IPs)
```

Each step:
1. Calls the Go tool via `asyncio.create_subprocess_exec`
2. Reads stdout line-by-line
3. Inserts each line as a `Finding` (dedup via unique constraint)
4. New findings trigger `notifier.send()` to Discord
5. Yields the line to the SSE endpoint for live browser display

If a tool is missing from `$PATH`, the step logs a clear error to the `scan_run` record and continues with remaining steps rather than aborting the whole pipeline.

---

## Web UI & Routes

UI: plain HTML + Pico.css (single stylesheet, zero config) + HTMX for dynamic updates. No login — single user, localhost.

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Dashboard: project list, last scan status, Run Scan button |
| `/projects/new` | GET/POST | Create project (name + scope) |
| `/projects/{id}` | GET | Project detail: findings tabs, scan history |
| `/projects/{id}/scan` | POST | Trigger manual scan, redirect to live output |
| `/projects/{id}/settings` | GET/POST | Edit scope, webhook URL, cron schedule |
| `/scans/{id}/stream` | GET | SSE stream of live tool output |

Changing a project's schedule via the settings page updates the APScheduler job live without a server restart.

---

## Error Handling

- Missing Go tool on `$PATH` → step skipped, error logged to `scan_run.error_message`, pipeline continues
- Failed scan run → `status=failed`, error visible in scan history UI
- Discord webhook failure → logged, does not abort scan

---

## Testing

- One integration test per pipeline step using `example.com` as a safe test target
- Unit tests for dedup logic (unique constraint behavior) and Discord notifier (mock webhook)
- No mocking of Go tool invocations in integration tests — real tool output validates end-to-end behavior

---

## Out of Scope (for now)

- Multi-user auth (architecture leaves room: single-user assumption is in UI only, not data model)
- Mullvad/VPN integration
- Container/Docker support
- Nuclei automated scanning (tool is installed but not wired into the default pipeline — can be added as an optional step)
