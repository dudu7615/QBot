from dataclasses import dataclass
from typing import Literal

from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.Weather_d import SqlCache, GetWeather

# 回复目标：私聊发往 user openid，群聊发往 group openid
ReplyTarget = tuple[Literal["person", "group"], str]


@dataclass(frozen=True)
class _Command:
    """一条 /命令 的解析结果。

    Attributes:
        name: 命令名（不含开头的 /）。
        argument: 命令后的第一个参数，未提供时为空字符串。
        valid: 参数数量是否合法（最多一个参数）。
    """

    name: str
    argument: str
    valid: bool


def _parse_command(content: str) -> _Command:
    """解析以 / 开头的命令文本。

    Args:
        content: 消息内容。

    Returns:
        解析后的命令。参数超过一个时 valid 为 False。
    """
    parts: list[str] = content.split()
    return _Command(
        name=parts[0].lstrip("/"),
        argument=parts[1] if len(parts) > 1 else "",
        valid=len(parts) <= 2,
    )


class Weather(PluginBase):
    usable = True
    messageStartWith = ["/今日天气", "/天气预报", "/常住地"]

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
        return "Weather"

    @staticmethod
    def _reply_target(message: MessageData) -> ReplyTarget:
        """根据消息类型返回 (发送方式, 目标 ID)。"""
        if message.t in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}:
            return ("group", message.d.group_openid)
        return ("person", message.d.author.id)

    async def _reply(self, text: str, message: MessageData) -> None:
        """按消息来源回复文本。

        Args:
            text: 回复内容。
            message: 收到的消息。
        """
        send_type, target = self._reply_target(message)
        if send_type == "group":
            await HttpSender.sendText2Group(text, message, target)
        else:
            await HttpSender.sendText2Person(text, message, target)

    async def _resolve_city(self, argument: str, author_id: str) -> str | None:
        """确定要查询的城市。

        Args:
            argument: 命令后附带的城市名，为空时回退到常住地。
            author_id: 用于查询常住地的用户标识。

        Returns:
            城市名；既未指定也未设置常住地时返回 None。
        """
        if argument:
            return argument
        return SqlCache.User.get(author_id)

    async def run(self, message: MessageData) -> None:
        command = _parse_command(message.d.content)
        author_id: str = message.d.author.id

        if command.name in {"今日天气", "天气预报"}:
            if not command.valid:
                await self._reply(
                    f"输入格式错误. 请输入 /{command.name} <城市名(若已设置常住地, 可省略)>",
                    message,
                )
                return

            city = await self._resolve_city(command.argument, author_id)
            if city is None:
                await self._reply("请先设置常住地", message)
                return

            if command.name == "今日天气":
                weather = await GetWeather.getTodayWeather(city)
            else:
                weather = await GetWeather.getFutureWeather(city)

            logger.info(f"发送天气信息: {weather}")
            await self._reply(weather, message)

        elif command.name == "常住地":
            if not command.valid or not command.argument:
                await self._reply("输入格式错误. 请输入 /常住地 <城市名>", message)
                return

            SqlCache.User.add(author_id, command.argument)
            await self._reply(f"设置常住地: {command.argument}", message)
