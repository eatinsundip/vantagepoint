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
