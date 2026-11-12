from plugin.AiChat_d import Paths
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

        personality_file = Paths.PERSONALITY / f"{config.personality}"
        with open(personality_file, "r", encoding="utf-8") as file:
            Message.addMessage(self.openId, file.read(), MessageRole.system)

    def getHistory(self) -> list[dict[str, str]]:
        """返回可直接放入 API 请求的历史消息。

        超过 ``max_context_length`` 时先裁剪为 system prompt + 最近
        ``keep_recent - 1`` 条，再回写数据库。
        """
        self._loadSystemPrompt()

        messages: list[Message] = Message.getByOpenId(self.openId)

        if len(messages) > config.max_context_length:
            messages = self._truncate(messages)

        return [{"role": msg.role.value, "content": msg.content} for msg in messages]

    def _truncate(self, messages: list[Message]) -> list[Message]:
        """裁剪上下文并同步数据库。

        按完整的用户/助手轮次裁剪：保留的片段必须从一条 user 消息开始，
        否则会留下没有对应提问的孤立回复，污染后续上下文。

        Args:
            messages: 按时间升序排列的全部消息，第一项为 system prompt。

        Returns:
            裁剪后的消息列表，第一项为 system prompt。
        """
        system_prompt: Message = messages[0]
        keep_recent: int = max(config.keep_recent - 1, 0)
        recent: list[Message] = messages[-keep_recent:] if keep_recent else []

        # 丢弃开头不属于 user 的消息，保证从一轮对话的提问开始
        while recent and recent[0].role != MessageRole.user:
            recent = recent[1:]

        keep_ids: set[int] = {
            item.id for item in recent if item.id is not None
        }
        Message.truncateToIds(self.openId, keep_ids)
        return [system_prompt] + recent

    def clearHistory(self) -> None:
        Message.clearByOpenId(self.openId)
        Message.resetMessageCount(self.openId)
        self._loadSystemPrompt()
