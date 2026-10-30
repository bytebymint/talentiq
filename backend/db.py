import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, event, Column, String, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.orm import declarative_base, sessionmaker

DATA = Path(os.environ.get('TALENTIQ_DATA_DIR', './data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / 'documents').mkdir(exist_ok=True)
engine = create_engine(f'sqlite:///{DATA / "talentiq.db"}', connect_args={'check_same_thread': False})
@event.listens_for(engine, 'connect')
def pragmas(conn, _):
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()
def uid(): return uuid.uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()

class Record:
    id = Column(String, primary_key=True, default=uid)
    created_at = Column(String, default=now, nullable=False)

class User(Record, Base):
    __tablename__ = 'users'
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False, default='admin')

class Login(Record, Base):
    __tablename__ = 'sessions'
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    expires = Column(Float, nullable=False)

class Profile(Record, Base):
    __tablename__ = 'profiles'
    name = Column(String, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    archived = Column(Integer, default=0)
    config = Column(JSON, nullable=False)

class ProfileVersion(Record, Base):
    __tablename__ = 'profile_versions'
    profile_id = Column(String, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    config = Column(JSON, nullable=False)

class Project(Record, Base):
    __tablename__ = 'projects'
    name = Column(String, nullable=False)
    department = Column(String, default='')
    profile_id = Column(String, ForeignKey('profiles.id'), nullable=False)
    archived = Column(Integer, default=0)

class Folder(Record, Base):
    __tablename__ = 'folders'
    name = Column(String, nullable=False)
    parent_id = Column(String, ForeignKey('folders.id', ondelete='CASCADE'))

class Candidate(Record, Base):
    __tablename__ = 'candidates'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String, nullable=False)
    status = Column(String, default='Imported', nullable=False)
    shortlisted = Column(Integer, default=0)
    reviewer = Column(String, default='')
    interview_date = Column(String, default='')
    notes = Column(JSON, default=list)
    details = Column(JSON, default=dict)

class Document(Record, Base):
    __tablename__ = 'documents'
    candidate_id = Column(String, ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False, index=True)
    folder_id = Column(String, ForeignKey('folders.id', ondelete='SET NULL'))
    filename = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    hash = Column(String, nullable=False, index=True)
    storage_name = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    pages = Column(JSON, default=list)
    warnings = Column(JSON, default=list)

class Evaluation(Record, Base):
    __tablename__ = 'evaluations'
    candidate_id = Column(String, ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_id = Column(String, ForeignKey('profiles.id'), nullable=False)
    profile_version = Column(Integer, nullable=False)
    profile_snapshot = Column(JSON, nullable=False)
    model = Column(String, nullable=False)
    scoring_version = Column(String, default='documented-v1')
    score = Column(Float)
    coverage = Column(Float, nullable=False)
    result = Column(JSON, nullable=False)
    duration = Column(Float, nullable=False)

class Job(Record, Base):
    __tablename__ = 'jobs'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    state = Column(String, default='queued', nullable=False)
    profile_snapshot = Column(JSON, nullable=False)
    profile_version = Column(Integer, nullable=False)
    model = Column(String, nullable=False)
    items = Column(JSON, default=list)
    current = Column(String)
    stage = Column(String, default='Waiting')
    error = Column(Text)
    updated_at = Column(String, default=now)

class Embedding(Record, Base):
    __tablename__ = 'embeddings'
    candidate_id = Column(String, ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False, index=True)
    document_id = Column(String, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    model = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    page = Column(Integer, nullable=False)
    passage = Column(Text, nullable=False)
    vector = Column(JSON, nullable=False)

class Comparison(Record, Base):
    __tablename__ = 'comparisons'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    name = Column(String, nullable=False)
    candidate_ids = Column(JSON, nullable=False)

class Message(Record, Base):
    __tablename__ = 'chat_messages'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)

class Audit(Record, Base):
    __tablename__ = 'audit'
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    target = Column(String, default='')
    project_id = Column(String, index=True)
    info = Column(JSON, default=dict)

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)

def audit(db, actor, action, target='', project_id=None, **info):
    db.add(Audit(actor=actor, action=action, target=target, project_id=project_id, info=info))

def migrate():
    # Numbered additive migrations; use a single backend worker.
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.exec_driver_sql('INSERT OR IGNORE INTO schema_migrations VALUES (1, ?)', (now(),))
    with Session() as db:
        for j in db.query(Job).filter(Job.state.in_(['queued','processing','pausing','stopping'])).all():
            j.state = 'paused'
            j.current = None
            j.stage = 'Recovered after restart; resume to retry interrupted candidates.'
            j.items = [{**i, 'state': 'pending'} if i['state'] == 'processing' else i for i in j.items]
        db.commit()
