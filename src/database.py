"""Database models and initialization for fraud detection system."""

import json
import os
from datetime import datetime
from pathlib import Path

import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Database setup
DB_PATH = Path(__file__).parent.parent / "fraud_detection.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
DEFAULT_ADMIN_EMAIL = os.getenv("FRAUD_DETECTION_ADMIN_EMAIL", "admin@fraud.local")
DEFAULT_ADMIN_PASSWORD = os.getenv("FRAUD_DETECTION_ADMIN_PASSWORD", "Admin@12345")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(String(50), default="user", nullable=False)
    force_password_change = Column(Boolean, default=True, nullable=False)

    # Relationship
    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))


class Analysis(Base):
    """Analysis record model."""
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    analyzer_email = Column(String(255), nullable=True)
    filename = Column(String(255), nullable=False)
    input_file_path = Column(String(512), nullable=False)  # Path to uploaded file
    report_file_path = Column(String(512), nullable=True)  # Path to exported report
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analysis_type = Column(String(50), default="standard", nullable=False)  # e.g., "standard", "batch"

    # Results stored as JSON for flexibility
    results_json = Column(Text, nullable=True)  # Serialized DataFrame/dict of results
    summary = Column(Text, nullable=True)  # Human-readable summary

    # Statistics
    total_rows = Column(Integer, nullable=True)
    suspicious_count = Column(Integer, nullable=True)
    avg_risk_score = Column(Float, nullable=True)

    # Relationship
    user = relationship("User", back_populates="analyses")

    def set_results(self, results_data: dict) -> None:
        """Store results as JSON."""
        self.results_json = json.dumps(results_data, default=str)

    def get_results(self) -> dict:
        """Retrieve results from JSON."""
        if self.results_json:
            return json.loads(self.results_json)
        return {}


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    migrate_users_table()
    migrate_analyses_table()
    seed_default_admin()
    print(f"Database initialized at {DB_PATH}")


def migrate_users_table() -> None:
    """Add missing user columns for older SQLite databases."""
    with engine.begin() as connection:
        existing_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(users)"))
        }

        if "role" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'user' NOT NULL"))
        if "force_password_change" not in existing_columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN force_password_change BOOLEAN DEFAULT 1 NOT NULL")
            )


def migrate_analyses_table() -> None:
    """Add missing analysis columns for older SQLite databases."""
    with engine.begin() as connection:
        existing_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(analyses)"))
        }

        if "analyzer_email" not in existing_columns:
            connection.execute(text("ALTER TABLE analyses ADD COLUMN analyzer_email VARCHAR(255)"))


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_default_admin() -> User | None:
    """Create the default admin user if it does not exist."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL).first()
        if admin:
            return admin

        admin = User(
            email=DEFAULT_ADMIN_EMAIL,
            role="admin",
            force_password_change=True,
            is_active=True,
        )
        admin.set_password(DEFAULT_ADMIN_PASSWORD)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin
    finally:
        db.close()


def create_user(
    email: str,
    password: str,
    role: str = "user",
    force_password_change: bool = True,
) -> User:
    """Create a new user."""
    db = SessionLocal()
    try:
        # Check if user exists
        normalized_email = email.strip().lower()
        existing = db.query(User).filter(User.email == normalized_email).first()
        if existing:
            raise ValueError(f"User with email {normalized_email} already exists")

        user = User(
            email=normalized_email,
            role=role,
            force_password_change=force_password_change,
        )
        user.set_password(password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def get_user_by_email(email: str) -> User | None:
    """Get user by email."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email.strip().lower()).first()
    finally:
        db.close()


def get_user_by_id(user_id: int) -> User | None:
    """Get user by ID."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def authenticate_user(email: str, password: str) -> User | None:
    """Authenticate user by email and password."""
    user = get_user_by_email(email)
    if user and user.verify_password(password):
        return user
    return None


def change_user_password(user_id: int, new_password: str) -> User:
    """Update a user's password and clear the forced-change flag."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        user.set_password(new_password)
        user.force_password_change = False
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def get_user_role(user_id: int) -> str | None:
    """Get the role for a user."""
    user = get_user_by_id(user_id)
    return user.role if user else None


def create_analysis(
    user_id: int,
    analyzer_email: str,
    filename: str,
    input_file_path: str,
    results_df: dict,
    total_rows: int = None,
    suspicious_count: int = None,
    avg_risk_score: float = None,
) -> Analysis:
    """Create a new analysis record."""
    db = SessionLocal()
    try:
        analysis = Analysis(
            user_id=user_id,
            analyzer_email=analyzer_email,
            filename=filename,
            input_file_path=input_file_path,
            total_rows=total_rows,
            suspicious_count=suspicious_count,
            avg_risk_score=avg_risk_score,
        )
        analysis.set_results(results_df)
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis
    finally:
        db.close()


def get_user_analyses(user_id: int) -> list[Analysis]:
    """Get all analyses for a user, ordered by most recent first."""
    db = SessionLocal()
    try:
        return db.query(Analysis).filter(Analysis.user_id == user_id).order_by(Analysis.created_at.desc()).all()
    finally:
        db.close()


def get_analysis_by_id(analysis_id: int, user_id: int) -> Analysis | None:
    """Get specific analysis (verifies ownership)."""
    db = SessionLocal()
    try:
        return db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == user_id).first()
    finally:
        db.close()


def update_analysis_report(analysis_id: int, report_file_path: str) -> None:
    """Update report file path for an analysis."""
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.report_file_path = report_file_path
            db.commit()
    finally:
        db.close()
