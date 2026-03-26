from pathlib import Path
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    text,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from passlib.context import CryptContext

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "debugiq.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class RegressionRun(Base):
    __tablename__ = "regression_runs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    total_failures = Column(Integer, default=0)
    unique_failures = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    health_score = Column(Float, default=100.0)
    user_id = Column(Integer, nullable=True)

    failures = relationship("Failure", back_populates="run", cascade="all, delete")


class Failure(Base):
    __tablename__ = "failures"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String)
    severity = Column(String)
    module = Column(String)
    line_no = Column(Integer)
    message = Column(String)
    context = Column(String)
    category = Column(String)
    cluster_id = Column(Integer)
    priority_score = Column(Float)
    is_duplicate = Column(Boolean, default=False)
    unique_failure_id = Column(Integer)
    run_id = Column(Integer, ForeignKey("regression_runs.id"))

    run = relationship("RegressionRun", back_populates="failures")


class UploadJob(Base):
    __tablename__ = "upload_jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    filename = Column(String, nullable=False)
    raw_logs_text = Column(Text, nullable=False)
    status = Column(String, default="queued")  # queued | processing | completed | failed
    error = Column(Text, nullable=True)
    run_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # admin | user
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_context_column()
    _ensure_user_columns()


def _ensure_context_column() -> None:
    """
    Lightweight migration to add context column if missing.
    """
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(failures)"))
        cols = [row[1] for row in res.fetchall()]
        if "context" not in cols:
            conn.execute(text("ALTER TABLE failures ADD COLUMN context TEXT"))


def _ensure_user_columns() -> None:
    with engine.connect() as conn:
        # regression_runs.user_id
        res = conn.execute(text("PRAGMA table_info(regression_runs)"))
        cols = [row[1] for row in res.fetchall()]
        if "user_id" not in cols:
            conn.execute(text("ALTER TABLE regression_runs ADD COLUMN user_id INTEGER"))

        # upload_jobs.user_id
        res = conn.execute(text("PRAGMA table_info(upload_jobs)"))
        cols = [row[1] for row in res.fetchall()]
        if "user_id" not in cols:
            conn.execute(text("ALTER TABLE upload_jobs ADD COLUMN user_id INTEGER"))


def create_run(
    session: Session,
    filename: str,
    total: int,
    unique: int,
    critical: int,
    health: float,
    *,
    user_id: int | None = None,
) -> RegressionRun:
    run = RegressionRun(
        filename=filename,
        total_failures=total,
        unique_failures=unique,
        critical_count=critical,
        health_score=health,
        user_id=user_id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def add_failures(session: Session, run_id: int, failures: List[dict]) -> None:
    records = []
    for f in failures:
        records.append(
            Failure(
                timestamp=f.get("timestamp"),
                severity=f.get("severity"),
                module=f.get("module"),
                line_no=f.get("line_no"),
                message=f.get("message"),
                context=f.get("context"),
                category=f.get("category"),
                cluster_id=f.get("cluster_id"),
                priority_score=f.get("priority_score"),
                is_duplicate=f.get("is_duplicate"),
                unique_failure_id=f.get("unique_failure_id"),
                run_id=run_id,
            )
        )
    session.bulk_save_objects(records)
    session.commit()


def get_run(session: Session, run_id: int, *, user_id: int | None = None) -> Optional[RegressionRun]:
    q = session.query(RegressionRun).filter(RegressionRun.id == run_id)
    if user_id is not None:
        q = q.filter(RegressionRun.user_id == user_id)
    return q.first()


def get_runs(session: Session, *, user_id: int | None = None) -> List[RegressionRun]:
    q = session.query(RegressionRun)
    if user_id is not None:
        q = q.filter(RegressionRun.user_id == user_id)
    return q.order_by(RegressionRun.uploaded_at.desc()).all()


def get_failures_by_run(session: Session, run_id: int) -> List[Failure]:
    return session.query(Failure).filter(Failure.run_id == run_id).all()


def delete_run(session: Session, run_id: int) -> None:
    run = get_run(session, run_id)
    if run:
        session.delete(run)
        session.commit()


def get_history_counts(session: Session) -> dict:
    """
    Aggregate historical failures by module+category for recurrence scoring.
    """
    results = (
        session.query(Failure.module, Failure.category)
        .all()
    )
    counts: dict = {}
    for mod, cat in results:
        key = f"{mod}:{cat}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def create_upload_job(session: Session, filename: str, raw_logs_text: str, *, user_id: int | None = None) -> UploadJob:
    job = UploadJob(filename=filename, raw_logs_text=raw_logs_text, status="queued", user_id=user_id)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_upload_job(session: Session, job_id: int) -> Optional[UploadJob]:
    return session.query(UploadJob).filter(UploadJob.id == job_id).first()


def set_upload_job_status(
    session: Session,
    job_id: int,
    status: str,
    *,
    error: Optional[str] = None,
    run_id: Optional[int] = None,
) -> None:
    job = get_upload_job(session, job_id)
    if not job:
        return
    job.status = status
    if error is not None:
        job.error = error
    if run_id is not None:
        job.run_id = run_id
    session.commit()


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.query(User).filter(User.username == username).first()


def create_user(session: Session, username: str, password: str, role: str) -> User:
    hashed = pwd_context.hash(password)
    user = User(username=username, password_hash=hashed, role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def admin_exists(session: Session) -> bool:
    res = session.execute(select(User.id).where(User.role == "admin").limit(1)).first()
    return res is not None
