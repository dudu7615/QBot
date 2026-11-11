from datetime import datetime
from enum import Enum
from pathlib import Path
import sqlite3
from typing import Any, Optional

from sqlmodel import SQLModel, Field, create_engine, Session, select, delete
from sqlalchemy import (
    Column,
    Enum as SAEnum,
    String,
    ForeignKey,
    event,
    func,
    MetaData,
    text,
)

from modules.Logger import logger
from plugin.AiChat_d import Paths

# 创建独立的metadata
_sqlMetadata = MetaData()


# 创建独立的SQLModel基类
class _Model(SQLModel):
    metadata = _sqlMetadata


class MessageRole(str, Enum):
    assistant = "assistant"
    user = "user"
    system = "system"


class User(_Model, table=True):
    openId: str = Field(primary_key=True, max_length=100)
    name: str = Field(index=True, max_length=50)
    createdAt: datetime = Field(default_factory=datetime.now)
    latestChat: datetime = Field(default_factory=datetime.now)
    messageCount: int = Field(default=0)

    @staticmethod
    def addOrUpdate(openId: str, name: str) -> "User":
        with Session(_engine) as session:
            user: Optional[User] = session.get(User, openId)
            if user is None:
                user = User(openId=openId, name=name)
            else:
                user.name = name
                user.latestChat = datetime.now()
            session.add(user)
            try:
                session.commit()
                session.refresh(user)
            except Exception as exc:
                logger.error(f"保存用户失败 openId={openId}: {exc}")
                session.rollback()
            return user

    @staticmethod
    def getByOpenId(openId: str) -> Optional["User"]:
        with Session(_engine) as session:
            return session.get(User, openId)

    @staticmethod
    def touch(openId: str, message_count: int) -> None:
        """更新最后活跃时间与消息计数。

        Args:
            openId: 用户 openid。
            message_count: 该用户当前的消息总数。
        """
        with Session(_engine) as session:
            user: Optional[User] = session.get(User, openId)
            if user is None:
                return
            user.messageCount = message_count
            user.latestChat = datetime.now()
            session.add(user)
            session.commit()


