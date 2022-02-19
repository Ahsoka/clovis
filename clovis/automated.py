from sqlalchemy import text
from .tables import mapper
from .bot import bot
from . import engine

@bot.event
async def on_ready():
    async with engine.begin() as conn:
        await conn.execute(text('PRAGMA foreign_keys=ON'))
        await conn.run_sync(mapper.metadata.create_all)
    print(f"{bot.user} is ready!")
