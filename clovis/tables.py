from sqlalchemy import Column, BigInteger, Boolean, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.decl_api import registry
from dataclasses import dataclass, field

mapper = registry()


@mapper.mapped
@dataclass
class Guild:
    __tablename__ = 'guilds'

    __sa_dataclass_metadata_key__ = 'sa'

    id: int = field(metadata={
        'sa': Column(BigInteger, primary_key=True)
        }
    )
    create_category_id: int = field(default=None, metadata={'sa': Column(BigInteger)})
    default_message: str = field(
        default=(
            'Hello {}, we are glad to have you!  Thank you for applying!  '
            '**Please change your nickname to your first and last name.**'
        ),
        metadata={'sa': Column(String(4000))}
    )
    welcome_channel_id: int = field(default=None, metadata={'sa': Column(BigInteger)})
    last_message_id: int = field(default=None, metadata={'sa': Column(BigInteger)})
    create_channel: bool = field(default=True, metadata={'sa': Column(Boolean, nullable=False)})
    message_error: bool = field(default=True, metadata={'sa': Column(Boolean, nullable=False)})
    message_missing_welcome_channel: bool = field(default=True, metadata={'sa': Column(Boolean, nullable=False)})

    @property
    def listen(self):
        return self.create_category_id and self.create_channel

    @classmethod
    async def get_or_create(cls, session: AsyncSession, guild_id: int) -> 'Guild':
        if (guild := await session.get(cls, guild_id)):
            return guild
        guild = cls(id=guild_id)
        session.add(guild)
        return guild
