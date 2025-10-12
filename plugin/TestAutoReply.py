from plugin.PluginBase import PluginBase, MessageType, MessageData, logger
from modules import HttpSender
class TestAutoReply(PluginBase):
    messageStartWith = ""  # only use for plugins that reply message startwith /

    @property
    def messageType(self) -> MessageType.Group | MessageType.Person:
        return MessageType.Person.C2C_MESSAGE_CREATE

    @property
    def pluginName(self) -> str:
        return "Test Auto Reply"

    async def run(self, message: MessageData):
        logger.info("Running Test Auto Reply Plugin")
        content = message["d"]["content"]
        author_id = message["d"]["author"]["id"]
        reply_content = f"Auto-reply to your message: {content}"

        await HttpSender.sendText2Person(reply_content, message, author_id)