# VantagePoint Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deployable foundation of VantagePoint — Docker Compose orchestration, FastAPI backend with Postgres, JWT auth, project/scope CRUD, and a React frontend with login and project management.

**Architecture:** FastAPI (async) serves a REST API at `/api/*` backed by Postgres via SQLAlchemy 2 async. React (Vite + TypeScript) runs as a separate service, talks to the API via Axios, and stores JWT in an httpOnly cookie. Docker Compose runs five services: `db`, `redis`, `backend`, `worker` (stub for now), `frontend`.

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async + asyncpg, passlib[bcrypt], python-jose[cryptography], Alembic, pytest, pytest-asyncio, httpx; React 18, Vite 5, TypeScript, React Router 6, TanStack Query 5, Axios, Tailwind CSS 3, Vitest, React Testing Library

---

## File Map

### Deleted (old design)
- `app/` — entire directory (SQLite/HTMX design, superseded)
- `tests/` — entire directory (superseded)
- `pytest.ini` — superseded
- `requirements.txt` — superseded

### Created

| File | Responsibility |
|---|---|
| `docker-compose.yml` | Orchestrates all 5 services |
| `Dockerfile.app` | FastAPI backend image |
| `Dockerfile.worker` | Stub worker image (extended in Plan 2) |
| `.env.example` | Environment variable template |
| `backend/requirements.txt` | Python dependencies |
| `backend/alembic.ini` | Alembic config |
| `backend/alembic/env.py` | Alembic async env |
| `backend/alembic/versions/` | Migration files |
| `backend/app/__init__.py` | Package marker |
| `backend/app/main.py` | FastAPI app, router registration, CORS, lifespan |
| `backend/app/db.py` | Async engine, SessionLocal, Base, `get_db`, `init_db` |
| `backend/app/models.py` | ORM models: Org, User, ApiKey, Project, Scope, ScanRun, Finding, NotificationConfig, Schedule |
| `backend/app/schemas.py` | Pydantic v2 schemas for all API request/response types |
| `backend/app/auth.py` | JWT creation/validation, bcrypt hashing, cookie helpers |
| `backend/app/deps.py` | FastAPI deps: `get_current_user`, `require_admin`, `get_db` |
| `backend/app/routers/__init__.py` | Package marker |
| `backend/app/routers/auth.py` | POST /api/auth/setup, /login, /logout; GET /api/auth/me, /api/auth/setup-needed |
| `backend/app/routers/projects.py` | GET/POST /api/projects, GET/DELETE /api/projects/{id} |
| `backend/app/routers/scope.py` | GET/POST /api/projects/{id}/scope, PATCH/DELETE /api/projects/{id}/scope/{sid} |
| `backend/tests/__init__.py` | Package marker |
| `backend/tests/conftest.py` | Async DB fixtures, TestClient, sample org+user |
| `backend/tests/test_models.py` | ORM constraints, cascade delete, defaults |
| `backend/tests/test_auth.py` | Login, setup, me, logout routes |
| `backend/tests/test_projects.py` | Project + scope CRUD routes |
| `frontend/package.json` | npm dependencies |
| `frontend/vite.config.ts` | Vite config with API proxy |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/tailwind.config.js` | Tailwind config |
| `frontend/postcss.config.js` | PostCSS for Tailwind |
| `frontend/index.html` | Vite entry HTML |
| `frontend/src/main.tsx` | React root, QueryClientProvider, RouterProvider |
| `frontend/src/App.tsx` | Route definitions |
| `frontend/src/api/client.ts` | Axios instance with base URL + credentials |
| `frontend/src/api/auth.ts` | login(), logout(), me(), setupNeeded(), setup() |
| `frontend/src/api/projects.ts` | listProjects(), createProject(), getProject(), deleteProject() |
| `frontend/src/api/scope.ts` | listScope(), addScope(), updateScope(), deleteScope() |
| `frontend/src/hooks/useAuth.ts` | useAuth() — current user + logout |
| `frontend/src/pages/SetupPage.tsx` | First-run setup form |
| `frontend/src/pages/LoginPage.tsx` | Login form |
| `frontend/src/pages/DashboardPage.tsx` | Project list |
| `frontend/src/pages/NewProjectPage.tsx` | Create project form |
| `frontend/src/pages/ProjectDetailPage.tsx` | Project stub (scope list, empty findings) |
| `frontend/src/components/Layout.tsx` | Nav bar + page wrapper |
| `frontend/src/components/ProtectedRoute.tsx` | Redirects to /login if unauthenticated |
| `frontend/src/test/setup.ts` | Vitest global setup |
| `frontend/src/pages/__tests__/LoginPage.test.tsx` | Login form tests |
| `frontend/src/pages/__tests__/DashboardPage.test.tsx` | Project list tests |

---

## Task 1: Delete old code, scaffold directory structure

**Files:**
- Delete: `app/`, `tests/`, `pytest.ini`, `requirements.txt`
- Create: `backend/`, `frontend/`, `.env.example`

- [ ] **Step 1: Remove superseded files**

```bash
cd ~/vantagepoint
rm -rf app tests pytest.ini requirements.txt
mkdir -p backend/app/routers backend/tests frontend/src
```

Expected: `ls` shows `backend/ docs/ frontend/ README.md setup.sh` (plus `.git/`)

- [ ] **Step 2: Create `.env.example`**

```
# Copy to .env and fill in values
POSTGRES_USER=vantagepoint
POSTGRES_PASSWORD=changeme
POSTGRES_DB=vantagepoint
DATABASE_URL=postgresql+asyncpg://vantagepoint:changeme@db:5432/vantagepoint
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-this-to-a-random-64-char-string
ACCESS_TOKEN_EXPIRE_HOURS=24
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=changeme
```

- [ ] **Step 3: Create `.env` from example**

```bash
cp .env.example .env
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old HTMX design, scaffold backend/ and frontend/"
```

---

## Task 2: Backend — DB layer, models, migrations

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.115.5
uvicorn[standard]==0.32.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-multipart==0.0.12
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
anyio==4.6.2
```

