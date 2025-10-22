from plugin.GlmAi_d import Paths, Types
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
    
    def addHistory(self, message: Types.ApiJson_Messages) -> None:
        self.history.append(message)
        with open(Paths.HISTORY / f"{self.openId}.yaml", "w+", encoding="utf-8") as f:
            yaml.dump(self.history, f, allow_unicode=True)

    def getHistory(self) -> list[Types.ApiJson_Messages]:
        return self.history
    
    def clearHistory(self) -> None:
        self.history = []
        with open(Paths.HISTORY / f"{self.openId}.yaml", "w+", encoding="utf-8") as f:
            yaml.dump(self.history, f, allow_unicode=True, Dumper=yaml.Dumper)