from typing import Optional, Any
from datetime import datetime
from enum import Enum
import sqlite3
from sqlmodel import SQLModel, Field, create_engine, Session, select, Relationship  # type: ignore
from sqlalchemy import Column, String, CheckConstraint, text, ForeignKey, event


from plugin.GlmAi_d import Paths


class User(SQLModel, table=True):
    openId: str = Field(primary_key=True, max_length=100)
    name: str = Field(index=True, max_length=50)
    createdAt: datetime = Field(default_factory=datetime.now)
    latestChat: datetime = Field(default_factory=datetime.now)
    messageCount: int = Field(default=0)

    @staticmethod
    def addOrUpdate(openId: str, name: str) -> "User":
        with Session(_engine) as session:
            user = session.get(User, openId)
            if user is None:
                user = User(openId=openId, name=name)
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
        with Session(_engine) as session:
            return session.get(User, openId)

    @staticmethod
    def delByOpenId(openId: str) -> None:
        with Session(_engine) as session:
            if user := session.get(User, openId):
                session.delete(user)
                try:
                    session.commit()
                except Exception:
                    session.rollback()

    @staticmethod
    def getmessageCount(openId: str) -> int:

        user = User.getByOpenId(openId)
        
        return user.messageCount if user else 0

class MessageRole(str, Enum):
    assistant = "assistant"
    user = "user"
    system = "system"


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    openId: str = Field(
        sa_column=Column(String, ForeignKey("user.openId", ondelete="CASCADE"))
    )
    content: str = Field(max_length=100000)
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
        with Session(_engine) as session:
            msg = Message(openId=openId, content=content, role=role)
            session.add(msg)
            if not ( user := session.get(User, openId)):
                User.addOrUpdate(openId, "Unknown")
            else:
                user.messageCount = user.messageCount + 1
                user.latestChat = datetime.now()

            try:
                session.commit()
                session.refresh(msg)
            except Exception:
                session.rollback()

            return msg

    @staticmethod
    def getByOpenId(openId: str) -> list[dict[str, str]]:
        with Session(_engine) as session:
            statement = (
                select(Message)
                .where(Message.openId == openId)
                .order_by(text("createdAt ASC"))
            )

            results = session.exec(statement)
            return [{"role": msg, "content": msg.content} for msg in results]  # type: ignore

    @staticmethod
    def clearByOpenId(openId: str) -> None:
        with Session(_engine) as session:
            statement = select(Message).where(Message.openId == openId)
            results = session.exec(statement)

            for msg in results:
                session.delete(msg)
            # set messageCount to 0
            if user := session.get(User, openId):
                user.messageCount = 0
                user.latestChat = datetime.now()
            try:
                session.commit()
            except Exception:
                session.rollback()


# 连接 SQLite 数据库
_sqlite_file = Paths.DATA / "chat.db"
_sqlite_file.parent.mkdir(parents=True, exist_ok=True)
_sqlite_url = f"sqlite:///{_sqlite_file.absolute().as_posix()}"
_engine = create_engine(_sqlite_url, connect_args={"check_same_thread": False})


@event.listens_for(_engine, "connect")
def _sqlitePragma(dbapi_connection: sqlite3.Connection, connection_record: Any):  # type: ignore
    cursor = dbapi_connection.cursor()
    # 必开4个核心配置（外键+WAL+最高安全+自动校验）
    cursor.execute("PRAGMA foreign_keys = ON")    # 外键检查
    cursor.execute("PRAGMA journal_mode = WAL")   # 断电安全
    cursor.execute("PRAGMA synchronous = FULL")   # 写盘安全
    cursor.execute("PRAGMA cache_size = -20000")  # 20MB缓存提速
    cursor.close()


# 创建表
SQLModel.metadata.create_all(_engine)
