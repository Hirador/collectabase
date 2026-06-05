import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

def get_database_url() -> str:
    # Inside Docker, /app always exists – use the environment variable or a safe default.
    # SQLite absolute path on Linux needs 4 slashes: sqlite:////absolute/path
    if os.path.exists("/app"):
        return os.getenv("DATABASE_URL", "sqlite:////app/data/games.db")

    # Local development: store next to the backend source
    local_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "data")
    os.makedirs(local_data_dir, exist_ok=True)
    local_db_path = os.path.join(local_data_dir, "games.db")
    return f"sqlite:///{local_db_path.replace(chr(92), '/')}"

engine = create_engine(get_database_url(), connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    # WAL lets readers and a writer coexist without blocking each other — needed
    # now that multiple users (e.g. co-owners of a shared collection) can write
    # concurrently. busy_timeout makes a contending writer wait instead of erroring.
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    """Dependency to provide a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
