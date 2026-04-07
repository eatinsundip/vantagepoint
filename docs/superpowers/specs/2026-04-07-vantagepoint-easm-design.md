# VantagePoint EASM Web App Design

**Date:** 2026-04-07
**Status:** Approved
**Supersedes:** `2026-04-03-vantagepoint-rewrite-design.md`

---

## Overview

VantagePoint is a self-hosted External Attack Surface Management (EASM) tool. Given a company name and optional seed domains, it discovers everything visible on the public internet belonging to that company — subdomains, IPs, live URLs, open ports, HTTP metadata, and ASN/netblock information. Findings are deduplicated across scans; new discoveries trigger notifications.

The primary users are non-technical clients and security teams who should never need a terminal. Everything is accessible from a browser.

**Design goals:**
- Start self-hosted, architect for multi-tenant SaaS later
- Widely-known stack so contributors can onboard easily
- `docker-compose up` is the complete install
- Scan stages are modular and pluggable — adding new tools requires no core changes

---

## Architecture

Five services orchestrated by Docker Compose:

```
┌─────────────────────────────────────────────┐
│                 Docker Compose               │
│                                              │
│  ┌──────────┐   ┌──────────┐  ┌──────────┐  │
│  │  React   │   │ FastAPI  │  │ Postgres │  │
│  │ Frontend │──▶│ Backend  │──▶│   DB     │  │
│  └──────────┘   └────┬─────┘  └──────────┘  │
│                      │                       │
│                 ┌────▼─────┐  ┌──────────┐   │
│                 │  Celery  │◀─│  Redis   │   │
│                 │  Worker  │  │  Queue   │   │
│                 └────┬─────┘  └──────────┘   │
│                      │                       │
│               ┌──────▼──────┐                │
│               │  Scan Tools │                │
│               │  Container  │                │
│               │ (subfinder, │                │
│               │  nmap, etc) │                │
│               └─────────────┘                │
└─────────────────────────────────────────────┘
```

- **React frontend** — communicates with FastAPI via REST + WebSockets (live scan output)
- **FastAPI** — handles auth, project management, scan job dispatch, result storage
- **Celery + Redis** — background job queue; long-running scans never block HTTP requests
- **Celery Beat** — scheduled scans (cron-style, per-project)
- **Postgres** — stores users, orgs, projects, scope, scan history, findings
- **Scan tools container** — the Celery worker image extends the tools image; all Go tools (`subfinder`, `nmap`, etc.) are baked in alongside the Python worker. Tools are invoked via `asyncio.create_subprocess_exec` — no Docker-in-Docker or SDK calls needed.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | React (Vite), plain TypeScript |
| Database | PostgreSQL 16, SQLAlchemy 2 (async) |
| Background jobs | Celery 5, Redis 7 |
| Scheduling | Celery Beat |
| Auth | JWT tokens, bcrypt password hashing |
| WebSockets | FastAPI native WebSocket support |
| Containerization | Docker, Docker Compose |
| Testing (backend) | pytest, pytest-asyncio |
| Testing (frontend) | Vitest, React Testing Library |
| E2E testing | Playwright |
| CI | GitHub Actions |

---

## Data Model

### `orgs`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT | Organization name |
| created_at | TIMESTAMPTZ | |

Single org for self-hosted. Multiple orgs for SaaS multi-tenancy.

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| org_id | FK → orgs | |
| email | TEXT UNIQUE | |
| password_hash | TEXT | bcrypt |
| role | TEXT | `admin` / `viewer` |
| created_at | TIMESTAMPTZ | |

### `api_keys`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| org_id | FK → orgs | |
| service | TEXT | `whoxy` / `shodan` / etc. |
| key_value | TEXT | Stored encrypted |

### `projects`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| org_id | FK → orgs | |
| name | TEXT | |
| company_name | TEXT | Input for apex discovery |
| created_at | TIMESTAMPTZ | |

### `scope`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | FK → projects | |
| value | TEXT | Apex domain or IP range |
| source | TEXT | `manual` / `discovered` |
| approved | BOOLEAN | False until user approves discovered items |

