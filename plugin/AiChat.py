from time import monotonic

from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.AiChat_d.History import PersonHistory
from plugin.AiChat_d.RequApi import request_reply

_CLEAR_COMMANDS = {"clear"}
_COMMAND_PREFIXES = ("!", "！")

# 群聊未 @ 机器人时，两次自动回复之间的最小间隔（秒）。
# 群消息量远大于私聊，全部交给 LLM 会打爆上游配额。
GROUP_REPLY_COOLDOWN_SECONDS: float = 30.0


class AiChat(PluginBase):
    usable = True

    def __init__(self) -> None:
        self._last_group_reply: dict[str, float] = {}

    def _allow_group_reply(self, group_openid: str) -> bool:
        """判断群聊里是否可以再自动回复一次。

        Args:
            group_openid: 群 openid。

        Returns:
            距上次自动回复超过冷却时间时为 True。
        """
        now: float = monotonic()
        last: float | None = self._last_group_reply.get(group_openid)
        if last is not None and now - last < GROUP_REPLY_COOLDOWN_SECONDS:
            return False
        self._last_group_reply[group_openid] = now
        return True

    @property
    def messageType(
        self,
    ) -> list[MessageType.Group | MessageType.Person]:
        return [
            MessageType.Person.C2C_MESSAGE_CREATE,
            MessageType.Group.GROUP_AT_MESSAGE_CREATE,
            MessageType.Group.GROUP_MESSAGE_CREATE,
        ]

    @property
    def pluginName(self) -> str:
        return "AiChat"

    @staticmethod
    def _session_id(message: MessageData) -> str:
        """返回会话标识。

        优先使用 union_openid，缺失时回退到 author.id。

        Args:
            message: 收到的消息。

        Returns:
            会话标识。
        """
        author = message.d.author
        return author.union_openid or author.id

    async def _reply(self, text: str, message: MessageData) -> None:
        """按消息来源回复文本。

        Args:
            text: 回复内容。
            message: 收到的消息。
        """
        if message.t in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}:
            await HttpSender.sendText2Group(text, message, message.d.group_openid)
        else:
            await HttpSender.sendText2Person(text, message, message.d.author.id)

    async def run(self, message: MessageData) -> None:
        content: str = message.d.content
        session_id: str = self._session_id(message)

        if content.startswith(_COMMAND_PREFIXES):
            command: str = content[1:].split(" ")[0].strip()
            if command in _CLEAR_COMMANDS:
                PersonHistory(session_id).clearHistory()
                await self._reply("已清空历史记录", message)
            else:
                logger.warning(f"未知命令: {command}")
                await self._reply("使用 “!clear” 清空历史记录", message)
            return

        # 群聊里只有被 @ 才必定回复，普通群消息按冷却时间限流
        if message.t == "GROUP_MESSAGE_CREATE" and not self._allow_group_reply(
            message.d.group_openid
        ):
            logger.debug(f"群聊自动回复冷却中，跳过: {message.d.group_openid[:12]}")
            return

        reply: str = await request_reply(content, session_id)
        await self._reply(reply, message)
