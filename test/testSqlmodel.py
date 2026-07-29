from pathlib import Path
from typing import Optional, Any
import sqlite3
from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field, create_engine, Session, select, Relationship  # type: ignore
from sqlalchemy import Column, String, CheckConstraint, text, ForeignKey, event

ROOT = Path(__file__).parent
sqlDir = ROOT / "sql"


class User(SQLModel, table=True):
    openId: str = Field(primary_key=True, max_length=100)
    name: str = Field(index=True, max_length=50)
    createdAt: datetime = Field(default_factory=datetime.now)
    latestChat: datetime = Field(default_factory=datetime.now)

    @staticmethod
    def addOrUpdate(openId: str, name: str) -> "User":
        with Session(engine) as session:
            user = session.get(User, openId)
            if user is None:
                user = User(openId=openId, name=name)
                session.add(user)
            else:
                user.name = name
                user.latestChat = datetime.now()
                session.add(user)

            try:
                session.commit()
                session.refresh(user)
            except Exception:
                session.rollback()

            return user

    @staticmethod
    def getByOpenId(openId: str) -> Optional["User"]:
        with Session(engine) as session:
            return session.get(User, openId)

    @staticmethod
    def delByOpenId(openId: str) -> None:
        with Session(engine) as session:
            user = session.get(User, openId)
            if user:
                session.delete(user)
                try:
                    session.commit()
                except Exception:
                    session.rollback()


class MessageRole(str, Enum):
    assistant = "assistant"
    user = "user"
    system = "system"


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    openId: str = Field(
        sa_column=Column(String, ForeignKey("user.openId", ondelete="CASCADE"))
    )
    content: str = Field()
    createdAt: datetime = Field(default_factory=datetime.now)
    role: MessageRole = Field(
        sa_column=Column(
            String(20),
            CheckConstraint("role IN ('assistant','user','system')"),
            nullable=False,
        )
    )

    @staticmethod
    def addMessage(openId: str, content: str, role: MessageRole) -> "Message":
        with Session(engine) as session:
            msg = Message(openId=openId, content=content, role=role)
            session.add(msg)
            user = session.get(User, openId)
            if user:
                user.latestChat = datetime.now()
                session.add(user)

            try:
                session.commit()
                session.refresh(msg)
            except Exception:
                session.rollback()

            return msg

    @staticmethod
    def getByOpenId(openId: str) -> list[dict[str, str]]:
        with Session(engine) as session:
            statement = (
                select(Message)
                .where(Message.openId == openId)
                .order_by(text("createdAt ASC"))
            )

            results = session.exec(statement)
            return [{"role": msg.role.value, "content": msg.content} for msg in results]

    @staticmethod
    def delByOpenId(openId: str) -> None:
        with Session(engine) as session:
            statement = select(Message).where(Message.openId == openId)
            results = session.exec(statement)

            for msg in results:
                session.delete(msg)
            try:
                session.commit()
            except Exception:
                session.rollback()


# 连接 SQLite 数据库
sqlite_file = Path(__file__).parent / "temp" / "chat.db"
sqlite_file.parent.mkdir(parents=True, exist_ok=True)
sqlite_url = f"sqlite:///{sqlite_file.absolute().as_posix()}"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


# 在 SQLite 连接上启用外键约束
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: sqlite3.Connection, connection_record: Any
) -> None:
    try:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
    except Exception:
        # fallback for pysqlite which may require a cursor
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


# 创建表
SQLModel.metadata.create_all(engine)


sql = ...
