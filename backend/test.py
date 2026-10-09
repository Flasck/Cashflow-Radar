import asyncio
import io
import sys

from app.crud import list_users

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.connection import SessionFactory


async def main():
    async with SessionFactory() as s:
        print(await list_users(s))
        await s.flush()


asyncio.run(main())
