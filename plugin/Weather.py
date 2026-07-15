from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.Weather_d import SqlCache, GetWeather


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
    def _reply_target(message: MessageData) -> tuple[str, str]:
        """根据消息类型返回 (发送方式, 目标 ID)。"""
        if message["t"] in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}:
            return ("group", message["d"]["group_openid"])
        return ("person", message["d"]["author"]["id"])

    async def run(self, message: MessageData):
        content = message["d"]["content"]
        author = message["d"]["author"]
        if content.startswith("/今日天气"):
            if len(content.split(" ")) != 2:
                weather = (
                    "输入格式错误. 请输入 /今日天气 <城市名(若已设置常住地, 可省略)>"
                )
            else:
                city = content.split(" ")[1]
                if city:
                    weather = await GetWeather.getTodayWeather(city)
                else:
                    city = SqlCache.User.get(author["id"])
                    if city:
                        weather = await GetWeather.getTodayWeather(city)
                    else:
                        weather = "请先设置常住地"
            logger.info(f"发送天气信息: {weather}")
            send_type, target = self._reply_target(message)
            if send_type == "group":
                await HttpSender.sendText2Group(weather, message, target)
            else:
                await HttpSender.sendText2Person(weather, message, target)

        elif content.startswith("/天气预报"):
            if len(content.split(" ")) != 2:
                weather = (
                    "输入格式错误. 请输入 /天气预报 <城市名(若已设置常住地, 可省略)>"
                )
            else:
                city = content.split(" ")[1]
                if city:
                    weather = await GetWeather.getFutureWeather(city)
                else:
                    city = SqlCache.User.get(author["id"])
                    if city:
                        weather = await GetWeather.getFutureWeather(city)
                    else:
                        weather = "请先设置常住地"

            logger.info(f"发送天气信息: {weather}")
            send_type, target = self._reply_target(message)
            if send_type == "group":
                await HttpSender.sendText2Group(weather, message, target)
            else:
                await HttpSender.sendText2Person(weather, message, author["id"])

        elif content.startswith("/常住地"):
            if len(content.split(" ")) != 2:
                send_type, target = self._reply_target(message)
                if send_type == "group":
                    await HttpSender.sendText2Group(
                        "输入格式错误. 请输入 /常住地 <城市名>", message, target
                    )
                else:
                    await HttpSender.sendText2Person(
                        "输入格式错误. 请输入 /常住地 <城市名>", message, author["id"]
                    )
            else:
                city = content.split(" ")[1]
                SqlCache.User.add(author["id"], city)
                send_type, target = self._reply_target(message)
                if send_type == "group":
                    await HttpSender.sendText2Group(
                        f"设置常住地: {city}", message, target
                    )
                else:
                    await HttpSender.sendText2Person(
                        f"设置常住地: {city}", message, author["id"]
                    )
