from plugin.AiChat_d import Paths, Types
from plugin.AiChat_d.Config import config
from plugin.AiChat_d.Sql import Message, MessageRole, User


class PersonHistory:
    """单个用户的对话历史。

    历史以 ``user/message`` 两表落库，system prompt 作为独立的一行保存，
    截断时始终保留，避免人设丢失。
    """

    def __init__(self, openId: str):
        self.openId = openId
        self._addUserIfNotExist()

    def _addUserIfNotExist(self) -> None:
        if not User.getByOpenId(self.openId):
            User.addOrUpdate(self.openId, "unknown")

    def _loadSystemPrompt(self) -> None:
        """确保 system prompt 存在。

        以「是否已有 system 角色消息」判断，而不是依赖 messageCount，
        因为截断后 messageCount 可能与实际行数不一致。
        """
        if Message.countByRole(self.openId, MessageRole.system) > 0:
            return

        personality_file = Paths.PERSONALITY / f"{config['personality']}"
        with open(personality_file, "r", encoding="utf-8") as file:
            Message.addMessage(self.openId, file.read(), MessageRole.system)

    def addHistory(self, message: Types.ApiJson_Messages) -> None:
        Message.addMessage(
            self.openId, message["content"], MessageRole(message["role"])
        )

    def getHistory(self) -> list[Types.ApiJson_Messages]:
        """返回可直接放入 API 请求的历史消息。

        超过 ``max_context_length`` 时先裁剪为 system prompt + 最近
        ``keep_recent - 1`` 条，再回写数据库。
        """
        self._loadSystemPrompt()

        messages: list[Message] = Message.getByOpenId(self.openId)

        if len(messages) > config["max_context_length"]:
            messages = self._truncate(messages)

        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _truncate(self, messages: list[Message]) -> list[Message]:
        """裁剪上下文并同步数据库。

        Args:
            messages: 按时间升序排列的全部消息。

        Returns:
            裁剪后的消息列表，第一项为 system prompt。
        """
        system_prompt: Message = messages[0]
        keep_recent: int = max(config["keep_recent"] - 1, 0)
        recent: list[Message] = messages[-keep_recent:] if keep_recent else []
        Message.truncateTo(self.openId, config["keep_recent"])
        return [system_prompt] + recent

    def clearHistory(self) -> None:
        Message.clearByOpenId(self.openId)
        Message.resetMessageCount(self.openId)
        self._loadSystemPrompt()
