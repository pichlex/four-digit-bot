from io import StringIO
from typing import Iterable, List, Optional

from .db import CodeRepository


class CodeService:
    def __init__(self, repo: CodeRepository):
        self.repo = repo

    async def take_code(self) -> Optional[int]:
        return await self.repo.take_random_code()

    async def export_used_text(self) -> StringIO:
        codes = await self.repo.export_used()
        buffer = StringIO()
        for code in codes:
            buffer.write(f"{code:04d}\n")
        buffer.seek(0)
        return buffer

    async def import_used_codes(self, codes: Iterable[int]) -> int:
        return await self.repo.import_used(codes)

    async def clear_used(self) -> int:
        return await self.repo.clear_used()

    async def remaining(self) -> int:
        return await self.repo.get_unused_count()

    @staticmethod
    def parse_codes_from_text(text: str) -> List[int]:
        cleaned: List[int] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if not line.isdigit() or len(line) != 4:
                continue
            value = int(line)
            if 0 <= value <= 9999:
                cleaned.append(value)
        return cleaned