### `scan_runs`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | FK → projects | |
| profile | TEXT | `passive` / `standard` / `active` / `full` |
| status | TEXT | `queued` / `running` / `complete` / `failed` |
| triggered_by | TEXT | `manual` / `scheduled` |
| error_message | TEXT | Set on failure |
| started_at | TIMESTAMPTZ | |
| finished_at | TIMESTAMPTZ | |

### `findings`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | FK → projects | |
| scan_run_id | FK → scan_runs | Run that first discovered this |
| type | TEXT | `subdomain` / `ip` / `live_url` / `open_port` / `http_header` / `asn` |
| value | TEXT | The discovered value |
| metadata | JSONB | Extra data (port number, header name, etc.) |
| first_seen_at | TIMESTAMPTZ | |
| last_seen_at | TIMESTAMPTZ | Updated on each scan |

**Unique constraint:** `(project_id, type, value)` — dedup at insert. New unique row triggers notification.

### `notification_configs`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | FK → projects | |
| type | TEXT | `discord` (others later) |
| config | JSONB | `{"webhook_url": "..."}` |

### `schedules`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | FK → projects | |
| cron_expression | TEXT | Standard cron syntax |
| profile | TEXT | Scan profile to run |
| enabled | BOOLEAN | |

---

## Scan Pipeline

### Phase 0 — Apex Domain Discovery

Runs before the main scan pipeline. Input: company name + optional seed domains.

| Source | Tool / API | Cost | Required |
|---|---|---|---|
| Reverse WHOIS | whoxy.com API | ~$2/500 queries | Optional — skipped if no key configured |
| ASN / BGP | ARIN + RIPE REST APIs | Free | Always runs |
| Certificate transparency | crt.sh API | Free | Always runs |
| Tenant domains | tenant-domains (Go tool) | Free | Always runs |

If a whoxy API key is not configured for the org, the reverse WHOIS discovery source is silently skipped and the remaining sources still run. The discovery review UI indicates which sources contributed results.

**Discovery workflow:**
1. User creates project with company name + optional seeds
2. Discovery tasks dispatched to Celery workers
3. Results surface in a **Review UI** — each discovered domain shown with its source
4. User explicitly approves or rejects each domain before it enters scope
5. Approved domains set `scope.approved = true` and are used in scan runs

The review gate is mandatory. Domains are never added to active scope without human approval.

### Scan Profiles

| Profile | Stages |
|---|---|
| Passive | Subdomain enumeration, DNS resolution |
| Standard | + Live host probing, HTTP header grab |
| Active | + Port scanning |
| Full | + Web app testing (future: nuclei, ffuf) |

### Stage Registry

Each stage is a self-contained plugin with:
- `name` and `description`
- `invasiveness_level`: `passive` / `active` / `invasive`
- `input_type` and `output_type` (e.g. takes `[domain]`, produces `[subdomain]`)
- `required_tools`: list of binaries that must be in `$PATH`

**Built-in stages (initial scope):**

| Stage | Tool | Input | Output |
|---|---|---|---|
| Subdomain enumeration | subfinder | apex domains | subdomains |
| DNS resolution | host | subdomains | IPs |
| Live host probe | httprobe | subdomains | live URLs |
| HTTP header grab | fff / httpx | live URLs | headers, tech |
| Port scan | nmap | IPs | open ports |
| ASN lookup | asnmap | IPs | ASN / netblocks |

**Future stages (not initial scope):** nuclei, ffuf, web screenshots, tech fingerprinting.

### Execution Flow

1. User clicks "Launch Scan", selects profile
2. FastAPI creates `ScanRun` record (status: `queued`) and enqueues Celery job
3. Worker picks up job, sets status → `running`
4. Each stage runs sequentially via `asyncio.create_subprocess_exec` inside the scan tools container
5. Output lines streamed back to API via WebSocket → displayed live in browser
6. Each line inserted as `Finding` (upsert — unique constraint handles dedup)
7. New findings trigger notification dispatch
8. On completion: status → `complete`. On failure: status → `failed`, error captured.

