from sqlalchemy.ext.asyncio import AsyncSession
from .utils import hardened_fetch_channel
from . import engine, sessionmaker
from .tables import Guild, mapper
from sqlalchemy import text
from .bot import bot

import discord

@bot.event
async def on_ready():
    async with engine.begin() as conn:
        await conn.execute(text('PRAGMA foreign_keys=ON'))
        await conn.run_sync(mapper.metadata.create_all)
    print(f"{bot.user} is ready!")

@bot.event
async def on_guild_join(guild: discord.Guild):
    logger_message = f"The bot joined the '{guild}' server"
    async with sessionmaker.begin() as session:
        # NOTE: SQLAlchemy doesn't really have typing so
        # we have to add it ourselves like this :/
        session: AsyncSession = session

        message = "Thank you for inviting me{} to the server! "
        if sql_guild := await session.get(Guild, guild.id):
            sql_guild: Guild = sql_guild
            if guild.owner:
                message = message.format(' back')
                category = await hardened_fetch_channel(sql_guild.category_id, guild, None)
                if category:
                    message += f"I currently have {category.mention} as the selected category."
                else:
                    message += (
                        "The previously set category no longer exists. "
                        "Please set a new one with the `/set category` command"
                    )
        else:
            last_message_id = None
            if guild.system_channel and guild.system_channel_flags.join_notifications:
                last_message_id = guild.system_channel.last_message_id
            sql_guild = Guild(id=guild.id, last_message_id=last_message_id)
            message = message.format('')
            session.add(sql_guild)
            message += "Please set a category to create new channels in with the `/set category` command."

    if guild.owner:
        await guild.owner.send(message)

@bot.event
async def on_member_join(member: discord.Member):
    if not member.bot:
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, member.guild.id)
            if sql_guild.listen:
                category = await hardened_fetch_channel(sql_guild.category_id, member.guild)
                await member.guild.create_text_channel(
                    member.display_name,
                    category=category,
                    overwrites={
                        member.guild.default_role: discord.PermissionOverwrite.from_pair(
                            discord.Permissions.none(),
                            discord.Permissions.all()
                        ),
                        member: discord.PermissionOverwrite(
                            view_channel=True,
                            read_message_history=True,
                            send_messages=True
                        )
                    }
                )
