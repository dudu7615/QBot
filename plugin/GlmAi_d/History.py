from plugin.GlmAi_d import Paths, Types
import yaml

class PersonHistory:
    def __init__(self, openId: str):
        self.openId = openId
        self.history: list[Types.ApiJson_Messages] = yaml.load(
            open(Paths.HISTORY / f"{self.openId}.yaml", "r+", encoding="utf-8"),
            Loader=yaml.FullLoader,
        )
    
    def addHistory(self, message: Types.ApiJson_Messages) -> None:
        self.history.append(message)
        yaml.dump(
            self.history,
            open(Paths.HISTORY / f"{self.openId}.yaml", "w+", encoding="utf-8"),
            Dumper=yaml.Dumper,
        )

    def getHistory(self) -> list[Types.ApiJson_Messages]:
        return self.history
    
    def clearHistory(self) -> None:
        self.history = []
        yaml.dump(
            self.history,
            open(Paths.HISTORY / f"{self.openId}.yaml", "w+", encoding="utf-8"),
            Dumper=yaml.Dumper,
        )