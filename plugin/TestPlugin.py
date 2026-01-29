from .PluginBase import PluginBase, MessageType, MessageData
from modules.Logger import logger


class TestPlugin(PluginBase):
    usable = False

    @property
    def messageType(self) -> MessageType.Group | MessageType.Person:
        return MessageType.Person.C2C_MESSAGE_CREATE

    @property
    def pluginName(self) -> str:
        return "Test Plugin"

    async def run(self, message: MessageData):
        logger.info("Running Test Plugin")
        return {"message": "This is a test plugin"}
