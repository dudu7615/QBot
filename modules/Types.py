from typing import TypedDict
from enum import Enum


class MessageData_d_Author(TypedDict):
    id: str
    user_openid: str
    union_openid: str

class MessageData_d(TypedDict):
    id: str
    content: str
    timestamp: str
    author: MessageData_d_Author
    message_type: int

class MessageData(TypedDict):
    id: str
    d: MessageData_d
    t: str # 事件类型

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
        GROUP_ADD_ROBOT = "GROUP_ADD_ROBOT"  # 群添加机器人
        GROUP_DEL_ROBOT = "GROUP_DEL_ROBOT"  # 群移除机器人
        GROUP_MSG_RECEIVE = "GROUP_MSG_RECEIVE"  # 群打开消息推送
        GROUP_MSG_REJECT = "GROUP_MSG_REJECT"  # 群关闭消息推送
        SUBSCRIBE_MESSAGE_STATUS = "SUBSCRIBE_MESSAGE_STATUS"  # 订阅消息授权状态变更
