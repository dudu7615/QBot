from datetime import date as DateType, datetime
from pathlib import Path
from typing import Any, Optional

import sqlite3
from sqlmodel import SQLModel, Field, create_engine, Session, select
from sqlalchemy import event, MetaData

from modules.Logger import logger

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
            session.add(
                Cache(
                    name=name,
                    date=datetime(date.year, date.month, date.day),
                    isHoliday=isHoliday,
                )
            )
            session.commit()

    @staticmethod
    def _query(
        day: DateType,
        is_holiday: bool,
    ) -> Optional["Cache"]:
        """查询 day 当天或之后的第一个假期/调休。

        Args:
            day: 起始日期（按自然日比较，忽略时分秒）。
            is_holiday: True 查假期，False 查调休。

        Returns:
            匹配的缓存行，没有则返回 None。
        """
        day_start: datetime = datetime(day.year, day.month, day.day)
        with Session(_engine) as session:
            statement = (
                select(Cache)
                .where(Cache.date >= day_start)
                .where(Cache.isHoliday == is_holiday)
                .order_by(Cache.date)  # type: ignore[arg-type]
            )
            return session.exec(statement).first()

    @staticmethod
    def getNextHoliday(day: DateType) -> Optional["Cache"]:
        """查询 day 当天或之后的下一个假期。"""
        return Cache._query(day, True)

    @staticmethod
    def getNextDeHoliday(day: DateType) -> Optional["Cache"]:
        """查询 day 当天或之后的下一个调休。"""
        return Cache._query(day, False)

    @staticmethod
    def getCachedYear() -> Optional[datetime]:
        """返回缓存中最晚的日期，用于判断缓存是否覆盖当前年份。"""
        with Session(_engine) as session:
            latest: Optional[Cache] = session.exec(
                select(Cache).order_by(Cache.date.desc())  # type: ignore[attr-defined,unused-ignore]
            ).first()
        return latest.date if latest is not None else None


# 连接 SQLite 数据库
(Path(__file__).parent / "data").mkdir(parents=True, exist_ok=True)
_sqlite_file = Path(__file__).parent / "data" / "cache.db"
_sqlite_url = f"sqlite:///{_sqlite_file.absolute().as_posix()}"
_engine = create_engine(
    _sqlite_url,
    connect_args={"check_same_thread": False},
    isolation_level="SERIALIZABLE",  # SQLite支持的隔离级别，提供最高的事务隔离
)


@event.listens_for(_engine, "connect")
def _sqlitePragma(dbapi_connection: sqlite3.Connection, connection_record: Any) -> None:  # type: ignore[unused-ignore]
    cursor = dbapi_connection.cursor()
    # 仅保留【必选核心配置】，剔除冗余调试和进阶配置，简洁高效
    cursor.execute("PRAGMA foreign_keys = ON")  # 外键检查（保障数据完整性）
    cursor.execute("PRAGMA journal_mode = WAL")  # 多进程并发核心（1写+多读）
    cursor.execute(
        "PRAGMA busy_timeout = 5000"
    )  # 锁定等待5秒（自动化解简单冲突，无需手动重试）
    cursor.close()


_sqlMetadata.create_all(_engine)
