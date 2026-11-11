import asyncio
from datetime import date, datetime

from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.Holiday_d import RequApi
from plugin.Holiday_d.SqlCache import Cache


class Holiday(PluginBase):
    usable = True
    messageStartWith = "/最近假期"

    _checked = False

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
        return "Holiday"

    @staticmethod
    def _format(cache: Cache) -> str:
        """把一条假期记录格式化为 ``名称（YYYY-MM-DD）``。"""
        return f"{cache.name}（{cache.date.strftime('%Y-%m-%d')}）"

    async def run(self, message: MessageData) -> None:
        if not self._checked:
            # 拉取年度数据是同步 HTTP，放到线程池避免阻塞事件循环。
            # 只有刷新成功才置位，否则下次请求会继续重试。
            refreshed: bool = await asyncio.to_thread(RequApi.ensure_cache_fresh)
            self._checked = refreshed

        today: date = date.today()
        # SQLite 读取放到线程池，避免阻塞事件循环
        next_holiday, next_de_holiday = await asyncio.to_thread(
            lambda: (Cache.getNextHoliday(today), Cache.getNextDeHoliday(today))
        )

        if next_holiday is None:
            reply = "没有找到下一个假期"
        elif next_de_holiday is None:
            reply = f"下一个假期是{self._format(next_holiday)}"
        else:
            reply = (
                f"下一个假期是{self._format(next_holiday)}\n"
                f"下一个调休是{self._format(next_de_holiday)}"
            )

        logger.info(f"查询最近假期: {reply}")
        if message.t in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}:
            await HttpSender.sendText2Group(reply, message, message.d.group_openid)
        else:
            await HttpSender.sendText2Person(reply, message, message.d.author.id)
