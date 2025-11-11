import sqlite3
import asyncio
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
sqlDir = ROOT / "sql"


class Sql:
    def __init__(self):
        self.lock = asyncio.Lock()

    async def __call__(
        self, command: str, params: dict[str, str] | tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        await self.initDb()
        return await self.run(command, params)

    async def initDb(self):
            if not (ROOT / "data").exists():
                (ROOT / "data").mkdir(parents=True, exist_ok=True)
                await self.run("init")

    async def run(
        self, command: str, params: dict[str, str] | tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        async with self.lock:
            conn = sqlite3.connect(ROOT / "data" / "chat.db")
            cur = conn.cursor()

            if params is None:
                params = {}
            if not (sqlDir / f"{command}.sql").exists():
                raise FileNotFoundError(f"SQL file for command '{command}' not found.")
            with open(sqlDir / f"{command}.sql", "r", encoding="utf-8") as f:
                sqlCmd = f.read()

            cur.execute(sqlCmd, params)
            conn.commit()
            return cur.fetchall()


sql = Sql()
