from plugin.GlmAi_d import Paths, Types
from plugin.GlmAi_d.Config import config
from plugin.GlmAi_d.Sql import Sql


class PersonHistory:
    def __init__(self, openId: str):
        self.openId = openId

        with Sql() as db:
            if not db("message/get", {"open_id": self.openId}):
                self._loadSystemPrompt(db)

    def _loadSystemPrompt(self, db: Sql) -> None:
        with open(
            Paths.PERSONALITY / f"{config['personality']}", "r", encoding="utf-8"
        ) as f:
            systemPrompt: Types.ApiJson_Messages = {
                "role": "system",
                "content": f.read(),
            }

            db(
                "message/add",
                {
                    "open_id": self.openId,
                    "role": systemPrompt["role"],
                    "content": systemPrompt["content"],
                },
            )

    def addHistory(self, message: Types.ApiJson_Messages) -> None:
        with Sql() as db:
            db(
                "message/add",
                {
                    "open_id": self.openId,
                    "role": message["role"],
                    "content": message["content"],
                },
            )

    def getHistory(self) -> list[Types.ApiJson_Messages]:
        with Sql() as db:
            return [
                {"role": role, "content": content}
                for role, content in db("message/get", {"open_id": self.openId})
            ]

    def clearHistory(self) -> None:
        with Sql() as db:
            db("message/clear", {"open_id": self.openId})
            self._loadSystemPrompt(db)
