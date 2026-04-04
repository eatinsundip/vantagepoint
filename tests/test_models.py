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