class Message(_Model, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    openId: str = Field(
        sa_column=Column(String, ForeignKey("user.openId", ondelete="CASCADE"))
    )
    content: str = Field(max_length=100000)
    createdAt: datetime = Field(default_factory=datetime.now)
    role: MessageRole = Field(
        sa_column=Column(
            SAEnum(
                MessageRole,
                native_enum=False,
                length=20,
                values_callable=lambda members: [item.value for item in members],
                validate_strings=True,
            ),
            nullable=False,
        )
    )

    @staticmethod
    def addMessage(openId: str, content: str, role: MessageRole) -> "Message":
        """追加一条消息。

        通过 CASCADE 外键保证用户行存在；messageCount 在写入后按实际行数重算，
        避免与截断逻辑互相覆盖。

        Raises:
            SQLAlchemyError: 写入失败（由调用方决定是否中断本轮对话）。
        """
        with Session(_engine) as session:
            if session.get(User, openId) is None:
                User.addOrUpdate(openId, "unknown")

            message = Message(openId=openId, content=content, role=role)
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    @staticmethod
    def addTurn(openId: str, user_content: str, assistant_content: str) -> None:
        """原子写入一问一答。

        同一事务内提交两条消息并更新用户活跃信息，避免进程中断或写入
        失败时历史里只剩半轮对话。

        Args:
            openId: 用户标识。
            user_content: 用户消息。
            assistant_content: 助手回复。

        Raises:
            SQLAlchemyError: 写入失败。
        """
        with Session(_engine) as session:
            if session.get(User, openId) is None:
                User.addOrUpdate(openId, "unknown")

            session.add(
                Message(openId=openId, content=user_content, role=MessageRole.user)
            )
            session.add(
                Message(
                    openId=openId,
                    content=assistant_content,
                    role=MessageRole.assistant,
                )
            )
            session.commit()

        Message._refresh_user_activity(openId)

    @staticmethod
    def _refresh_user_activity(openId: str) -> None:
        """按实际行数刷新用户的 messageCount 与最后活跃时间。

        Args:
            openId: 用户标识。
        """
        User.touch(openId, Message.countByOpenId(openId))

    @staticmethod
    def countByOpenId(openId: str) -> int:
        with Session(_engine) as session:
            statement = select(func.count()).where(Message.openId == openId)
            return int(session.exec(statement).one())

    @staticmethod
    def countByRole(openId: str, role: MessageRole) -> int:
        with Session(_engine) as session:
            statement = (
                select(func.count())
                .where(Message.openId == openId)
                .where(Message.role == role)
            )
            return int(session.exec(statement).one())

    @staticmethod
    def getByOpenId(openId: str) -> list["Message"]:
        """按对话顺序返回用户全部消息。

        排序规则：system prompt 始终在最前，其余按写入顺序（createdAt、id）。

        Args:
            openId: 用户 openid。

        Returns:
            消息列表。
        """
        with Session(_engine) as session:
            statement = (
                select(Message)
                .where(Message.openId == openId)
                .order_by(text("createdAt ASC, id ASC"))
            )
            messages: list[Message] = list(session.exec(statement))

        system: list[Message] = [
            item for item in messages if item.role == MessageRole.system
        ]
        others: list[Message] = [
            item for item in messages if item.role != MessageRole.system
        ]
        return system + others

    @staticmethod
    def clearByOpenId(openId: str) -> None:
        with Session(_engine) as session:
            session.exec(delete(Message).where(Message.openId == openId))  # type: ignore[arg-type]
            try:
                session.commit()
            except Exception as exc:
                logger.error(f"清空历史失败 openId={openId}: {exc}")
                session.rollback()

    @staticmethod
    def resetMessageCount(openId: str) -> None:
        User.touch(openId, 0)

    @staticmethod
    def truncateToIds(openId: str, keep_ids: set[int]) -> None:
        """只保留指定 id 的非 system 消息，其余删除。

        Args:
            openId: 用户 openid。
            keep_ids: 需要保留的消息 id 集合（不含 system prompt）。
        """
        with Session(_engine) as session:
            statement = (
                select(Message)
                .where(Message.openId == openId)
                .where(Message.role != MessageRole.system)
            )
            for message in session.exec(statement):
                if message.id is not None and message.id not in keep_ids:
                    session.delete(message)

            try:
                session.commit()
            except Exception as exc:
                logger.error(f"截断历史失败 openId={openId}: {exc}")
                session.rollback()

        Message._refresh_user_activity(openId)

    @staticmethod
    def truncateTo(openId: str, keep_count: int) -> None:
        """保留最近 keep_count 条消息，删除更早的。

        始终保留最早的一条 system prompt。

        Args:
            openId: 用户 openid。
            keep_count: 保留的最新消息数量（含 system prompt）。
        """
        with Session(_engine) as session:
            all_messages: list[Message] = list(
                session.exec(
                    select(Message)
                    .where(Message.openId == openId)
                    .order_by(text("createdAt ASC, id ASC"))
                )
            )
            if len(all_messages) <= keep_count:
                return

            system_messages: list[Message] = [
                item for item in all_messages if item.role == MessageRole.system
            ]
            others: list[Message] = [
                item for item in all_messages if item.role != MessageRole.system
            ]
            budget: int = max(keep_count - len(system_messages), 0)
            for message in others[: max(len(others) - budget, 0)]:
                session.delete(message)

            try:
                session.commit()
            except Exception as exc:
                logger.error(f"截断历史失败 openId={openId}: {exc}")
                session.rollback()

        User.touch(openId, Message.countByOpenId(openId))


# 连接 SQLite 数据库
_sqlite_file: Path = Paths.DATA / "chat.db"
_sqlite_file.parent.mkdir(parents=True, exist_ok=True)
_sqlite_url: str = f"sqlite:///{_sqlite_file.absolute().as_posix()}"
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


# 创建表
_sqlMetadata.create_all(_engine)
