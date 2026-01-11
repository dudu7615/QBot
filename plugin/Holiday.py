from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.Holiday_d.SqlCache import Cache
from plugin.Holiday_d import RequApi
from datetime import datetime


class Holiday(PluginBase):
    usable = True
    messageStartWith = "/最近假期"

    def __init__(self):
        super().__init__()
        RequApi.checkAndUpdata()

    @property
    def messageType(self) -> MessageType.Group | MessageType.Person:
        return MessageType.Person.C2C_MESSAGE_CREATE

    @property
    def pluginName(self) -> str:
        return "Holiday"

    async def run(self, message: MessageData):
        content = message["d"]["content"]
        author = message["d"]["author"]
        
        nextHoliday =  Cache.getNextHoliday(datetime.now())
        nextDeHoliday = Cache.getNextDeHoliday(datetime.now())

        if nextHoliday is None:
            reply = "没有找到下一个假期"
        elif nextDeHoliday is None:
            reply = f"下一个假期是{nextHoliday.name}，日期为{nextHoliday.date.strftime('%Y-%m-%d')}"
        else:
            reply = (f"下一个假期是{nextHoliday.name}，日期为{nextHoliday.date.strftime('%Y-%m-%d')}\n"
                     f"下一个调休是{nextDeHoliday.name}，日期为{nextDeHoliday.date.strftime('%Y-%m-%d')}")
        await HttpSender.sendText2Person(reply, message, author["id"])
