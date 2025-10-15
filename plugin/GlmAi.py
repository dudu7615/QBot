from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.GlmAi_d import RequApi

class GlmAi(PluginBase):
    usable = True

    @property
    def messageType(self) -> MessageType.Group | MessageType.Person:
        return MessageType.Person.C2C_MESSAGE_CREATE

    @property
    def pluginName(self) -> str:
        return "GlmAi"
    
    async def run(self, message: MessageData):
        content = message["d"]["content"]
        author = message["d"]["author"]
        reply = await RequApi.RequApi(content, author["id"])
        await HttpSender.sendText2Person(reply, message, author["id"])