**Error handling:**
- Missing tool → stage skipped, error logged, pipeline continues
- Stage timeout → configurable per stage, logged on breach
- Worker crash → Celery auto-requeues
- Notification failure → logged, does not abort scan

---

## Auth

- JWT-based session tokens (httpOnly cookie)
- bcrypt password hashing
- Two roles: `admin` (full access) and `viewer` (read-only, cannot launch scans)
- Org-scoped: all data is filtered by `org_id` — SaaS multi-tenancy is additive, not a rewrite
- Initial self-hosted setup: single org, admin user created on first boot via CLI or setup wizard

---

## Frontend Pages

| Page | Purpose |
|---|---|
| Login | Email + password |
| Dashboard | Project list, last scan status per project |
| New Project | Company name, optional seed domains |
| Apex Discovery Review | Approve / reject discovered domains per source |
| Project Detail | Findings table (filterable by type, date), scan history |
| Launch Scan | Select scan profile, confirm scope |
| Live Scan Output | Streaming terminal-style output, progress by stage |
| Findings | Full filterable/searchable findings table |
| Methodology | VantagePoint OSINT reference notes (Markdown, rendered) |
| Settings — Project | Scope management, notification config, schedule |
| Settings — Org | API keys (whoxy, Shodan, etc.), user management |

---

## Methodology Page

The OSINT technique notes from the VantagePoint README (reverse WHOIS sources, ASN mapping, Shodan tips, BGP lookups, etc.) are preserved as a Markdown reference page rendered in the browser. This content is static and ships with the app. It is the canonical place to document investigation techniques.

---

## Directory Layout

```
vantagepoint/
├── docker-compose.yml
├── Dockerfile.app
├── Dockerfile.tools          # Go tools base image (extended by Dockerfile.worker)
├── Dockerfile.worker         # Celery worker image: tools base + Python deps
├── setup.sh                  # Kept — used in Dockerfile.tools
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── auth.py
│   │   ├── schemas.py
│   │   ├── deps.py
│   │   ├── routers/
│   │   │   ├── projects.py
│   │   │   ├── scans.py
│   │   │   ├── findings.py
│   │   │   ├── scope.py
│   │   │   └── settings.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   ├── pipeline.py
│   │   │   └── discovery.py
│   │   ├── stages/
│   │   │   ├── base.py       # Stage base class / registry
│   │   │   ├── subfinder.py
│   │   │   ├── dns.py
│   │   │   ├── httprobe.py
│   │   │   ├── fff.py
│   │   │   ├── nmap.py
│   │   │   └── asnmap.py
│   │   └── notifier.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_models.py
│   │   ├── test_pipeline.py
│   │   ├── test_stages.py
│   │   ├── test_discovery.py
│   │   └── test_routes.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   └── superpowers/
│       ├── specs/
│       └── plans/
└── README.md
```

---

## Testing Strategy

**Backend (pytest):**
- Unit tests: FastAPI routes (mock Celery), stage registry, dedup logic, notifier
- Integration tests: pipeline stages run against real tools container using `scanme.nmap.org` as a safe target
- DB tests: throwaway Postgres via Docker in CI

**Frontend (Vitest + React Testing Library):**
- Component tests for key flows: create project, launch scan, approve discovered domains, view findings

**E2E (Playwright):**
- Happy path: login → create project → launch scan → findings appear
- Runs on merge to `main` only

**CI (GitHub Actions):**
- On every PR: lint, unit tests, integration tests
- On merge to main: full suite including E2E

---

## Out of Scope (initial release)

- Nuclei / web app vulnerability scanning (architecture supports it as a future stage)
- VPN integration (Mullvad)
- Email notifications (Discord only initially)
- Mobile UI
- SSO / OAuth

---

## Migration from Prior Design

The existing `app/` directory (SQLite + APScheduler + HTMX) is superseded by this design. Existing `app/models.py`, `app/db.py`, `app/state.py` and related tests should be removed and replaced. The prior design spec (`2026-04-03-vantagepoint-rewrite-design.md`) and plan (`2026-04-04-vantagepoint-rewrite.md`) are retained for reference but no longer active.
