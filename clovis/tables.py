from sqlalchemy import Column, BigInteger, Boolean, String, PickleType
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.decl_api import registry
from dataclasses import dataclass, field

mapper = registry()


@mapper.mapped
@dataclass
class Guild:
    default_message = (
        'Hello {}, we are glad to have you!  Thank you for applying!  '
        '**Please change your nickname to your first and last name.**'
    )

    __tablename__ = 'guilds'

    __sa_dataclass_metadata_key__ = 'sa'

    id: int = field(metadata={
        'sa': Column(BigInteger, primary_key=True)
        }
    )
    create_category_id: int = field(default=None, metadata={'sa': Column(BigInteger)})
    when2meet_category_id: int = field(default=None, metadata={'sa': Column(BigInteger)})
    when2meet: 'When2Meet' = field(default=None, metadata={'sa': Column(PickleType)})
    welcome_message: str = field(default=default_message, metadata={'sa': Column(String(4000))})
    welcome_channel_id: int = field(default=None, metadata={'sa': Column(BigInteger)})
    last_message_id: int = field(default=None, metadata={'sa': Column(BigInteger)})
    create_channel: bool = field(default=True, metadata={'sa': Column(Boolean, nullable=False)})
    message_error: bool = field(default=True, metadata={'sa': Column(Boolean, nullable=False)})
    message_missing_welcome_channel: bool = field(default=True, metadata={'sa': Column(Boolean, nullable=False)})

    @property
    def listen(self):
        return self.create_category_id and self.create_channel

    @property
    def mention_welcome(self):
        return f'<#{self.welcome_channel_id}>'

    @classmethod
    async def get_or_create(cls, session: AsyncSession, guild_id: int) -> 'Guild':
        if (guild := await session.get(cls, guild_id)):
            return guild
        guild = cls(id=guild_id)
        session.add(guild)
        return guild

from .utils import When2Meet
