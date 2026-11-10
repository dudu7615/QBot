"""全局数据类型：消息事件与消息体。"""

from enum import Enum

from pydantic import BaseModel


class MessageAuthor(BaseModel):
    """消息发送者信息。"""

    id: str
    user_openid: str
    union_openid: str


class MessageContent(BaseModel):
    """消息体。

    Attributes:
        id: 消息 id，用于被动回复。
        content: 消息文本。
        timestamp: 消息时间戳。
        author: 发送者信息。
        message_type: 遗留字段，固定为 0。
        group_openid: 群 openid（私聊为空字符串）。
    """

    id: str
    content: str
    timestamp: str
    author: MessageAuthor
    message_type: int = 0
    group_openid: str = ""


class MessageData(BaseModel):
    """插件层统一的消息结构。

    Attributes:
        id: 消息 id。
        d: 消息体。
        t: 事件类型。
        event_id: 网关事件 id，用于被动回复。
    """

    id: str
    d: MessageContent
    t: str
    event_id: str = ""


class MessageType:
    class Person(Enum):
        # 单聊事件
        C2C_MESSAGE_CREATE = "C2C_MESSAGE_CREATE"  # C2C消息事件
        FRIEND_ADD = "FRIEND_ADD"  # C2C添加好友
        FRIEND_DEL = "FRIEND_DEL"  # C2C删除好友
        C2C_MSG_REJECT = "C2C_MSG_REJECT"  # C2C关闭消息推送
        C2C_MSG_RECEIVE = "C2C_MSG_RECEIVE"  # C2C打开消息推送

    class Group(Enum):
        # 群聊事件
        GROUP_AT_MESSAGE_CREATE = "GROUP_AT_MESSAGE_CREATE"  # 群消息事件 AT 事件
        GROUP_MESSAGE_CREATE = "GROUP_MESSAGE_CREATE"  # 群消息事件（2026 新协议）
        GROUP_ADD_ROBOT = "GROUP_ADD_ROBOT"  # 群添加机器人
        GROUP_DEL_ROBOT = "GROUP_DEL_ROBOT"  # 群移除机器人
        GROUP_MSG_RECEIVE = "GROUP_MSG_RECEIVE"  # 群打开消息推送
        GROUP_MSG_REJECT = "GROUP_MSG_REJECT"  # 群关闭消息推送
        SUBSCRIBE_MESSAGE_STATUS = "SUBSCRIBE_MESSAGE_STATUS"  # 订阅消息授权状态变更
