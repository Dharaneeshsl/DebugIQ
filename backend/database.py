from pathlib import Path
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "debugiq.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class RegressionRun(Base):
    __tablename__ = "regression_runs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    total_failures = Column(Integer, default=0)
    unique_failures = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    health_score = Column(Float, default=100.0)

    failures = relationship("Failure", back_populates="run", cascade="all, delete")


class Failure(Base):
    __tablename__ = "failures"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String)
    severity = Column(String)
    module = Column(String)
    line_no = Column(Integer)
    message = Column(String)
    category = Column(String)
    cluster_id = Column(Integer)
    priority_score = Column(Float)
    is_duplicate = Column(Boolean, default=False)
    unique_failure_id = Column(Integer)
    run_id = Column(Integer, ForeignKey("regression_runs.id"))

    run = relationship("RegressionRun", back_populates="failures")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def create_run(session: Session, filename: str, total: int, unique: int, critical: int, health: float) -> RegressionRun:
    run = RegressionRun(
        filename=filename,
        total_failures=total,
        unique_failures=unique,
        critical_count=critical,
        health_score=health,
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


def get_run(session: Session, run_id: int) -> Optional[RegressionRun]:
    return session.query(RegressionRun).filter(RegressionRun.id == run_id).first()


def get_runs(session: Session) -> List[RegressionRun]:
    return session.query(RegressionRun).order_by(RegressionRun.uploaded_at.desc()).all()


def get_failures_by_run(session: Session, run_id: int) -> List[Failure]:
    return session.query(Failure).filter(Failure.run_id == run_id).all()


def delete_run(session: Session, run_id: int) -> None:
    run = get_run(session, run_id)
    if run:
        session.delete(run)
        session.commit()