from typing import Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import sqlite3
from sqlmodel import SQLModel, Field, create_engine, Session, select, delete  # type: ignore
from sqlalchemy import Column, String, CheckConstraint, text, ForeignKey, event, MetaData


class WeatherType(str, Enum):
    today = "today"
    future = "future"

class Cache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    weatherType: WeatherType = Field(
        sa_column=Column(
            String(20),
            CheckConstraint("weatherType IN ('today','future')"),
            nullable=False,
        )
    )
    createdAt: datetime = Field(default_factory=datetime.now)
    detal: str

    @staticmethod
    def addCache(path: str, detal: str, weaterType: WeatherType) -> None:
        with Session(_engine) as session:
            cache = Cache(name=path, detal=detal, weatherType=weaterType)
            session.add(cache)
            session.commit()

    @staticmethod
    def getByPath(path: str) -> Optional["Cache"]:
        with Session(_engine) as session:
            statement = select(Cache).where(Cache.name == path).order_by(text("createdAt DESC"))
            cache = session.exec(statement).first()
            if cache and cache.createdAt > datetime.now() - timedelta(hours=1):
                return cache
            else:
                return None
            

class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    
    openId: str = Field(primary_key=True)
    name: Optional[str] = Field(default=None)
    location: str

    @staticmethod
    def add(openId: str, location: str) -> None:
        with Session(_engine) as session:
            user = User(openId=openId, location=location)
            session.add(user)
            session.commit()

    @staticmethod
    def get(openId: str) -> Optional[str]:
        with Session(_engine) as session:
            statement = select(User).where(User.openId == openId)
            user = session.exec(statement).first()
            if user:
                return user.location
            else:
                return None

# 连接 SQLite 数据库
(Path(__file__).parent / "data").mkdir(parents=True, exist_ok=True)
_sqlite_file = Path(__file__).parent / "data" / "cache.db"
_sqlite_file.parent.mkdir(parents=True, exist_ok=True)
_sqlite_url = f"sqlite:///{_sqlite_file.absolute().as_posix()}"
_engine = create_engine(
    _sqlite_url,
    connect_args={"check_same_thread": False},
    isolation_level="SERIALIZABLE"  # SQLite支持的隔离级别，提供最高的事务隔离
)


@event.listens_for(_engine, "connect")
def _sqlitePragma(dbapi_connection: sqlite3.Connection, connection_record: Any):  # type: ignore
    cursor = dbapi_connection.cursor()
    # 仅保留【必选核心配置】，剔除冗余调试和进阶配置，简洁高效
    cursor.execute("PRAGMA foreign_keys = ON")    # 外键检查（保障数据完整性）
    cursor.execute("PRAGMA journal_mode = WAL")   # 多进程并发核心（1写+多读）
    cursor.execute("PRAGMA busy_timeout = 5000")  # 锁定等待5秒（自动化解简单冲突，无需手动重试）
    cursor.close()

SQLModel.metadata.create_all(_engine)