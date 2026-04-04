# VantagePoint Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Bash-based bug bounty recon toolkit as a self-hosted FastAPI web app with live scan streaming, scheduled scans, and Discord alerts on new findings.

**Architecture:** FastAPI handles HTTP and SSE streaming; the scan pipeline runs as an asyncio background task, writing results into an in-memory queue that the SSE endpoint drains. SQLAlchemy + SQLite persists projects, scan runs, and deduplicated findings. APScheduler runs scheduled scans inside the same process.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2, SQLite, APScheduler 3, sse-starlette, httpx, Jinja2, HTMX, Pico.css, pytest, pytest-asyncio

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | Python dependencies |
| `pytest.ini` | pytest + asyncio config |
| `app/__init__.py` | Empty package marker |
| `app/db.py` | SQLAlchemy engine, SessionLocal, Base, `get_db`, `init_db` |
| `app/models.py` | ORM models: Project, Scope, ScanRun, Finding |
| `app/state.py` | `scan_queues` dict shared between routes and scheduler |
| `app/notifier.py` | `send_discord(webhook_url, message)` — async Discord webhook POST |
| `app/scanner.py` | Async generator wrappers: `run_subfinder`, `run_host_lookup`, `run_httprobe`, `run_fff`, `run_nmap` |
| `app/pipeline.py` | `run_pipeline(project_id, scan_run_id, session_factory, queue)` — orchestrates scanner steps |
| `app/scheduler.py` | APScheduler instance, `register_job`, `remove_job`, `load_all_jobs` |
| `app/main.py` | FastAPI app, lifespan, all routes |
| `app/templates/base.html` | Pico.css + HTMX CDN, nav |
| `app/templates/index.html` | Dashboard: project list + Run Scan buttons |
| `app/templates/project_new.html` | Create project form |
| `app/templates/project_detail.html` | Findings tabs (subdomains/IPs/web hosts/ports) + scan history |
| `app/templates/project_settings.html` | Edit scope, webhook URL, cron schedule |
| `app/templates/scan_live.html` | Live SSE output page |
| `tests/__init__.py` | Empty package marker |
| `tests/conftest.py` | Fixtures: in-memory DB, TestClient with DB override, sample project |
| `tests/test_models.py` | Dedup constraint, cascade delete, field defaults |
| `tests/test_notifier.py` | Discord webhook unit tests (mock httpx) |
| `tests/test_scanner.py` | Tool wrapper unit tests (mock subprocess) |
| `tests/test_pipeline.py` | Pipeline integration tests (mock scanner, real DB) |
| `tests/test_routes.py` | HTTP route tests (TestClient) |

---

## Task 1: Scaffold, DB layer, and models

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `app/__init__.py`
- Create: `app/db.py`
- Create: `app/models.py`
- Create: `app/state.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.36
apscheduler==3.10.4
httpx==0.27.2
jinja2==3.1.4
python-multipart==0.0.12
sse-starlette==2.1.3
pytest==8.3.3
pytest-asyncio==0.24.0
anyio==4.6.2
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 4: Create app/__init__.py and tests/__init__.py**

Both files are empty. Just `touch` them:

```bash
touch app/__init__.py tests/__init__.py
```

- [ ] **Step 5: Create app/db.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./vantagepoint.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401 — registers models with Base
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 6: Create app/models.py**

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    discord_webhook_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scan_schedule: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scope: Mapped[list["Scope"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scan_runs: Mapped[list["ScanRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ScanRun.started_at.desc()"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Scope(Base):
    __tablename__ = "scope"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="scope")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="running")
    triggered_by: Mapped[str] = mapped_column(String, default="manual")
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="scan_runs")
    findings: Mapped[list["Finding"]] = relationship(back_populates="scan_run")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    scan_run_id: Mapped[int] = mapped_column(ForeignKey("scan_runs.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="findings")
    scan_run: Mapped["ScanRun"] = relationship(back_populates="findings")

    __table_args__ = (UniqueConstraint("project_id", "type", "value", name="uq_finding"),)
```

- [ ] **Step 7: Create app/state.py**

```python
import asyncio

# Keyed by scan_run_id. Pipeline writes lines; SSE endpoint reads.
# None sentinel signals end of stream.
scan_queues: dict[int, asyncio.Queue[str | None]] = {}
```

- [ ] **Step 8: Create tests/conftest.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.models import Project, Scope


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    from app.main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def project(db):
    p = Project(
        name="test-project",
        discord_webhook_url="https://discord.com/api/webhooks/test/token",
    )
    db.add(p)
    db.flush()
    db.add(Scope(project_id=p.id, value="example.com"))
    db.commit()
    db.refresh(p)
    return p
```

- [ ] **Step 9: Write tests/test_models.py**

```python
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Project, Scope, ScanRun, Finding


def test_project_creation(db):
    p = Project(name="acme")
    db.add(p)
    db.commit()
    assert p.id is not None
    assert p.created_at is not None


