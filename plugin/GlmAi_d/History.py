from plugin.GlmAi_d import Paths, Types
from plugin.GlmAi_d.Config import config
import yaml

class PersonHistory:
    def __init__(self, openId: str):
        self.openId = openId
        self.path = Paths.HISTORY / f"{self.openId}.yaml"
        if not self.path.exists():
            with open(Paths.HISTORY / f"{self.openId}.yaml", "w+", encoding="utf-8") as f:
                yaml.dump(self.history, f, allow_unicode=True)
        else:
            with open(Paths.HISTORY / f"{self.openId}.yaml", "r+", encoding="utf-8") as f:
                self.history: list[Types.ApiJson_Messages] = yaml.load(f, Loader=yaml.FullLoader)

        if not self.history:
            self.history = []
            self.loadSystemPrompt()

    def loadSystemPrompt(self) -> None:
        with open(Paths.PERSONALITY / f"{config['personality']}", "r", encoding="utf-8") as f:
            systemPrompt: Types.ApiJson_Messages = {
                "role": "system",
                "content": f.read()
            }
            self.history.insert(0, systemPrompt)

    def addHistory(self, message: Types.ApiJson_Messages) -> None:
        self.history.append(message)
        with open(Paths.HISTORY / f"{self.openId}.yaml", "w+", encoding="utf-8") as f:
            yaml.dump(self.history, f, allow_unicode=True)

    def getHistory(self) -> list[Types.ApiJson_Messages]:
        return self.history
    
    def clearHistory(self) -> None:
        self.history = []
        self.loadSystemPrompt()
        with open(Paths.HISTORY / f"{self.openId}.yaml", "w+", encoding="utf-8") as f:
            yaml.dump(self.history, f, allow_unicode=True, Dumper=yaml.Dumper)