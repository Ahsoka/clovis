from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession
from .utils import hardened_fetch_channel
from . import sessionmaker, engine
from .tables import Guild, mapper
from datetime import datetime
from sqlalchemy import text
from .bot import bot

import discord
import logging
import sys

logger = logging.getLogger(__name__)

@bot.event
async def on_ready():
    # NOTE: There is an issue with the database being accessed before the database has been created.
    # This only happens whenever one of the listener functions try to retrieve data before the
    # database has been created. This is very rare occurences and is most likely to occur in testing
    # mode. Could solve this using an asyncio.Event however I would need to add it every spot where the
    # database might be accessed before the database has been created. Might be worth looking into if
    # this can be done implicitly, perhaps might be worth creating an issue on SQLAlchemy.
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

            try:
                admins = None
                category = await hardened_fetch_channel(sql_guild.create_category_id, before.guild)
                for text_channel in category.text_channels:
                    if admins is None:
                        admins = set(
                            map(
                                lambda member: member.id,
                                filter(
                                    lambda member: member.guild_permissions.administrator,
                                    text_channel.members
                                )
                            )
                        )
                    person = set(map(lambda member: member.id, text_channel.members)) - admins
                    if len(person) > 1:
                        raise ValueError(
                            f"Multiple people detected in the private text channel: {text_channel}."
                        )
                    elif len(person) == 0:
                        raise ValueError(
                            f"No one detected in the private text channel: {text_channel}."
                        )

                    if person.pop() == after.id:
                        await text_channel.edit(
                            name=after.nick if after.nick else after.name,
                            reason="Updating channel to the user's real name (as inferred from their nickname)."
                        )
                        logger.info(f"Successfully updated the name of {after}'s private channel to {after.nick!r}")
                        break
                else:
                    raise ValueError(f"Failed to locate {after}'s private channel.")
            except ValueError as error:
                logger.warning(
                    f"Failed to locate {after}'s private channel, "
                    "it may be because they are an admin and do not have one.",
                    exc_info=error
                )

@bot.event
async def on_guild_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    if isinstance(after, discord.TextChannel) and after.category and before.category != after.category:
        logger.debug(f'The {after} channel was updated in {after.guild}!')
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, after.guild.id)
            if sql_guild.when2meet_category_id:
                category = await hardened_fetch_channel(sql_guild.when2meet_category_id, after.guild, None)
                if category:
                    logger.info(
                        f'Detected the when2meet_category_id as a valid category '
                        f'in the {after.guild} server.'
                    )
                    if after.category.id == sql_guild.when2meet_category_id:
                        when2meet = sql_guild.when2meet.format(after.name.replace('-', ' ').title())
                        when2meet.possible_dates = list(
                            map(
                                lambda date: datetime.today() + relativedelta(
                                    weekday=date.weekday()
                                ),
                                sql_guild.when2meet.possible_dates
                            )
                        )
                        url = await when2meet.create_event()
                        logger.info(
                            f'Successfully created the when2meet for the #{after} channel.'
                        )
                        await after.send(
                            embed=when2meet.create_embed(),
                            view=when2meet.create_view(url)
                        )
                        logger.info(
                            f'Successfully sent message for the when2meet in the #{after} channel.'
                        )
                else:
                    message = (
                        "Detected the when2meet_category_id as an "
                        f"invalid category in the {after.guild} server."
                    )
                    sql_guild.when2meet_category_id = None
                    if after.guild.owner:
                        await after.guild.owner.send(
                            'The category for automatically creating when2meets '
                            'has been deleted! Please set a new one with the `/set when2meet '
                            'category` command.'
                        )
                        message += " Notified the owner about the issue."
                    logger.warning(message)

@bot.event
async def on_error(event: str, *args, **kwargs):
    logger.error(f"The following error occured with the {event} event:", exc_info=sys.exc_info())
