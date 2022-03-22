from sqlalchemy.ext.asyncio import AsyncSession
from .utils import hardened_fetch_channel
from . import sessionmaker, engine
from .tables import Guild, mapper
from sqlalchemy import text
from typing import Dict
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
                    category = await hardened_fetch_channel(sql_guild.create_category_id, guild, None)
                    if category:
                        message += f"I currently have {category.mention} as the selected category."
                    else:
                        message += (
                            "The previously set category no longer exists. "
                            "Please set a new one with the `/set category` command."
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
                    category = await hardened_fetch_channel(sql_guild.create_category_id, member.guild)
                    channel = await member.guild.create_text_channel(
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
                    placeholders = [member.mention]
                    if sql_guild.welcome_channel_id:
                        placeholders.append(sql_guild.mention_welcome)

                    await channel.send(sql_guild.welcome_message.format(*placeholders))
                    logger.info(f"Successfully sent welcome message in {member}'s private channel.")

                    if (
                        not sql_guild.welcome_channel_id
                        and sql_guild.message_missing_welcome_channel
                        and member.guild.owner
                    ):
                        logger.warning(f'There is no welcome channel set in {member.guild}.')
                        await member.guild.owner.send(
                            "There is currently no welcome channel set. "
                            "Please use `/set welcome channel` command "
                            "to set a welcome channel."
                        )
                        logger.info('Successfully notified the server owner about the issue.')
                        sql_guild.message_missing_welcome_channel = False

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
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    if after.is_bot_managed() and after in after.guild.me.roles:
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, after.guild.id)
            if not after.permissions.administrator and sql_guild.message_error:
                logger.warning("Someone accidentally removed the bot's admin permission.")
                if after.guild.owner:
                    await after.guild.owner.send(
                        "Uh oh! Someone accidentally removed my admin permission! "
                        "I can no longer create new private channels until this permission "
                        "is restored."
                    )
                    sql_guild.message_error = False
                    logger.info("The owner was notified about the missing permission.")
            elif not before.permissions.administrator and after.permissions.administrator:
                logger.info("The bot's admin permission has been restored.")
                sql_guild.message_error = True
                if after.guild.owner:
                    await after.guild.owner.send(
                        "My admin permission has been restored and I will now continue to "
                        "create new private channels."
                    )
                    logger.info("The owner was notified about the correction to the bot's role.")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    async with sessionmaker.begin() as session:
        sql_guild = await Guild.get_or_create(session, after.guild.id)
        if not after.bot and before.nick != after.nick and sql_guild.create_category_id:
            logger.debug(f"{after} changed their nickname from {before.nick!r} to {after.nick!r}.")
            category = await hardened_fetch_channel(sql_guild.create_category_id, before.guild)
            nonadmins = set()
            admins = set()
            user_channels: Dict[int, discord.TextChannel] = {}
            try:
                for num, text_channel in enumerate(category.text_channels):
                    users = set(map(lambda member: member.id, text_channel.members))
                    admins |= nonadmins & users
                    persons = users - admins
                    nonadmins |= persons
                    nonadmins -= admins
                    if num == 1:
                        nonadmins_temp = list(nonadmins)
                        channel = lambda person_id: next(
                            filter(
                                lambda channel: person_id in map(
                                    lambda member: member.id, channel.members
                                ),
                                category.text_channels
                            )
                        )
                        user_channels[nonadmins_temp[0]] = channel(nonadmins_temp[0])
                        user_channels[nonadmins_temp[1]] = channel(nonadmins_temp[1])
                    elif num > 1:
                        if len(persons) > 1:
                            raise ValueError(
                                f"Multiple people detected in the private text channel: {text_channel}."
                            )
                        elif len(persons) == 0:
                            raise ValueError(
                                f"No one detected in the private text channel: {text_channel}."
                            )
                        user_channels[persons.pop()] = text_channel

                await user_channels[after.id].edit(
                    name=after.nick if after.nick else after.name,
                    reason="Updating channel to the user's real name (as inferred from their nickname)."
                )
                logger.info(f"Successfully updated the name of {after}'s private channel to {after.nick!r}")
            except (ValueError, KeyError) as error:
                logger.warning(
                    f"Failed to locate {after}'s private channel, "
                    "it may be because they are an admin and do not have one.",
                    exc_info=error
                )

@bot.event
async def on_error(event: str, *args, **kwargs):
    logger.error(f"The following error occured with the {event} event:", exc_info=sys.exc_info())
