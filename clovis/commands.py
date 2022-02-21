from datetime import datetime, timedelta
from discord.commands import Option
from discord.ext import commands
from bs4 import BeautifulSoup
from . import sessionmaker
from .tables import Guild
from dateutil import tz
from .utils import (
    autocomplete_timezones,
    hardened_fetch_channel,
    When2MeetPaginator,
    TimeZoneConverter,
    HTMLChangeError,
    autocomplete
)

import aiohttp
import discord
import logging

logger = logging.getLogger(__name__)


class CommandsCog(commands.Cog):
    set_commands = discord.SlashCommandGroup(
        'set',
        'Commands used to configure various aspects of the bot.'
    )

    get_commands = discord.SlashCommandGroup(
        'get',
        "Commands used to get various information about the bot."
    )

    start_commands = discord.SlashCommandGroup(
        'start',
        "Commands used to start some automated action of the bot."
    )

    stop_commands = discord.SlashCommandGroup(
        'stop',
        "Commands used to stop some automated action of the bot."
    )

    create_commands = discord.SlashCommandGroup(
        'create',
        "Commands used to create something."
    )

    @set_commands.command(
        name='category',
        description="Use this command to set the category in which new channels will be created in.",
        options=[
            Option(
                discord.CategoryChannel,
                name='channel',
                description="The category to create new channels in."
            )
        ]

    )
    @commands.has_guild_permissions(administrator=True)
    async def set_category(self, ctx: discord.ApplicationContext, channel: discord.CategoryChannel):
        # NOTE: Must have the admin permission to be able to create private channels
        if ctx.me.guild_permissions.administrator:
            async with sessionmaker.begin() as session:
                sql_guild = await Guild.get_or_create(session, ctx.guild_id)
                sql_guild.category_id = channel.id
                sql_guild.create_channel = True
            await ctx.respond(f"{channel.mention} has been set as the new category to create private channels in.")
            logger.info(f"{ctx.author} used the /set category command to set the category to {channel}.")
        else:
            await ctx.respond(
                "Uh oh! I don't have the admin permission! "
                "Please give me the admin permission in order to "
                "set a category to create private channels in."
            )
            logger.warning(
                f"{ctx.author} tried to use the /set category command "
                "but the bot did not have the admin permission."
            )

    @get_commands.command(
        name='category',
        description="Use this command find out which category is currently being used to create new channels."
    )
    @commands.has_guild_permissions(administrator=True)
    async def get_category(self, ctx: discord.ApplicationContext):
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, ctx.guild_id)
            if category := await hardened_fetch_channel(
                sql_guild.category_id, ctx.guild, default=None
            ):
                message = f'The current category set is {category.mention}.'
            else:
                if sql_guild.category_id:
                    message = (
                        "The previously set category channel was deleted, "
                        "please set a new one with the `/set category` command."
                    )
                else:
                    message = (
                        "This server does not currently have category, "
                        "set one using `/set category` command."
                    )
                sql_guild.category_id = None
        await ctx.respond(message)
        logger.info(f"{ctx.author} used the /get category command.")

    @start_commands.command(
        name='listening',
        description="Use this command to make me start listening for new members joining."
    )
    @commands.has_guild_permissions(administrator=True)
    async def start_listening(self, ctx: discord.ApplicationContext):
        await self.listening(
            ctx=ctx,
            action=True,
            message="I will now start creating new text channels when new members join.",
            alt_message="I am already listening for messages!"
        )
        logger.info(f"{ctx.author} used the /start listening command.")

    @stop_commands.command(
        name='listening',
        description="Use this command to make me stop listening for new members joining."
    )
    @commands.has_guild_permissions(administrator=True)
    async def stop_listening(self, ctx: discord.ApplicationContext):
        await self.listening(
            ctx=ctx,
            action=False,
            message="I will no longer create new text channels when new members join.",
            alt_message="I am already not listening for messages!"
        )
        logger.info(f"{ctx.author} used the /stop listening command.")

    async def listening(
        self,
        ctx: discord.ApplicationContext,
        action: bool,
        message: str,
        alt_message: str
    ):
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, ctx.guild_id)
            if action is sql_guild.create_channel:
                await ctx.respond(alt_message)
            else:
                sql_guild.create_channel = action
                await ctx.respond(message)

    @create_commands.command(
        name='when2meet',
        description="Use this command to create a when2meet.",
        options=[
            Option(
                str,
                name="event-name",
                description="Use this to set the name of the event.",
            ),
            Option(
                TimeZoneConverter,
                name='timezone',
                description=(
                    'Use this to set the timezone, '
                    'by default the timezone is Pacific Standard Time.'
                ),
                autocomplete=autocomplete_timezones if autocomplete else None,
                required=False
            )
        ]
    )
    async def create_when2meet(
        self,
        ctx: discord.ApplicationContext,
        event_name: str,
        timezone: str = None
    ):
        # TODO: If you want implement DaysOfWeek Too
        if timezone is None:
            timezone = 'America/Los_Angeles'

        paginator = When2MeetPaginator(
            [
                '📅 Select One or Multiple Dates:',
                '⏰ Select a Start and End Time:'
            ],
            tz.gettz(timezone)
        )
        await paginator.respond(ctx.interaction)

        await paginator.ready.wait()

        payload = paginator.create_payload(event_name, timezone)
        async with aiohttp.request(
            'POST',
            'https://www.when2meet.com/SaveNewEvent.php',
            data=payload
        ) as resp:
            resp.raise_for_status()
            soup = BeautifulSoup(await resp.text(), 'html.parser')
        try:
            url = f"https://www.when2meet.com/{soup.body['onload'].split('/')[-1][:-1]}"
        except (KeyError, IndexError) as error:
            raise HTMLChangeError(
                'The when2meet HTML code has changed! '
                'You need to update this portion of code '
                'to be able to analyze the new HTML.'
            ) from error

        view = discord.ui.View(discord.ui.Button(label='When2Meet', url=url))
        # embed = discord.Embed(title=f"{event_name} When2Meet", url=url)
        embed = discord.Embed()
        embed.add_field(name='Event Name', value=event_name)
        embed.add_field(
            name='Earliest Time',
            value=format(datetime.min.replace(hour=payload['NoEarlierThan']), '%I %p'),
            # inline=False
        )
        embed.add_field(
            name='Latest Time',
            value=format(datetime.min.replace(hour=payload['NoLaterThan']), '%I %p')
        )
        if len(paginator.selected_dates) > 1:
            max_format_code = '%A'
            max_date = max(paginator.selected_dates)
            min_date = min(paginator.selected_dates)
            if max_date - min_date >= timedelta(days=7):
                max_format_code = '%A %m/%d'
            embed.add_field(
                name='Date Range',
                value=f"{format(min_date, '%A')} - {format(max_date, max_format_code)}"
            )
        else:
            embed.add_field(
                name='Date',
                value=format(list(paginator.selected_dates)[0], '%A %m/%d'),
            )
        embed.add_field(name='Time Zone', value=timezone)
        await ctx.interaction.edit_original_message(content=None, embed=embed, view=view)

    @create_when2meet.error
    async def handle_create_when2meet_error(
        self,
        ctx: discord.ApplicationContext,
        error: discord.ApplicationCommandInvokeError
    ):
        if isinstance(error.original, commands.BadArgument):
            await ctx.respond(
                f"You selected an invalid timezone: '{error.original.bad_argument}'. "
                "Please select a valid timezone from the given options."
            )

    @commands.slash_command(
        description="Use this command to get my source code!"
    )
    async def source(self, ctx: discord.ApplicationContext):
        # TODO: Add link button to source command
        await ctx.respond("You can find my source code here: https://github.com/Ahsoka/clovis")
        logger.info(f"{ctx.author} used the /source command.")

    @commands.Cog.listener()
    async def on_application_command_error(
        self,
        ctx: discord.ApplicationContext,
        error: discord.ApplicationCommandInvokeError
    ):
        if isinstance(error.original, commands.MissingPermissions):
            logger.info(
                f"{ctx.author} tried to use the /{ctx.command.qualified_name} "
                "even though they don't have permission to do so."
            )
            await ctx.respond("You do not have permission to use this command.")
        elif isinstance(error.original, commands.NoPrivateMessage):
            logger.info(
                f"{ctx.author} tried to use the /{ctx.command.qualified_name} in a DM."
            )
            await ctx.respond("This command is not available in DM messages.")
        elif isinstance(error.original, commands.BadArgument):
            # NOTE: We are assuming that if this happens the individual command will have
            # logic to handle this situation.
            pass
        else:
            # NOTE: In this case you may want to add ping_dev function like with the bdaybot
            logger.error("The following error occured with the bot:", exc_info=error)
            await ctx.respond("Uh oh! Something went wrong on our end. Please try again later!")
