"""SQLite persistence layer — sessions and per-stage outputs."""

import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "news_reporter.db")
DB_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class NewsSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(500), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="running")  # running | completed | failed

    outputs = relationship("StageOutput", back_populates="session", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="session", cascade="all, delete-orphan")


class StageOutput(Base):
    __tablename__ = "outputs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    stage = Column(String(50), nullable=False)   # brief | raw | verified | article
    content = Column(Text, nullable=False)

    session = relationship("NewsSession", back_populates="outputs")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("NewsSession", back_populates="comments")


def init_db():
    Base.metadata.create_all(engine)


# --- CRUD helpers ---

def create_session(topic: str) -> int:
    init_db()
    with SessionLocal() as db:
        s = NewsSession(topic=topic, status="running")
        db.add(s)
        db.commit()
        db.refresh(s)
        return s.id


def save_output(session_id: int, stage: str, content: str):
    with SessionLocal() as db:
        db.add(StageOutput(session_id=session_id, stage=stage, content=content))
        db.commit()


def complete_session(session_id: int, status: str = "completed"):
    with SessionLocal() as db:
        s = db.get(NewsSession, session_id)
        if s:
            s.status = status
            db.commit()


def list_sessions() -> list[dict]:
    init_db()
    with SessionLocal() as db:
        rows = db.query(NewsSession).order_by(NewsSession.timestamp.desc()).all()
        return [
            {
                "id": r.id,
                "topic": r.topic,
                "timestamp": r.timestamp,
                "status": r.status,
            }
            for r in rows
        ]


def get_session_outputs(session_id: int) -> dict[str, str]:
    with SessionLocal() as db:
        rows = db.query(StageOutput).filter(StageOutput.session_id == session_id).all()
        return {r.stage: r.content for r in rows}


def delete_session(session_id: int):
    with SessionLocal() as db:
        s = db.get(NewsSession, session_id)
        if s:
            db.delete(s)
            db.commit()


def save_comment(session_id: int, question: str, answer: str):
    with SessionLocal() as db:
        db.add(Comment(session_id=session_id, question=question, answer=answer))
        db.commit()


def get_comments(session_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(Comment).filter(Comment.session_id == session_id).order_by(Comment.timestamp).all()
        return [{"question": r.question, "answer": r.answer, "timestamp": r.timestamp} for r in rows]