from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine('sqlite+aiosqlite:///:memory:')