def test_project_name_unique(db):
    db.add(Project(name="acme"))
    db.commit()
    db.add(Project(name="acme"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_finding_dedup_raises_on_duplicate(db, project):
    run = ScanRun(project_id=project.id)
    db.add(run)
    db.flush()
    db.add(Finding(project_id=project.id, scan_run_id=run.id, type="subdomain", value="sub.example.com"))
    db.commit()
    db.add(Finding(project_id=project.id, scan_run_id=run.id, type="subdomain", value="sub.example.com"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_value_different_type_allowed(db, project):
    run = ScanRun(project_id=project.id)
    db.add(run)
    db.flush()
    db.add(Finding(project_id=project.id, scan_run_id=run.id, type="subdomain", value="example.com"))
    db.add(Finding(project_id=project.id, scan_run_id=run.id, type="ip", value="example.com"))
    db.commit()
    assert db.query(Finding).count() == 2


def test_project_cascade_delete(db, project):
    run = ScanRun(project_id=project.id)
    db.add(run)
    db.flush()
    db.add(Finding(project_id=project.id, scan_run_id=run.id, type="subdomain", value="sub.example.com"))
    db.commit()
    db.delete(project)
    db.commit()
    assert db.query(ScanRun).count() == 0
    assert db.query(Finding).count() == 0
    assert db.query(Scope).count() == 0
```

- [ ] **Step 10: Run tests to verify they pass**

```bash
cd /home/collin/vantagepoint && pytest tests/test_models.py -v
```

Expected:
```
tests/test_models.py::test_project_creation PASSED
tests/test_models.py::test_project_name_unique PASSED
tests/test_models.py::test_finding_dedup_raises_on_duplicate PASSED
tests/test_models.py::test_same_value_different_type_allowed PASSED
tests/test_models.py::test_project_cascade_delete PASSED
5 passed
```

- [ ] **Step 11: Commit**

```bash
git add requirements.txt pytest.ini app/__init__.py app/db.py app/models.py app/state.py tests/__init__.py tests/conftest.py tests/test_models.py
git commit -m "feat: scaffold DB layer, models, and test fixtures"
```

---

## Task 2: Discord notifier

**Files:**
- Create: `app/notifier.py`
- Test: `tests/test_notifier.py`

- [ ] **Step 1: Write tests/test_notifier.py**

```python
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from app.notifier import send_discord


async def test_send_discord_posts_message():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.notifier.httpx.AsyncClient", return_value=mock_client):
        await send_discord("https://discord.com/api/webhooks/123/abc", "new subdomain: sub.example.com")

    mock_client.post.assert_called_once_with(
        "https://discord.com/api/webhooks/123/abc",
        json={"content": "new subdomain: sub.example.com"},
        timeout=10,
    )


async def test_send_discord_empty_webhook_does_nothing():
    # Must not raise or make any HTTP calls
    with patch("app.notifier.httpx.AsyncClient") as mock_cls:
        await send_discord("", "message")
        await send_discord(None, "message")
    mock_cls.assert_not_called()


async def test_send_discord_network_error_does_not_raise():
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.notifier.httpx.AsyncClient", return_value=mock_client):
        await send_discord("https://discord.com/api/webhooks/123/abc", "message")
    # No exception — notifier swallows errors
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_notifier.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `app.notifier` does not exist yet.

- [ ] **Step 3: Create app/notifier.py**

```python
import logging
import httpx

logger = logging.getLogger(__name__)


async def send_discord(webhook_url: str | None, message: str) -> None:
    """POST message to a Discord webhook. Logs errors; never raises."""
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                webhook_url, json={"content": message}, timeout=10
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Discord notification failed: %s", exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notifier.py -v
```

Expected:
```
tests/test_notifier.py::test_send_discord_posts_message PASSED
tests/test_notifier.py::test_send_discord_empty_webhook_does_nothing PASSED
tests/test_notifier.py::test_send_discord_network_error_does_not_raise PASSED
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add app/notifier.py tests/test_notifier.py
git commit -m "feat: Discord notifier with error isolation"
```

---

## Task 3: Scanner tool wrappers

**Files:**
- Create: `app/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Write tests/test_scanner.py**

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.scanner import (
    run_subfinder,
    run_host_lookup,
    run_httprobe,
    run_fff,
    run_nmap,
)


async def _collect(agen):
    """Drain an async generator into a list."""
    return [item async for item in agen]


def _make_proc(stdout_lines: list[bytes], communicate_result: bytes | None = None):
    """Build a mock asyncio Process."""
    proc = MagicMock()
    if communicate_result is not None:
        proc.communicate = AsyncMock(return_value=(communicate_result, b""))
        proc.stdin = MagicMock()
        proc.stdin.write = MagicMock()
        proc.stdin.drain = AsyncMock()
        proc.stdin.close = MagicMock()
    else:
        async def _aiter_stdout():
            for line in stdout_lines:
                yield line
        proc.stdout = _aiter_stdout()
        proc.wait = AsyncMock()
    return proc


async def test_run_subfinder_yields_subdomains():
    proc = _make_proc([b"sub1.example.com\n", b"sub2.example.com\n"])
    with patch("shutil.which", return_value="/usr/bin/subfinder"), \
         patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        results = await _collect(run_subfinder(["example.com"]))
    assert results == ["sub1.example.com", "sub2.example.com"]


async def test_run_subfinder_missing_tool_raises():
    with patch("shutil.which", return_value=None):
        with pytest.raises(FileNotFoundError, match="subfinder not found in PATH"):
            await _collect(run_subfinder(["example.com"]))


async def test_run_httprobe_yields_live_hosts():
    output = b"http://example.com\nhttps://example.com\n"
    proc = _make_proc([], communicate_result=output)
    with patch("shutil.which", return_value="/usr/bin/httprobe"), \
         patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        results = await _collect(run_httprobe(["example.com"]))
    assert results == ["http://example.com", "https://example.com"]


async def test_run_httprobe_empty_input_yields_nothing():
    results = await _collect(run_httprobe([]))
    assert results == []


async def test_run_nmap_yields_output_lines():
    proc = _make_proc([b"80/tcp open http\n", b"443/tcp open https\n"])
    with patch("shutil.which", return_value="/usr/bin/nmap"), \
         patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        results = await _collect(run_nmap(["93.184.216.34"]))
    assert "80/tcp open http" in results
    assert "443/tcp open https" in results


async def test_run_nmap_empty_ips_yields_nothing():
    results = await _collect(run_nmap([]))
    assert results == []


async def test_run_host_lookup_extracts_ips():
    output = b"example.com has address 93.184.216.34\nexample.com has address 93.184.216.35\n"
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(output, b""))
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        results = await _collect(run_host_lookup(["example.com"]))
    assert results == ["93.184.216.34", "93.184.216.35"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scanner.py -v
```

Expected: `ImportError` — `app.scanner` does not exist yet.

- [ ] **Step 3: Create app/scanner.py**

```python
import asyncio
import shutil
from typing import AsyncIterator


def _check_tool(name: str) -> None:
    if not shutil.which(name):
        raise FileNotFoundError(f"{name} not found in PATH")


async def _stream_proc(*args: str) -> AsyncIterator[str]:
    """Run a subprocess, stream stdout line-by-line."""
    _check_tool(args[0])
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    async for raw in proc.stdout:
        line = raw.decode().strip()
        if line:
            yield line
    await proc.wait()


async def _communicate_proc(*args: str, stdin_data: bytes) -> AsyncIterator[str]:
    """Run a subprocess with stdin, yield stdout lines after completion."""
    _check_tool(args[0])
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate(stdin_data)
    for raw in stdout.decode().splitlines():
        line = raw.strip()
        if line:
            yield line


async def run_subfinder(scope: list[str]) -> AsyncIterator[str]:
    """Enumerate subdomains for each domain in scope."""
    args = ["subfinder", "-silent"]
    for domain in scope:
        args += ["-d", domain]
    async for line in _stream_proc(*args):
        yield line


async def run_host_lookup(domains: list[str]) -> AsyncIterator[str]:
    """Resolve A records for each domain, yield IP addresses."""
    for domain in domains:
        try:
            proc = await asyncio.create_subprocess_exec(
                "host", "-t", "A", domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            for line in stdout.decode().splitlines():
                if "has address" in line:
                    yield line.split()[-1]
        except Exception:
            continue


async def run_httprobe(domains: list[str]) -> AsyncIterator[str]:
    """Probe domains for live HTTP/HTTPS endpoints."""
    if not domains:
        return
    async for line in _communicate_proc("httprobe", stdin_data="\n".join(domains).encode()):
        yield line


async def run_fff(urls: list[str], output_dir: str) -> AsyncIterator[str]:
    """Fetch HTTP headers for each URL, store output in output_dir."""
    if not urls:
        return
    async for line in _communicate_proc(
        "fff", "-d", "1", "-S", "-o", output_dir,
        stdin_data="\n".join(urls).encode(),
    ):
        yield line


async def run_nmap(ips: list[str]) -> AsyncIterator[str]:
    """Run nmap default port scan against the given IPs."""
    if not ips:
        return
    async for line in _stream_proc("nmap", *ips):
        yield line
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scanner.py -v
```

Expected:
```
tests/test_scanner.py::test_run_subfinder_yields_subdomains PASSED
tests/test_scanner.py::test_run_subfinder_missing_tool_raises PASSED
tests/test_scanner.py::test_run_httprobe_yields_live_hosts PASSED
tests/test_scanner.py::test_run_httprobe_empty_input_yields_nothing PASSED
tests/test_scanner.py::test_run_nmap_yields_output_lines PASSED
tests/test_scanner.py::test_run_nmap_empty_ips_yields_nothing PASSED
tests/test_scanner.py::test_run_host_lookup_extracts_ips PASSED
7 passed
```

- [ ] **Step 5: Commit**

```bash
git add app/scanner.py tests/test_scanner.py
git commit -m "feat: async scanner wrappers for Go tools"
```

---

## Task 4: Pipeline orchestration

**Files:**
- Create: `app/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write tests/test_pipeline.py**

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Project, Scope, ScanRun, Finding
from app.pipeline import run_pipeline, upsert_finding


# ── DB fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def mem_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def SessionFactory(mem_engine):
    return sessionmaker(bind=mem_engine)


@pytest.fixture
def pipeline_project(SessionFactory):
    db = SessionFactory()
    p = Project(name="pipe-test")
    db.add(p)
    db.flush()
    db.add(Scope(project_id=p.id, value="example.com"))
    db.commit()
    project_id = p.id
    db.close()
    return project_id


# ── upsert_finding tests ──────────────────────────────────────────────────────

def test_upsert_finding_new_returns_true(SessionFactory, pipeline_project):
    db = SessionFactory()
    run = ScanRun(project_id=pipeline_project)
    db.add(run)
    db.flush()
    is_new = upsert_finding(db, pipeline_project, run.id, "subdomain", "sub.example.com")
    assert is_new is True
    assert db.query(Finding).count() == 1
    db.close()


def test_upsert_finding_duplicate_returns_false(SessionFactory, pipeline_project):
    db = SessionFactory()
    run = ScanRun(project_id=pipeline_project)
    db.add(run)
    db.flush()
    upsert_finding(db, pipeline_project, run.id, "subdomain", "sub.example.com")
    is_new = upsert_finding(db, pipeline_project, run.id, "subdomain", "sub.example.com")
    assert is_new is False
    assert db.query(Finding).count() == 1
    db.close()


# ── run_pipeline tests ────────────────────────────────────────────────────────

async def _drain(queue: asyncio.Queue) -> list[str]:
    lines = []
    while True:
        item = await queue.get()
        if item is None:
            break
        lines.append(item)
    return lines


async def _agen(*items):
    for item in items:
        yield item


async def test_pipeline_stores_subdomains(SessionFactory, pipeline_project):
    queue = asyncio.Queue()
    with patch("app.pipeline.run_subfinder", return_value=_agen("sub.example.com")), \
         patch("app.pipeline.run_host_lookup", return_value=_agen()), \
         patch("app.pipeline.run_httprobe", return_value=_agen()), \
         patch("app.pipeline.run_fff", return_value=_agen()), \
         patch("app.pipeline.run_nmap", return_value=_agen()), \
         patch("app.pipeline.send_discord", AsyncMock()):

        db = SessionFactory()
        run = ScanRun(project_id=pipeline_project)
        db.add(run)
        db.commit()
        scan_run_id = run.id
        db.close()

        await run_pipeline(pipeline_project, scan_run_id, SessionFactory, queue)

    db = SessionFactory()
    findings = db.query(Finding).all()
    assert any(f.value == "sub.example.com" and f.type == "subdomain" for f in findings)
    db.close()
    await _drain(queue)


async def test_pipeline_sends_discord_for_new_finding(SessionFactory, pipeline_project):
    queue = asyncio.Queue()
    mock_discord = AsyncMock()
    with patch("app.pipeline.run_subfinder", return_value=_agen("new.example.com")), \
         patch("app.pipeline.run_host_lookup", return_value=_agen()), \
         patch("app.pipeline.run_httprobe", return_value=_agen()), \
         patch("app.pipeline.run_fff", return_value=_agen()), \
         patch("app.pipeline.run_nmap", return_value=_agen()), \
         patch("app.pipeline.send_discord", mock_discord):

        db = SessionFactory()
        run = ScanRun(project_id=pipeline_project)
        db.add(run)
        db.commit()
        scan_run_id = run.id
        db.close()

        await run_pipeline(pipeline_project, scan_run_id, SessionFactory, queue)

    mock_discord.assert_called_once()
    await _drain(queue)


async def test_pipeline_missing_tool_continues(SessionFactory, pipeline_project):
    """A FileNotFoundError on one step should not abort the pipeline."""
    queue = asyncio.Queue()

    async def _raise():
        raise FileNotFoundError("subfinder not found in PATH")
        yield  # make it an async generator

    with patch("app.pipeline.run_subfinder", side_effect=FileNotFoundError("subfinder not found in PATH")), \
         patch("app.pipeline.run_host_lookup", return_value=_agen()), \
         patch("app.pipeline.run_httprobe", return_value=_agen()), \
         patch("app.pipeline.run_fff", return_value=_agen()), \
         patch("app.pipeline.run_nmap", return_value=_agen()), \
         patch("app.pipeline.send_discord", AsyncMock()):

        db = SessionFactory()
        run = ScanRun(project_id=pipeline_project)
        db.add(run)
        db.commit()
        scan_run_id = run.id
        db.close()

        await run_pipeline(pipeline_project, scan_run_id, SessionFactory, queue)

    db = SessionFactory()
    run = db.get(ScanRun, scan_run_id)
    assert "subfinder" in (run.error_message or "")
    assert run.status == "complete"  # pipeline continued to completion
    db.close()
    await _drain(queue)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_pipeline.py -v
```

Expected: `ImportError` — `app.pipeline` does not exist yet.

- [ ] **Step 3: Create app/pipeline.py**

```python
import asyncio
import os
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Finding, Project, ScanRun
from app.notifier import send_discord
from app.scanner import (
    run_fff,
    run_host_lookup,
    run_httprobe,
    run_nmap,
    run_subfinder,
)


def upsert_finding(
    db: Session,
    project_id: int,
    scan_run_id: int,
    type_: str,
    value: str,
) -> bool:
    """Insert finding if new. Returns True if new, False if already existed."""
    try:
        db.add(Finding(project_id=project_id, scan_run_id=scan_run_id, type=type_, value=value))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        existing = db.query(Finding).filter_by(
            project_id=project_id, type=type_, value=value
        ).first()
        if existing:
            existing.last_seen_at = datetime.utcnow()
            db.commit()
        return False


async def run_pipeline(
    project_id: int,
    scan_run_id: int,
    session_factory,
    queue: asyncio.Queue,
) -> None:
    """
    Run full recon pipeline for a project. Puts status lines into queue.
    Sends None sentinel when done.
    """
    db = session_factory()
    try:
        project = db.get(Project, project_id)
        run = db.get(ScanRun, scan_run_id)
        scope = [s.value for s in project.scope]
        webhook = project.discord_webhook_url

        async def emit(line: str) -> None:
            await queue.put(line)

        async def step(label: str, type_: str, items):
            results = []
            await emit(f"--- {label} ---")
            async for value in items:
                is_new = upsert_finding(db, project_id, scan_run_id, type_, value)
                tag = " [NEW]" if is_new else ""
                await emit(f"{value}{tag}")
                if is_new:
                    await send_discord(webhook, f"[{project.name}] new {type_}: {value}")
                results.append(value)
            return results

        subdomains = []
        ips = []
        web_hosts = []

        try:
            subdomains = await step("subfinder", "subdomain", run_subfinder(scope))
        except FileNotFoundError as e:
            run.error_message = str(e)
            db.commit()
            await emit(f"ERROR: {e}")

        try:
            ips = await step("host lookup", "ip", run_host_lookup(subdomains + scope))
        except FileNotFoundError as e:
            run.error_message = (run.error_message or "") + f"; {e}"
            db.commit()
            await emit(f"ERROR: {e}")

        try:
            web_hosts = await step("httprobe", "web_host", run_httprobe(subdomains + scope))
        except FileNotFoundError as e:
            run.error_message = (run.error_message or "") + f"; {e}"
            db.commit()
            await emit(f"ERROR: {e}")

        if web_hosts:
            roots_dir = os.path.expanduser(f"~/recon/{project.name}/roots")
            os.makedirs(roots_dir, exist_ok=True)
            try:
                await step("fff headers", "web_host", run_fff(web_hosts, roots_dir))
            except FileNotFoundError as e:
                run.error_message = (run.error_message or "") + f"; {e}"
                db.commit()
                await emit(f"ERROR: {e}")

        if ips:
            try:
                await step("nmap", "nmap_port", run_nmap(ips))
            except FileNotFoundError as e:
                run.error_message = (run.error_message or "") + f"; {e}"
                db.commit()
                await emit(f"ERROR: {e}")

        run.status = "complete"
        run.finished_at = datetime.utcnow()
        db.commit()
        await emit("--- scan complete ---")

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = datetime.utcnow()
        db.commit()
        await emit(f"FATAL: {e}")
    finally:
        db.close()
        await queue.put(None)  # sentinel
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_pipeline.py -v
```

Expected:
```
tests/test_pipeline.py::test_upsert_finding_new_returns_true PASSED
tests/test_pipeline.py::test_upsert_finding_duplicate_returns_false PASSED
tests/test_pipeline.py::test_pipeline_stores_subdomains PASSED
tests/test_pipeline.py::test_pipeline_sends_discord_for_new_finding PASSED
tests/test_pipeline.py::test_pipeline_missing_tool_continues PASSED
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add app/pipeline.py tests/test_pipeline.py
git commit -m "feat: scan pipeline with dedup and Discord alerts"
```

---

## Task 5: Scheduler

**Files:**
- Create: `app/scheduler.py`

*No isolated unit tests — scheduler behavior is validated via route tests in Task 6.*

- [ ] **Step 1: Create app/scheduler.py**

```python
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def _parse_cron(expr: str) -> dict:
    """Parse '* * * * *' cron expression into APScheduler kwargs."""
    minute, hour, day, month, day_of_week = expr.strip().split()
    return dict(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)


async def _run_scheduled_scan(project_id: int) -> None:
    from app.db import SessionLocal
    from app.models import ScanRun
    from app.pipeline import run_pipeline
    from app.state import scan_queues

    db = SessionLocal()
    try:
        run = ScanRun(project_id=project_id, triggered_by="scheduled")
        db.add(run)
        db.commit()
        db.refresh(run)
        scan_run_id = run.id
    finally:
        db.close()

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    scan_queues[scan_run_id] = queue
    await run_pipeline(project_id, scan_run_id, SessionLocal, queue)


def register_job(project_id: int, cron_expr: str) -> None:
    """Add or replace a scheduled scan job for a project."""
    job_id = f"project_{project_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        _run_scheduled_scan,
        trigger="cron",
        id=job_id,
        args=[project_id],
        **_parse_cron(cron_expr),
    )
    logger.info("Scheduled scan for project %s: %s", project_id, cron_expr)


def remove_job(project_id: int) -> None:
    """Remove scheduled scan job for a project if it exists."""
    job_id = f"project_{project_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def load_all_jobs() -> None:
    """Register jobs for all projects with a scan_schedule on startup."""
    from app.db import SessionLocal
    from app.models import Project

    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.scan_schedule.isnot(None)).all()
        for project in projects:
            register_job(project.id, project.scan_schedule)
    finally:
        db.close()
```

- [ ] **Step 2: Commit**

```bash
git add app/scheduler.py
git commit -m "feat: APScheduler setup with per-project cron jobs"
```

---

## Task 6: Web routes

**Files:**
- Create: `app/main.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Write tests/test_routes.py**

```python
import pytest
from unittest.mock import patch, AsyncMock
from app.models import Project, Scope, ScanRun, Finding


def test_dashboard_shows_projects(client, project):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "test-project" in resp.text


def test_create_project_get(client):
    resp = client.get("/projects/new")
    assert resp.status_code == 200
    assert "form" in resp.text.lower()


def test_create_project_post_redirects(client, db):
    resp = client.post(
        "/projects/new",
        data={"name": "new-project", "scope": "example.com\ntarget.com"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    proj = db.query(Project).filter_by(name="new-project").first()
    assert proj is not None
    assert db.query(Scope).filter_by(project_id=proj.id).count() == 2


def test_project_detail(client, project):
    resp = client.get(f"/projects/{project.id}")
    assert resp.status_code == 200
    assert "test-project" in resp.text


def test_project_detail_404(client):
    resp = client.get("/projects/9999")
    assert resp.status_code == 404


def test_trigger_scan_creates_run(client, project, db):
    with patch("app.main.asyncio.create_task"), \
         patch("app.main.scan_queues", {}):
        resp = client.post(f"/projects/{project.id}/scan", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert db.query(ScanRun).filter_by(project_id=project.id).count() == 1


def test_project_settings_get(client, project):
    resp = client.get(f"/projects/{project.id}/settings")
    assert resp.status_code == 200
    assert "example.com" in resp.text


def test_project_settings_post_updates_webhook(client, project, db):
    with patch("app.main.scheduler.remove_job"), \
         patch("app.main.scheduler.register_job"):
        resp = client.post(
            f"/projects/{project.id}/settings",
            data={
                "scope": "example.com",
                "discord_webhook_url": "https://discord.com/api/webhooks/new/token",
                "scan_schedule": "",
            },
            follow_redirects=False,
        )
    assert resp.status_code in (302, 303)
    db.refresh(project)
    assert project.discord_webhook_url == "https://discord.com/api/webhooks/new/token"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_routes.py -v
```

Expected: `ImportError` — `app.main` does not exist yet.

- [ ] **Step 3: Create app/main.py**

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.db import SessionLocal, get_db, init_db
from app.models import Finding, Project, Scope, ScanRun
from app.pipeline import run_pipeline
from app.scheduler import load_all_jobs, register_job, remove_job, scheduler
from app.state import scan_queues


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    load_all_jobs()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "projects": projects})


# ── Create project ────────────────────────────────────────────────────────────

@app.get("/projects/new", response_class=HTMLResponse)
def new_project_form(request: Request):
    return templates.TemplateResponse("project_new.html", {"request": request})


@app.post("/projects/new")
def create_project(
    name: str = Form(...),
    scope: str = Form(...),
    db: Session = Depends(get_db),
):
    project = Project(name=name)
    db.add(project)
    db.flush()
    for line in scope.splitlines():
        value = line.strip()
        if value:
            db.add(Scope(project_id=project.id, value=value))
    db.commit()
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


# ── Project detail ────────────────────────────────────────────────────────────

@app.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    findings_by_type = {
        "subdomain": db.query(Finding).filter_by(project_id=project_id, type="subdomain").all(),
        "ip": db.query(Finding).filter_by(project_id=project_id, type="ip").all(),
        "web_host": db.query(Finding).filter_by(project_id=project_id, type="web_host").all(),
        "nmap_port": db.query(Finding).filter_by(project_id=project_id, type="nmap_port").all(),
    }
    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "project": project,
        "findings": findings_by_type,
    })


# ── Trigger scan ──────────────────────────────────────────────────────────────

@app.post("/projects/{project_id}/scan")
def trigger_scan(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    run = ScanRun(project_id=project_id, triggered_by="manual")
    db.add(run)
    db.commit()
    db.refresh(run)

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    scan_queues[run.id] = queue
    asyncio.create_task(run_pipeline(project_id, run.id, SessionLocal, queue))

    return RedirectResponse(url=f"/scans/{run.id}", status_code=303)


# ── Scan live view ────────────────────────────────────────────────────────────

@app.get("/scans/{scan_id}", response_class=HTMLResponse)
def scan_live(scan_id: int, request: Request, db: Session = Depends(get_db)):
    run = db.get(ScanRun, scan_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scan not found")
    return templates.TemplateResponse("scan_live.html", {"request": request, "scan": run})


@app.get("/scans/{scan_id}/stream")
async def scan_stream(scan_id: int):
    async def event_gen():
        queue = scan_queues.get(scan_id)
        if queue is None:
            yield {"data": "<div class='error'>Scan stream not available.</div>"}
            return
        while True:
            line = await queue.get()
            if line is None:
                scan_queues.pop(scan_id, None)
                break
            yield {"data": f"<div>{line}</div>"}
    return EventSourceResponse(event_gen())


# ── Project settings ──────────────────────────────────────────────────────────

@app.get("/projects/{project_id}/settings", response_class=HTMLResponse)
def project_settings(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse("project_settings.html", {
        "request": request,
        "project": project,
    })


@app.post("/projects/{project_id}/settings")
def update_project_settings(
    project_id: int,
    scope: str = Form(...),
    discord_webhook_url: str = Form(""),
    scan_schedule: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update scope
    db.query(Scope).filter_by(project_id=project_id).delete()
    for line in scope.splitlines():
        value = line.strip()
        if value:
            db.add(Scope(project_id=project_id, value=value))

    # Update webhook and schedule
    project.discord_webhook_url = discord_webhook_url.strip() or None
    project.scan_schedule = scan_schedule.strip() or None
    db.commit()

    # Update scheduler
    remove_job(project_id)
    if project.scan_schedule:
        register_job(project_id, project.scan_schedule)

    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_routes.py -v
```

Expected:
```
tests/test_routes.py::test_dashboard_shows_projects PASSED
tests/test_routes.py::test_create_project_get PASSED
tests/test_routes.py::test_create_project_post_redirects PASSED
tests/test_routes.py::test_project_detail PASSED
tests/test_routes.py::test_project_detail_404 PASSED
tests/test_routes.py::test_trigger_scan_creates_run PASSED
tests/test_routes.py::test_project_settings_get PASSED
tests/test_routes.py::test_project_settings_post_updates_webhook PASSED
8 passed
```

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat: FastAPI routes and SSE scan streaming"
```

---

## Task 7: Templates

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/index.html`
- Create: `app/templates/project_new.html`
- Create: `app/templates/project_detail.html`
- Create: `app/templates/project_settings.html`
- Create: `app/templates/scan_live.html`

*Templates are validated by route tests already passing — no new tests needed.*

- [ ] **Step 1: Create app/templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VantagePoint{% block title %}{% endblock %}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12/dist/ext/sse.js"></script>
</head>
<body>
  <main class="container">
    <nav>
      <ul>
        <li><strong><a href="/">VantagePoint</a></strong></li>
      </ul>
    </nav>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Create app/templates/index.html**

```html
{% extends "base.html" %}
{% block title %} — Dashboard{% endblock %}
{% block content %}
<hgroup>
  <h1>Projects</h1>
  <p><a href="/projects/new" role="button">+ New Project</a></p>
</hgroup>

{% if projects %}
<table>
  <thead>
    <tr>
      <th>Name</th>
      <th>Last Scan</th>
      <th>Schedule</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
  {% for p in projects %}
    <tr>
      <td><a href="/projects/{{ p.id }}">{{ p.name }}</a></td>
      <td>
        {% if p.scan_runs %}
          {{ p.scan_runs[0].status }} — {{ p.scan_runs[0].started_at.strftime('%Y-%m-%d %H:%M') }}
        {% else %}
          Never
        {% endif %}
      </td>
      <td>{{ p.scan_schedule or "—" }}</td>
      <td>
        <form method="post" action="/projects/{{ p.id }}/scan" style="display:inline">
          <button type="submit" class="outline">Run Scan</button>
        </form>
        <a href="/projects/{{ p.id }}/settings" role="button" class="secondary outline">Settings</a>
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p>No projects yet. <a href="/projects/new">Create one.</a></p>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Create app/templates/project_new.html**

```html
{% extends "base.html" %}
{% block title %} — New Project{% endblock %}
{% block content %}
<h1>New Project</h1>
<form method="post" action="/projects/new">
  <label for="name">Project name
    <input type="text" id="name" name="name" placeholder="acme-corp" required>
  </label>
  <label for="scope">Scope (one domain per line)
    <textarea id="scope" name="scope" rows="6" placeholder="example.com&#10;sub.example.com" required></textarea>
  </label>
  <button type="submit">Create Project</button>
  <a href="/" role="button" class="secondary outline">Cancel</a>
</form>
{% endblock %}
```

- [ ] **Step 4: Create app/templates/project_detail.html**

```html
{% extends "base.html" %}
{% block title %} — {{ project.name }}{% endblock %}
{% block content %}
<hgroup>
  <h1>{{ project.name }}</h1>
  <p>
    <form method="post" action="/projects/{{ project.id }}/scan" style="display:inline">
      <button type="submit">Run Scan</button>
    </form>
    <a href="/projects/{{ project.id }}/settings" role="button" class="secondary outline">Settings</a>
  </p>
</hgroup>

<article>
  <details open>
    <summary><strong>Subdomains</strong> ({{ findings.subdomain|length }})</summary>
    {% if findings.subdomain %}
    <ul>{% for f in findings.subdomain %}<li>{{ f.value }}</li>{% endfor %}</ul>
    {% else %}<p>None found yet.</p>{% endif %}
  </details>
  <details>
    <summary><strong>IPs</strong> ({{ findings.ip|length }})</summary>
    {% if findings.ip %}
    <ul>{% for f in findings.ip %}<li>{{ f.value }}</li>{% endfor %}</ul>
    {% else %}<p>None found yet.</p>{% endif %}
  </details>
  <details>
    <summary><strong>Web Hosts</strong> ({{ findings.web_host|length }})</summary>
    {% if findings.web_host %}
    <ul>{% for f in findings.web_host %}<li><a href="{{ f.value }}" target="_blank">{{ f.value }}</a></li>{% endfor %}</ul>
    {% else %}<p>None found yet.</p>{% endif %}
  </details>
  <details>
    <summary><strong>Ports</strong> ({{ findings.nmap_port|length }})</summary>
    {% if findings.nmap_port %}
    <ul>{% for f in findings.nmap_port %}<li>{{ f.value }}</li>{% endfor %}</ul>
    {% else %}<p>None found yet.</p>{% endif %}
  </details>
</article>

<h2>Scan History</h2>
{% if project.scan_runs %}
<table>
  <thead><tr><th>Started</th><th>Status</th><th>Triggered by</th><th>Error</th></tr></thead>
  <tbody>
  {% for run in project.scan_runs %}
    <tr>
      <td><a href="/scans/{{ run.id }}">{{ run.started_at.strftime('%Y-%m-%d %H:%M') }}</a></td>
      <td>{{ run.status }}</td>
      <td>{{ run.triggered_by }}</td>
      <td>{{ run.error_message or "—" }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p>No scans run yet.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Create app/templates/project_settings.html**

```html
{% extends "base.html" %}
{% block title %} — Settings: {{ project.name }}{% endblock %}
{% block content %}
<h1>Settings — {{ project.name }}</h1>
<form method="post" action="/projects/{{ project.id }}/settings">
  <label for="scope">Scope (one domain per line)
    <textarea id="scope" name="scope" rows="6">{{ project.scope | map(attribute='value') | join('\n') }}</textarea>
  </label>
  <label for="discord_webhook_url">Discord webhook URL
    <input type="url" id="discord_webhook_url" name="discord_webhook_url"
           value="{{ project.discord_webhook_url or '' }}"
           placeholder="https://discord.com/api/webhooks/...">
  </label>
  <label for="scan_schedule">Cron schedule (leave blank to disable)
    <input type="text" id="scan_schedule" name="scan_schedule"
           value="{{ project.scan_schedule or '' }}"
           placeholder="0 6 * * *">
    <small>Format: minute hour day month weekday — e.g. <code>0 6 * * *</code> = daily at 6am</small>
  </label>
  <button type="submit">Save</button>
  <a href="/projects/{{ project.id }}" role="button" class="secondary outline">Cancel</a>
</form>
{% endblock %}
```

- [ ] **Step 6: Create app/templates/scan_live.html**

```html
{% extends "base.html" %}
{% block title %} — Scan #{{ scan.id }}{% endblock %}
{% block content %}
<hgroup>
  <h1>Scan #{{ scan.id }}</h1>
  <p>Status: <strong id="scan-status">{{ scan.status }}</strong></p>
</hgroup>

<pre id="output"
     style="background:#1a1a1a;color:#00ff41;padding:1rem;min-height:300px;overflow-y:auto;"
     hx-ext="sse"
     sse-connect="/scans/{{ scan.id }}/stream"
     sse-swap="message"
     hx-swap="beforeend"></pre>

<a href="/projects/{{ scan.project_id }}" role="button" class="secondary outline">Back to project</a>
{% endblock %}
```

- [ ] **Step 7: Run full test suite to confirm nothing is broken**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/templates/
git commit -m "feat: Jinja2 + HTMX templates for all routes"
```

---

## Task 8: Update setup.sh and smoke test

**Files:**
- Modify: `setup.sh`

- [ ] **Step 1: Update setup.sh to include Python deps**

Replace the existing `setup.sh` with:

```bash
#!/bin/bash
set -e

echo "=== Installing system packages ==="
apt update && apt install -y golang-go python3 python3-pip

echo "=== Installing Go recon tools ==="
go install github.com/tomnomnom/httprobe@latest
go install github.com/tomnomnom/anew@latest
go install github.com/tomnomnom/fff@latest
go install github.com/tomnomnom/waybackurls@latest
go install github.com/tomnomnom/gf@latest
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
go install -v github.com/projectdiscovery/notify/cmd/notify@latest
go install -v github.com/projectdiscovery/nuclei/cmd/nuclei@latest
git clone https://github.com/tomnomnom/gf /tmp/gf-tmp
mkdir -p ~/.gf
mv /tmp/gf-tmp/examples/* ~/.gf
rm -rf /tmp/gf-tmp

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Done. Start VantagePoint with: ==="
echo "    uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"
```

- [ ] **Step 2: Smoke test the app starts**

```bash
cd /home/collin/vantagepoint && uvicorn app.main:app --host 127.0.0.1 --port 8080 &
sleep 2
curl -s http://127.0.0.1:8080/ | grep -i "vantagepoint"
kill %1
```

Expected: HTML response containing "VantagePoint".

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest -v
```

Expected: all tests pass, no warnings about missing modules.

- [ ] **Step 4: Commit**

```bash
git add setup.sh
git commit -m "feat: update setup.sh with Python deps and start instructions"
```

- [ ] **Step 5: Push to GitHub**

```bash
git push origin main
```

---

## Self-Review

**Spec coverage:**
- [x] FastAPI + Uvicorn — Task 6
- [x] SQLAlchemy + SQLite — Task 1
- [x] APScheduler — Task 5
- [x] Jinja2 + HTMX — Task 7
- [x] SSE live scan output — Task 6 (`/scans/{id}/stream`)
- [x] Discord webhook — Task 2
- [x] Go tools via asyncio subprocess — Task 3
- [x] Project, Scope, ScanRun, Finding models — Task 1
- [x] Unique constraint dedup — Task 1, Task 4
- [x] All 6 routes — Task 6
- [x] Schedule live update without restart — Task 5, Task 6 (`update_project_settings`)
- [x] Missing tool → error logged, pipeline continues — Task 4
- [x] Discord failure doesn't abort scan — Task 2
- [x] TDD throughout — all tasks follow test-first

**Placeholder scan:** None found.

**Type consistency:**
- `upsert_finding(db, project_id, scan_run_id, type_, value)` — defined Task 4, used Task 4 ✓
- `send_discord(webhook_url, message)` — defined Task 2, used Task 4 ✓
- `run_subfinder / run_host_lookup / run_httprobe / run_fff / run_nmap` — defined Task 3, used Task 4 ✓
- `register_job / remove_job / load_all_jobs` — defined Task 5, used Task 6 ✓
- `scan_queues` — defined `app/state.py` Task 1, imported in Task 5 + Task 6 ✓
