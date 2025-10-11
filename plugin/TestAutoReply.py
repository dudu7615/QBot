from plugin.PluginBase import PluginBase, MessageType, MessageData, client, logger

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

        # 假设有一个发送消息的API端点
        api_url = "http://example.com/api/send_message"
        payload = {
            "recipient_id": author_id,
            "message": reply_content
        }

        try:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            logger.info(f"Sent auto-reply to {author_id}")
        except Exception as e:
            logger.error(f"Failed to send auto-reply: {e}")