- [ ] **Step 2: Install dependencies**

```bash
cd ~/vantagepoint/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: packages install without error.

- [ ] **Step 3: Create `backend/app/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `backend/app/db.py`**

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 5: Create `backend/app/models.py`**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="org", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="org", cascade="all, delete-orphan")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_utcnow)

    org: Mapped["Org"] = relationship(back_populates="users")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    service: Mapped[str] = mapped_column(String, nullable=False)
    key_value: Mapped[str] = mapped_column(Text, nullable=False)

    org: Mapped["Org"] = relationship(back_populates="api_keys")

    __table_args__ = (UniqueConstraint("org_id", "service", name="uq_api_key_service"),)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_utcnow)

    org: Mapped["Org"] = relationship(back_populates="projects")
    scope: Mapped[list["Scope"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    scan_runs: Mapped[list["ScanRun"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    notification_configs: Mapped[list["NotificationConfig"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Scope(Base):
    __tablename__ = "scope"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project: Mapped["Project"] = relationship(back_populates="scope")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    profile: Mapped[str] = mapped_column(String, nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    triggered_by: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="scan_runs")
    findings: Mapped[list["Finding"]] = relationship(back_populates="scan_run")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    scan_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scan_runs.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="findings")
    scan_run: Mapped["ScanRun"] = relationship(back_populates="findings")

    __table_args__ = (UniqueConstraint("project_id", "type", "value", name="uq_finding"),)


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False, default="discord")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="notification_configs")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String, nullable=False)
    profile: Mapped[str] = mapped_column(String, nullable=False, default="standard")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project: Mapped["Project"] = relationship(back_populates="schedules")
```

- [ ] **Step 6: Create `backend/tests/__init__.py`**

```python
```
(empty)

- [ ] **Step 7: Create `backend/tests/conftest.py`**

```python
import asyncio
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.db import Base, get_db
from app.models import Org, User
from app.auth import hash_password
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_org(db):
    org = Org(name="Test Org")
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@pytest_asyncio.fixture
async def sample_admin(db, sample_org):
    user = User(
        org_id=sample_org.id,
        email="admin@test.com",
        password_hash=hash_password("password123"),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

- [ ] **Step 8: Add `aiosqlite` to requirements.txt** (needed for in-memory test DB)

Append to `backend/requirements.txt`:
```
aiosqlite==0.20.0
```

Then reinstall:
```bash
pip install -r requirements.txt
```

- [ ] **Step 9: Write the failing test**

Create `backend/tests/test_models.py`:

```python
import pytest
import pytest_asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Org, User, Project, Scope, Finding, ScanRun
from app.auth import hash_password


@pytest.mark.asyncio
async def test_org_defaults(db):
    org = Org(name="Acme")
    db.add(org)
    await db.commit()
    await db.refresh(org)

    assert org.id is not None
    assert org.created_at is not None


@pytest.mark.asyncio
async def test_user_belongs_to_org(db, sample_org):
    user = User(
        org_id=sample_org.id,
        email="test@example.com",
        password_hash=hash_password("pass"),
        role="viewer",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    assert user.org_id == sample_org.id
    assert user.role == "viewer"


@pytest.mark.asyncio
async def test_user_email_unique(db, sample_org):
    u1 = User(org_id=sample_org.id, email="dup@example.com", password_hash="x", role="viewer")
    u2 = User(org_id=sample_org.id, email="dup@example.com", password_hash="y", role="viewer")
    db.add(u1)
    db.add(u2)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_finding_dedup_constraint(db, sample_org):
    project = Project(org_id=sample_org.id, name="P", company_name="Co")
    db.add(project)
    await db.flush()

    scan = ScanRun(project_id=project.id)
    db.add(scan)
    await db.flush()

    f1 = Finding(project_id=project.id, scan_run_id=scan.id, type="subdomain", value="a.example.com")
    f2 = Finding(project_id=project.id, scan_run_id=scan.id, type="subdomain", value="a.example.com")
    db.add(f1)
    db.add(f2)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_project_cascade_delete(db, sample_org):
    project = Project(org_id=sample_org.id, name="CascadeTest", company_name="Co")
    db.add(project)
    await db.flush()

    scope = Scope(project_id=project.id, value="example.com")
    db.add(scope)
    await db.commit()

    await db.delete(project)
    await db.commit()

    result = await db.execute(select(Scope).where(Scope.project_id == project.id))
    assert result.scalars().all() == []
```

- [ ] **Step 10: Run test to verify it fails** (auth.py doesn't exist yet)

```bash
cd ~/vantagepoint/backend
source .venv/bin/activate
pytest tests/test_models.py -v
```

Expected: ImportError — `app.auth` not found.

- [ ] **Step 11: Commit scaffold**

```bash
cd ~/vantagepoint
git add backend/ .env.example
git commit -m "feat: scaffold backend structure, DB layer, and models"
```

---

## Task 3: Backend — Auth

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/deps.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Create `backend/app/auth.py`**

```python
import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
COOKIE_NAME = "access_token"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": subject, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: str = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return sub
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
```

- [ ] **Step 2: Create `backend/app/schemas.py`**

```python
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# --- Auth ---

class LoginRequest(BaseModel):
    email: str
    password: str


class SetupRequest(BaseModel):
    org_name: str
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SetupNeededOut(BaseModel):
    setup_needed: bool


# --- Projects ---

class ProjectCreate(BaseModel):
    name: str
    company_name: str


class ProjectOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    company_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Scope ---

class ScopeCreate(BaseModel):
    value: str
    source: str = "manual"


class ScopeUpdate(BaseModel):
    approved: bool


class ScopeOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    value: str
    source: str
    approved: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create `backend/app/deps.py`**

```python
from fastapi import Cookie, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.auth import COOKIE_NAME, decode_access_token
from app.models import User


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_access_token(access_token)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return current_user
```

- [ ] **Step 4: Create `backend/app/routers/__init__.py`**

```python
```
(empty)

- [ ] **Step 5: Create `backend/app/routers/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import get_db
from app.models import Org, User
from app.auth import hash_password, verify_password, create_access_token, COOKIE_NAME
from app.schemas import LoginRequest, SetupRequest, UserOut, SetupNeededOut
from app.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/setup-needed", response_model=SetupNeededOut)
async def setup_needed(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar()
    return SetupNeededOut(setup_needed=count == 0)


@router.post("/setup", response_model=UserOut)
async def setup(body: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(User))
    if result.scalar() > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setup already complete")

    org = Org(name=body.org_name)
    db.add(org)
    await db.flush()

    user = User(
        org_id=org.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return user


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return user


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 6: Create `backend/app/main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="VantagePoint", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://frontend:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
```

- [ ] **Step 7: Write the failing auth tests**

Create `backend/tests/test_auth.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio


async def test_setup_needed_true(client):
    resp = await client.get("/api/auth/setup-needed")
    assert resp.status_code == 200
    assert resp.json()["setup_needed"] is True


async def test_setup_creates_admin(client):
    resp = await client.post("/api/auth/setup", json={
        "org_name": "Acme",
        "email": "admin@acme.com",
        "password": "strongpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@acme.com"
    assert data["role"] == "admin"


async def test_setup_blocked_second_time(client):
    # First setup
    await client.post("/api/auth/setup", json={
        "org_name": "Acme",
        "email": "admin@acme.com",
        "password": "strongpass123",
    })
    # Second attempt should fail
    resp = await client.post("/api/auth/setup", json={
        "org_name": "Other",
        "email": "other@acme.com",
        "password": "pass",
    })
    assert resp.status_code == 400


async def test_login_success(client, sample_admin):
    resp = await client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@test.com"
    assert "access_token" in resp.cookies


async def test_login_wrong_password(client, sample_admin):
    resp = await client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


async def test_me_unauthenticated(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_authenticated(client, sample_admin):
    login = await client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password123",
    })
    token = login.cookies["access_token"]
    resp = await client.get("/api/auth/me", cookies={"access_token": token})
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@test.com"


async def test_logout_clears_cookie(client, sample_admin):
    login = await client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password123",
    })
    token = login.cookies["access_token"]
    resp = await client.post("/api/auth/logout", cookies={"access_token": token})
    assert resp.status_code == 200
```

- [ ] **Step 8: Run tests**

```bash
cd ~/vantagepoint/backend
source .venv/bin/activate
DATABASE_URL=sqlite+aiosqlite:///:memory: pytest tests/test_models.py tests/test_auth.py -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
cd ~/vantagepoint
git add backend/
git commit -m "feat: add auth — JWT login, setup, logout, me endpoints"
```

---

## Task 4: Backend — Projects and Scope routes

**Files:**
- Create: `backend/app/routers/projects.py`
- Create: `backend/app/routers/scope.py`
- Modify: `backend/app/main.py` (add routers)
- Test: `backend/tests/test_projects.py`

- [ ] **Step 1: Create `backend/app/routers/projects.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models import Project
from app.schemas import ProjectCreate, ProjectOut
from app.deps import get_current_user, require_admin
from app.models import User

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.org_id == current_user.org_id)
    )
    return result.scalars().all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        org_id=current_user.org_id,
        name=body.name,
        company_name=body.company_name,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == current_user.org_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == current_user.org_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await db.delete(project)
    await db.commit()
```

- [ ] **Step 2: Create `backend/app/routers/scope.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models import Project, Scope
from app.schemas import ScopeCreate, ScopeUpdate, ScopeOut
from app.deps import get_current_user, require_admin
from app.models import User

router = APIRouter(prefix="/api/projects/{project_id}/scope", tags=["scope"])


async def _get_project_for_user(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == user.org_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=list[ScopeOut])
async def list_scope(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_for_user(project_id, current_user, db)
    result = await db.execute(select(Scope).where(Scope.project_id == project_id))
    return result.scalars().all()


@router.post("", response_model=ScopeOut, status_code=status.HTTP_201_CREATED)
async def add_scope(
    project_id: uuid.UUID,
    body: ScopeCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_for_user(project_id, current_user, db)
    entry = Scope(project_id=project_id, value=body.value, source=body.source)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.patch("/{scope_id}", response_model=ScopeOut)
async def update_scope(
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    body: ScopeUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_for_user(project_id, current_user, db)
    result = await db.execute(
        select(Scope).where(Scope.id == scope_id, Scope.project_id == project_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope entry not found")
    entry.approved = body.approved
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scope(
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_for_user(project_id, current_user, db)
    result = await db.execute(
        select(Scope).where(Scope.id == scope_id, Scope.project_id == project_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope entry not found")
    await db.delete(entry)
    await db.commit()
```

- [ ] **Step 3: Register routers in `backend/app/main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import auth, projects, scope


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="VantagePoint", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://frontend:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(scope.router)
```

- [ ] **Step 4: Write the failing project tests**

Create `backend/tests/test_projects.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client, email="admin@test.com", password="password123"):
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.cookies["access_token"]


async def test_list_projects_unauthenticated(client):
    resp = await client.get("/api/projects")
    assert resp.status_code == 401


async def test_create_and_list_projects(client, sample_admin):
    token = await _login(client)
    cookies = {"access_token": token}

    create_resp = await client.post("/api/projects", json={
        "name": "Acme Recon",
        "company_name": "Acme Corp",
    }, cookies=cookies)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    list_resp = await client.get("/api/projects", cookies=cookies)
    assert list_resp.status_code == 200
    ids = [p["id"] for p in list_resp.json()]
    assert project_id in ids


async def test_get_project(client, sample_admin):
    token = await _login(client)
    cookies = {"access_token": token}

    create_resp = await client.post("/api/projects", json={
        "name": "Get Test",
        "company_name": "Co",
    }, cookies=cookies)
    project_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/projects/{project_id}", cookies=cookies)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Get Test"


async def test_delete_project(client, sample_admin):
    token = await _login(client)
    cookies = {"access_token": token}

    create_resp = await client.post("/api/projects", json={
        "name": "To Delete",
        "company_name": "Co",
    }, cookies=cookies)
    project_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/projects/{project_id}", cookies=cookies)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/projects/{project_id}", cookies=cookies)
    assert get_resp.status_code == 404


async def test_scope_crud(client, sample_admin):
    token = await _login(client)
    cookies = {"access_token": token}

    proj = await client.post("/api/projects", json={
        "name": "Scope Test",
        "company_name": "Co",
    }, cookies=cookies)
    pid = proj.json()["id"]

    # Add scope entry
    add_resp = await client.post(f"/api/projects/{pid}/scope", json={
        "value": "example.com",
        "source": "manual",
    }, cookies=cookies)
    assert add_resp.status_code == 201
    scope_id = add_resp.json()["id"]
    assert add_resp.json()["approved"] is True

    # List scope
    list_resp = await client.get(f"/api/projects/{pid}/scope", cookies=cookies)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Update (set not approved)
    patch_resp = await client.patch(
        f"/api/projects/{pid}/scope/{scope_id}",
        json={"approved": False},
        cookies=cookies,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["approved"] is False

    # Delete
    del_resp = await client.delete(f"/api/projects/{pid}/scope/{scope_id}", cookies=cookies)
    assert del_resp.status_code == 204

    list_resp2 = await client.get(f"/api/projects/{pid}/scope", cookies=cookies)
    assert list_resp2.json() == []
```

- [ ] **Step 5: Run all backend tests**

```bash
cd ~/vantagepoint/backend
source .venv/bin/activate
DATABASE_URL=sqlite+aiosqlite:///:memory: pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd ~/vantagepoint
git add backend/
git commit -m "feat: add project and scope CRUD routes"
```

---

## Task 5: Docker setup

**Files:**
- Create: `Dockerfile.app`
- Create: `Dockerfile.worker`
- Create: `docker-compose.yml`
- Create: `backend/pytest.ini`

- [ ] **Step 1: Create `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: Create `Dockerfile.app`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 3: Create `Dockerfile.worker`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt celery==5.4.0

COPY backend/ .

# Placeholder — Plan 2 will add scan tools and real task code
CMD ["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"]
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile.app
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app

  frontend:
    build:
      context: frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  postgres_data:
```

- [ ] **Step 5: Commit Docker files**

```bash
cd ~/vantagepoint
git add Dockerfile.app Dockerfile.worker docker-compose.yml backend/pytest.ini
git commit -m "feat: add Docker Compose orchestration and Dockerfiles"
```

---

## Task 6: Frontend scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/Dockerfile`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/test/setup.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "vantagepoint-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0",
    "@tanstack/react-query": "^5.60.5",
    "axios": "^1.7.7"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.10",
    "tailwindcss": "^3.4.14",
    "postcss": "^8.4.47",
    "autoprefixer": "^10.4.20",
    "vitest": "^2.1.4",
    "@vitest/coverage-v8": "^2.1.4",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@testing-library/jest-dom": "^6.6.3",
    "jsdom": "^25.0.1"
  }
}
```

- [ ] **Step 2: Install frontend dependencies**

```bash
cd ~/vantagepoint/frontend
npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

- [ ] **Step 4: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 5: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 6: Create `frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

- [ ] **Step 7: Create `frontend/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 8: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>VantagePoint</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 9: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 10: Create `frontend/src/test/setup.ts`**

```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 11: Create `frontend/src/main.tsx`**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 12: Create `frontend/src/App.tsx`** (placeholder routes — pages added in Task 7)

```typescript
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import SetupPage from './pages/SetupPage'
import DashboardPage from './pages/DashboardPage'
import NewProjectPage from './pages/NewProjectPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

const router = createBrowserRouter([
  { path: '/setup', element: <SetupPage /> },
  { path: '/login', element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/projects/new', element: <NewProjectPage /> },
          { path: '/projects/:id', element: <ProjectDetailPage /> },
        ],
      },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
```

- [ ] **Step 13: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]
```

- [ ] **Step 14: Commit**

```bash
cd ~/vantagepoint
git add frontend/
git commit -m "feat: scaffold React frontend with Vite, Tailwind, React Router, TanStack Query"
```

---

## Task 7: Frontend — API layer and auth hook

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/projects.ts`
- Create: `frontend/src/api/scope.ts`
- Create: `frontend/src/hooks/useAuth.ts`

- [ ] **Step 1: Create `frontend/src/api/client.ts`**

```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  withCredentials: true,   // sends httpOnly cookie automatically
})

export default client
```

- [ ] **Step 2: Create `frontend/src/api/auth.ts`**

```typescript
import client from './client'

export interface User {
  id: string
  org_id: string
  email: string
  role: string
  created_at: string
}

export async function setupNeeded(): Promise<boolean> {
  const { data } = await client.get<{ setup_needed: boolean }>('/auth/setup-needed')
  return data.setup_needed
}

export async function setup(org_name: string, email: string, password: string): Promise<User> {
  const { data } = await client.post<User>('/auth/setup', { org_name, email, password })
  return data
}

export async function login(email: string, password: string): Promise<User> {
  const { data } = await client.post<User>('/auth/login', { email, password })
  return data
}

export async function logout(): Promise<void> {
  await client.post('/auth/logout')
}

export async function me(): Promise<User> {
  const { data } = await client.get<User>('/auth/me')
  return data
}
```

- [ ] **Step 3: Create `frontend/src/api/projects.ts`**

```typescript
import client from './client'

export interface Project {
  id: string
  org_id: string
  name: string
  company_name: string
  created_at: string
}

export async function listProjects(): Promise<Project[]> {
  const { data } = await client.get<Project[]>('/projects')
  return data
}

export async function createProject(name: string, company_name: string): Promise<Project> {
  const { data } = await client.post<Project>('/projects', { name, company_name })
  return data
}

export async function getProject(id: string): Promise<Project> {
  const { data } = await client.get<Project>(`/projects/${id}`)
  return data
}

export async function deleteProject(id: string): Promise<void> {
  await client.delete(`/projects/${id}`)
}
```

- [ ] **Step 4: Create `frontend/src/api/scope.ts`**

```typescript
import client from './client'

export interface ScopeEntry {
  id: string
  project_id: string
  value: string
  source: string
  approved: boolean
}

export async function listScope(project_id: string): Promise<ScopeEntry[]> {
  const { data } = await client.get<ScopeEntry[]>(`/projects/${project_id}/scope`)
  return data
}

export async function addScope(project_id: string, value: string, source = 'manual'): Promise<ScopeEntry> {
  const { data } = await client.post<ScopeEntry>(`/projects/${project_id}/scope`, { value, source })
  return data
}

export async function updateScope(project_id: string, scope_id: string, approved: boolean): Promise<ScopeEntry> {
  const { data } = await client.patch<ScopeEntry>(`/projects/${project_id}/scope/${scope_id}`, { approved })
  return data
}

export async function deleteScope(project_id: string, scope_id: string): Promise<void> {
  await client.delete(`/projects/${project_id}/scope/${scope_id}`)
}
```

- [ ] **Step 5: Create `frontend/src/hooks/useAuth.ts`**

```typescript
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { me, logout as logoutApi, User } from '../api/auth'

export function useAuth() {
  const queryClient = useQueryClient()

  const { data: user, isLoading } = useQuery<User | null>({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await me()
      } catch {
        return null
      }
    },
    staleTime: 60_000,
  })

  async function logout() {
    await logoutApi()
    queryClient.clear()
    window.location.href = '/login'
  }

  return { user: user ?? null, isLoading, logout }
}
```

- [ ] **Step 6: Commit**

```bash
cd ~/vantagepoint
git add frontend/src/api/ frontend/src/hooks/
git commit -m "feat: add frontend API layer and useAuth hook"
```

---

## Task 8: Frontend — Auth pages (Login, Setup)

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/SetupPage.tsx`
- Create: `frontend/src/components/ProtectedRoute.tsx`
- Test: `frontend/src/pages/__tests__/LoginPage.test.tsx`

- [ ] **Step 1: Create `frontend/src/components/ProtectedRoute.tsx`**

```typescript
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function ProtectedRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <span className="text-gray-500">Loading…</span>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
```

- [ ] **Step 2: Create `frontend/src/pages/LoginPage.tsx`**

```typescript
import { useState, FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { login } from '../api/auth'

export default function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate('/')
    } catch {
      setError('Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-8 bg-white p-8 rounded-lg shadow">
        <h1 className="text-2xl font-bold text-gray-900">VantagePoint</h1>
        <h2 className="text-lg text-gray-600">Sign in to your account</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/pages/SetupPage.tsx`**

```typescript
import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { setup } from '../api/auth'

export default function SetupPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [orgName, setOrgName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await setup(orgName, email, password)
      queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate('/')
    } catch {
      setError('Setup failed. It may have already been completed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-8 bg-white p-8 rounded-lg shadow">
        <h1 className="text-2xl font-bold text-gray-900">VantagePoint</h1>
        <h2 className="text-lg text-gray-600">First-time setup</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Organization name</label>
            <input
              type="text"
              value={orgName}
              onChange={e => setOrgName(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Admin email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Write the failing login test**

Create `frontend/src/pages/__tests__/LoginPage.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LoginPage from '../LoginPage'
import * as authApi from '../../api/auth'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function renderLogin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('LoginPage', () => {
  beforeEach(() => mockNavigate.mockClear())

  it('renders email and password fields', () => {
    renderLogin()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('calls login and navigates on success', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      id: '1', org_id: '1', email: 'a@b.com', role: 'admin', created_at: ''
    })
    renderLogin()
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'pass')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'))
  })

  it('shows error on failed login', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue(new Error('bad'))
    renderLogin()
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument())
  })
})
```

- [ ] **Step 5: Run frontend tests**

```bash
cd ~/vantagepoint/frontend
npm test
```

Expected: LoginPage tests pass.

- [ ] **Step 6: Commit**

```bash
cd ~/vantagepoint
git add frontend/src/pages/ frontend/src/components/ProtectedRoute.tsx
git commit -m "feat: add login and setup pages with tests"
```

---

## Task 9: Frontend — Dashboard, New Project, Project Detail, Layout

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Create: `frontend/src/pages/NewProjectPage.tsx`
- Create: `frontend/src/pages/ProjectDetailPage.tsx`
- Test: `frontend/src/pages/__tests__/DashboardPage.test.tsx`

- [ ] **Step 1: Create `frontend/src/components/Layout.tsx`**

```typescript
import { Link, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <Link to="/" className="text-lg font-bold text-blue-600">VantagePoint</Link>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">{user?.email}</span>
          <button
            onClick={logout}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Sign out
          </button>
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Create `frontend/src/pages/DashboardPage.tsx`**

```typescript
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listProjects, Project } from '../api/projects'

export default function DashboardPage() {
  const { data: projects, isLoading, error } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: listProjects,
  })

  if (isLoading) return <p className="text-gray-500">Loading projects…</p>
  if (error) return <p className="text-red-600">Failed to load projects.</p>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Link
          to="/projects/new"
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          New project
        </Link>
      </div>

      {projects?.length === 0 && (
        <p className="text-gray-500">No projects yet. Create one to get started.</p>
      )}

      <ul className="space-y-3">
        {projects?.map(p => (
          <li key={p.id}>
            <Link
              to={`/projects/${p.id}`}
              className="block bg-white rounded-lg border border-gray-200 px-5 py-4 hover:border-blue-400 transition-colors"
            >
              <p className="font-medium text-gray-900">{p.name}</p>
              <p className="text-sm text-gray-500">{p.company_name}</p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/pages/NewProjectPage.tsx`**

```typescript
import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { createProject } from '../api/projects'

export default function NewProjectPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const project = await createProject(name, companyName)
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate(`/projects/${project.id}`)
    } catch {
      setError('Failed to create project. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New project</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Project name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            required
            placeholder="Acme Corp Q2 2026"
            className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Company name</label>
          <p className="text-xs text-gray-500 mt-0.5">Used for automated apex domain discovery</p>
          <input
            type="text"
            value={companyName}
            onChange={e => setCompanyName(e.target.value)}
            required
            placeholder="Acme Corp"
            className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating…' : 'Create project'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Create `frontend/src/pages/ProjectDetailPage.tsx`** (stub — filled in Plan 2)

```typescript
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getProject } from '../api/projects'
import { listScope } from '../api/scope'

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id!),
    enabled: !!id,
  })

  const { data: scope } = useQuery({
    queryKey: ['scope', id],
    queryFn: () => listScope(id!),
    enabled: !!id,
  })

  if (isLoading || !project) return <p className="text-gray-500">Loading…</p>

  return (
    <div>
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <Link to="/" className="hover:text-gray-700">Projects</Link>
        <span>/</span>
        <span>{project.name}</span>
      </div>

      <h1 className="text-2xl font-bold text-gray-900 mb-1">{project.name}</h1>
      <p className="text-gray-500 mb-6">{project.company_name}</p>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Scope</h2>
        {scope?.length === 0 && <p className="text-gray-500 text-sm">No scope entries yet.</p>}
        <ul className="space-y-1">
          {scope?.map(s => (
            <li key={s.id} className="text-sm font-mono text-gray-700 bg-white border border-gray-200 rounded px-3 py-1.5">
              {s.value}
              {!s.approved && <span className="ml-2 text-yellow-600 text-xs">(pending approval)</span>}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Scan runs</h2>
        <p className="text-gray-500 text-sm">Scanning available in Plan 2.</p>
      </section>
    </div>
  )
}
```

- [ ] **Step 5: Write the failing dashboard test**

Create `frontend/src/pages/__tests__/DashboardPage.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DashboardPage from '../DashboardPage'
import * as projectsApi from '../../api/projects'

function renderDashboard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DashboardPage', () => {
  it('shows loading state initially', () => {
    vi.spyOn(projectsApi, 'listProjects').mockReturnValue(new Promise(() => {}))
    renderDashboard()
    expect(screen.getByText(/loading projects/i)).toBeInTheDocument()
  })

  it('renders project list', async () => {
    vi.spyOn(projectsApi, 'listProjects').mockResolvedValue([
      { id: '1', org_id: 'o1', name: 'Acme Recon', company_name: 'Acme Corp', created_at: '' },
    ])
    renderDashboard()
    await waitFor(() => expect(screen.getByText('Acme Recon')).toBeInTheDocument())
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
  })

  it('shows empty state when no projects', async () => {
    vi.spyOn(projectsApi, 'listProjects').mockResolvedValue([])
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/no projects yet/i)).toBeInTheDocument())
  })

  it('shows error state on failure', async () => {
    vi.spyOn(projectsApi, 'listProjects').mockRejectedValue(new Error('fail'))
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/failed to load/i)).toBeInTheDocument())
  })
})
```

- [ ] **Step 6: Run all frontend tests**

```bash
cd ~/vantagepoint/frontend
npm test
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd ~/vantagepoint
git add frontend/src/
git commit -m "feat: add dashboard, new project, and project detail pages with tests"
```

---

## Task 10: Smoke test — full stack via Docker Compose

**Goal:** Verify `docker-compose up` brings up all services and the app is usable end to end.

- [ ] **Step 1: Build and start all services**

```bash
cd ~/vantagepoint
docker-compose up --build -d
```

Expected: all 5 services start without error. Check with:
```bash
docker-compose ps
```
Expected: `db`, `redis`, `backend`, `worker`, `frontend` all show `running` or `Up`.

- [ ] **Step 2: Verify backend health**

```bash
curl http://localhost:8000/api/auth/setup-needed
```

Expected: `{"setup_needed":true}`

- [ ] **Step 3: Run setup via API**

```bash
curl -X POST http://localhost:8000/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"org_name":"Test Org","email":"admin@example.com","password":"password123"}'
```

Expected: `{"id": "...", "email": "admin@example.com", "role": "admin", ...}`

- [ ] **Step 4: Verify frontend loads**

Open `http://localhost:5173` in a browser.

