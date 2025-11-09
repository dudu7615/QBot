import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
sqlDir = ROOT / "sql"
class Sql:
    # def __init__(self):
    #     self.conn = sqlite3.connect(ROOT / "data" / "chat.db")
    #     self.cur = self.conn.cursor()

    # def __del__(self):
    #     self.conn.close()

    def __enter__(self):
        self.conn = sqlite3.connect(ROOT / "data" / "chat.db")
        self.cur = self.conn.cursor()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.conn.close()

    def __call__(self, command: str, params: dict[str,str] | tuple[Any,...] | None = None) -> list[tuple[Any,...]]:
        return self.run(command, params)

    def run(self, command: str, params: dict[str,str] | tuple[Any,...] | None = None) -> list[tuple[Any,...]]:
        if params is None:
            params = {}
        if not (sqlDir / f"{command}.sql").exists():
            raise FileNotFoundError(f"SQL file for command '{command}' not found.")
        with open(sqlDir / f"{command}.sql", "r", encoding="utf-8") as f:
            sqlCmd = f.read()
        self.cur.execute(sqlCmd, params)
        self.conn.commit()
        return self.cur.fetchall()

if __name__ == "__main__": 
    sql = Sql()
    ...