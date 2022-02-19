from sqlalchemy.ext.asyncio import AsyncSession
from .utils import hardened_fetch_channel
from . import sessionmaker, engine
from .tables import Guild, mapper
from sqlalchemy import text
from .bot import bot

import discord
import logging
import sys

logger = logging.getLogger(__name__)

@bot.event
async def on_ready():
    async with engine.begin() as conn:
        await conn.execute(text('PRAGMA foreign_keys=ON'))
        await conn.run_sync(mapper.metadata.create_all)
    logger.info(f"{bot.user} is ready!")

@bot.event
async def on_guild_join(guild: discord.Guild):
    if not guild.me.guild_permissions.administrator:
        message = f"The bot immediately left the '{guild}' server due to a lack of permissions."
        if guild.owner:
            await guild.owner.send(
                "Thank you for inviting me but my stay was short lived "
                "due to a lack of permissions. In order to function properly "
                "I need the admin permission. Please invite me back using this "
                "link which will give me the admin permissions: "
                + discord.utils.oauth_url(
                    bot.user.id,
                    permissions=discord.Permissions(administrator=True),
                    scopes=('bot', 'applications.commands')
                )
            )
            message += " And messaged the owner about the issue."
        await guild.leave()
        logger.info(message)
    else:
        logger_message = f"The bot joined the '{guild}' server"
        async with sessionmaker.begin() as session:
            # NOTE: SQLAlchemy doesn't really have typing so
            # we have to add it ourselves like this :/
            session: AsyncSession = session

            message = "Thank you for inviting me{} to the server! "
            if sql_guild := await session.get(Guild, guild.id):
                logger.info(f"{logger_message} which it was previously in.")
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
                logger.info(f"{logger_message}.")
                last_message_id = None
                if guild.system_channel and guild.system_channel_flags.join_notifications:
                    last_message_id = guild.system_channel.last_message_id
                sql_guild = Guild(id=guild.id, last_message_id=last_message_id)
                message = message.format('')
                session.add(sql_guild)
                message += "Please set a category to create new channels in with the `/set category` command."

        if guild.owner:
            await guild.owner.send(message)
            logger.info('The owner was notified about the bot joining.')

@bot.event
async def on_member_join(member: discord.Member):
    if not member.bot:
        failed_log = False
        logger.debug(f"{member} joined the server.")
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, member.guild.id)
            if member.guild.me.guild_permissions.administrator:
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
                    logger.info(f"{member}'s private channel was successfully created!")
            elif sql_guild.message_error:
                if member.guild.owner:
                    await member.guild.owner.send(
                        "Uh oh! Someone accidentally removed my admin permission! "
                        "I can no longer create new private channels until this permission "
                        "is restored."
                    )
                    sql_guild.message_error = False
                failed_log = True
            else:
                failed_log = True

            if failed_log:
                logger.warning(
                    f"The bot failed to make a private channel for {member} "
                    "due to permission errors."
                )

@bot.event
async def on_error(event: str, *args, **kwargs):
    logger.error(f"The following error occured with the {event} event:", exc_info=sys.exc_info())