Expected: login page renders.

- [ ] **Step 5: Log in and create a project**

Log in with `admin@example.com` / `password123`. Create a project. Verify it appears in the project list.

- [ ] **Step 6: Stop services**

```bash
docker-compose down
```

- [ ] **Step 7: Final commit and push**

```bash
cd ~/vantagepoint
git add -A
git commit -m "feat: Plan 1 complete — Foundation (Docker, FastAPI, auth, projects, React UI)"
git push
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `docker-compose up` is the complete install | Task 5, 10 |
| FastAPI backend | Tasks 2–4 |
| Postgres + SQLAlchemy 2 async | Task 2 |
| JWT auth (httpOnly cookie) | Task 3 |
| bcrypt passwords | Task 3 |
| admin/viewer roles | Tasks 3–4 |
| Org-scoped data | Tasks 3–4 |
| First-run setup endpoint | Task 3 |
| Project CRUD | Task 4 |
| Scope CRUD with approved flag | Task 4 |
| React + Vite + TypeScript | Task 6 |
| React Router 6 | Tasks 6–9 |
| TanStack Query | Tasks 7–9 |
| Tailwind CSS | Tasks 6–9 |
| Login page | Task 8 |
| Setup page | Task 8 |
| Dashboard (project list) | Task 9 |
| New project page | Task 9 |
| Project detail (stub) | Task 9 |
| ProtectedRoute (auth guard) | Task 8 |
| pytest tests | Tasks 2–4 |
| Vitest + RTL tests | Tasks 8–9 |
| Migration from old design (delete app/) | Task 1 |

**All spec requirements for Plan 1 are covered.**
