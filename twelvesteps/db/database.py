import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv
import os




import pathlib
env_path = pathlib.Path(__file__).parent.parent.parent / "backend.env"
load_dotenv(env_path)

class Base(DeclarativeBase):

    def __repr__(self):
        cols = []
        for col in self.__table__.columns.keys():

            cols.append(f"{col}={getattr(self, col)}")
        return f"{self.__class__.__name__}(" + ", ".join(cols) + ")"
    pass


_database_url = os.getenv("DATABASE_URL")
if not _database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_async_engine(
    url=_database_url,
    echo=os.getenv("SQL_DEBUG", "").lower() in ("1", "true", "yes"),
)


async_session_factory = async_sessionmaker(
    engine,
    class_ = AsyncSession,
    expire_on_commit=False)




