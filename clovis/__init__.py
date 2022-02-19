from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as maker

engine = create_async_engine('sqlite+aiosqlite:///:memory:')

sessionmaker = maker(bind=engine, class_=AsyncSession)
