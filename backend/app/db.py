from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Create SQLite engine; check_same_thread=False allows multi-threaded FastAPI access
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

# Session factory for generating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all SQLAlchemy ORM models
Base = declarative_base()

# FastAPI dependency that provides a transactional database session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize and create all tables defined in models
def init_db():
    Base.metadata.create_all(bind=engine)

