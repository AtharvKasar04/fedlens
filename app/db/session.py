from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Default to the Docker database we set up
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://fomc_user:fomc_password@localhost/fomc_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
