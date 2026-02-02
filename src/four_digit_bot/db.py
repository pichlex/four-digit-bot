import asyncio
from pathlib import Path
from typing import Iterable, List, Optional

import aiosqlite


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS codes (
    code INTEGER PRIMARY KEY,
    used INTEGER NOT NULL DEFAULT 0 CHECK(used IN (0,1))
);
"""


class CodeRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self._conn.execute(CREATE_TABLE_SQL)
        await self._seed_codes()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _seed_codes(self):
        assert self._conn is not None
        cursor = await self._conn.execute("SELECT COUNT(*) AS c FROM codes;")
        row = await cursor.fetchone()
        await cursor.close()
        if row["c"] == 10000:
            return

        # Insert missing codes in a transaction
        await self._conn.execute("BEGIN IMMEDIATE;")
        existing = set()
        cursor = await self._conn.execute("SELECT code FROM codes;")
        async for r in cursor:
            existing.add(r["code"])
        await cursor.close()

        missing = [i for i in range(10000) if i not in existing]
        await self._conn.executemany("INSERT OR IGNORE INTO codes(code, used) VALUES (?, 0);",
                                     ((c,) for c in missing))
        await self._conn.commit()

    async def get_unused_count(self) -> int:
        assert self._conn is not None
        cursor = await self._conn.execute("SELECT COUNT(*) AS c FROM codes WHERE used=0;")
        row = await cursor.fetchone()
        await cursor.close()
        return int(row["c"])

    async def take_random_code(self) -> Optional[int]:
        """Atomically pick an unused code, mark as used, and return it."""
        assert self._conn is not None
        async with self._lock:
            await self._conn.execute("BEGIN IMMEDIATE;")
            cursor = await self._conn.execute(
                """
                UPDATE codes
                SET used = 1
                WHERE code = (
                    SELECT code FROM codes WHERE used = 0 ORDER BY RANDOM() LIMIT 1
                )
                RETURNING code;
                """
            )
            row = await cursor.fetchone()
            await cursor.close()
            await self._conn.commit()
            if row is None:
                return None
            return int(row["code"])

    async def export_used(self) -> List[int]:
        assert self._conn is not None
        cursor = await self._conn.execute("SELECT code FROM codes WHERE used=1 ORDER BY code;")
        codes = [int(row["code"]) for row in await cursor.fetchall()]
        await cursor.close()
        return codes

    async def import_used(self, codes: Iterable[int]) -> int:
        """Mark provided codes as used. Returns number of codes newly marked."""
        assert self._conn is not None
        unique_codes = {int(c) for c in codes if 0 <= int(c) <= 9999}
        if not unique_codes:
            return 0
        async with self._lock:
            await self._conn.execute("BEGIN IMMEDIATE;")
            cursor = await self._conn.executemany(
                "UPDATE codes SET used = 1 WHERE code = ? AND used = 0;",
                ((code,) for code in unique_codes)
            )
            await self._conn.commit()
            return cursor.rowcount

    async def clear_used(self) -> int:
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute("UPDATE codes SET used = 0 WHERE used = 1;")
            await self._conn.commit()
            return cursor.rowcount


async def create_repository(db_path: Path) -> CodeRepository:
    repo = CodeRepository(db_path)
    await repo.connect()
    return repo
