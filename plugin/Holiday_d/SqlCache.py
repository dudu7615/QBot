from typing import Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import sqlite3
from sqlmodel import SQLModel, Field, create_engine, Session, select, delete  # type: ignore
from sqlalchemy import Column, String, CheckConstraint, text, event, MetaData


# 创建独立的metadata
_sqlMetadata = MetaData()

# 创建独立的SQLModel基类
class _Model(SQLModel):
    metadata = _sqlMetadata

class Cache(_Model, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    date: datetime
    isHoliday: bool

    @staticmethod
    def addCache(name: str, date: datetime, isHoliday: bool) -> None:
        with Session(_engine) as session:
            session.add(Cache(name=name, date=datetime(date.year, date.month, date.day), isHoliday=isHoliday))
            session.commit()

    @staticmethod
    def getNextHoliday(date: datetime) -> Optional["Cache"]:
        with Session(_engine) as session:
            statement = (
                select(Cache)
                .where(Cache.date >= date)
                .where(Cache.isHoliday == True)
                .order_by(text("date ASC"))
                )
            result = session.exec(statement).first()
            return result
        
    @staticmethod
    def getNextDeHoliday(date: datetime) -> Optional["Cache"]:
        """ 调休 """
        with Session(_engine) as session:
            statement = (
                select(Cache)
                .where(Cache.date >= date)
                .where(Cache.isHoliday == False)
                .order_by(text("date ASC"))
                )
            result = session.exec(statement).first()
            return result

    @staticmethod
    def getCachedYear() -> Optional[datetime]:
        with Session(_engine) as session:
            statement = select(Cache).order_by(text("date DESC")).limit(1)
            result = session.exec(statement).first()
            if result:
                return result.date
            return None
        
    @staticmethod
    def clearCache() -> None:
        with Session(_engine) as session:
            statement = delete(Cache)
            session.exec(statement)
            session.commit()

    
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

_sqlMetadata.create_all(_engine)