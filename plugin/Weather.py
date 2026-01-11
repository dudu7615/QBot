from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.Weather_d import SqlCache, GetWeather


class Weather(PluginBase):
    usable = True
    messageStartWith = ["/今日天气", "/天气预报", "/常住地"]

    @property
    def messageType(self) -> MessageType.Group | MessageType.Person:
        return MessageType.Person.C2C_MESSAGE_CREATE

    @property
    def pluginName(self) -> str:
        return "Weather"
    
    async def run(self, message: MessageData):
        content = message["d"]["content"]
        author = message["d"]["author"]
        if content.startswith("/今日天气"):
            if len(content.split(" ")) == 2:
                city = content.split(" ")[1]
                weather = await GetWeather.getTodayWeather(city)
            elif len(content.split(" ")) == 1:
                city = SqlCache.User.get(author["id"])
                if city:
                    weather = await GetWeather.getTodayWeather(city)
                else:
                    weather = "请先设置常住地"
            else:
                weather = "输入格式错误. 请输入 /今日天气 <城市名(若已设置常住地, 可省略)>"
            await HttpSender.sendText2Person(weather, message, author["id"])
