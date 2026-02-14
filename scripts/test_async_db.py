import asyncio
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.api.models import Memory

async def main():
    async with AsyncSessionLocal() as s:
        # Trivial roundtrip
        res = await s.execute(select(Memory).limit(1))
        print("Async OK:", res.first() is None or "row found")

if __name__ == "__main__":
    asyncio.run(main())
