from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as maker

import argparse

parser = argparse.ArgumentParser(description='Use this to set bot settings.')
parser.add_argument('-nt', '--not-testing', action='store_false', dest='testing')
config = parser.parse_args()

engine = create_async_engine(f"sqlite+aiosqlite:///{':memory:' if config.testing else 'bot.db'}")

sessionmaker = maker(bind=engine, class_=AsyncSession)
