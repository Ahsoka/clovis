from discord.commands import Option
from discord.ext import commands
from . import sessionmaker
from .tables import Guild
from dateutil import tz
from .utils import (
    autocomplete_timezones,
    hardened_fetch_channel,
    When2MeetPaginator,
    TimeZoneConverter,
    WelcomeModal,
    autocomplete
)

import discord
import logging

logger = logging.getLogger(__name__)


class CommandsCog(commands.Cog):
    set_commands = discord.SlashCommandGroup(
        'set',
        'Commands used to configure various aspects of the bot.'
    )
    welcome_set_command = set_commands.create_subgroup(
        'welcome',
        'Command used for setting the welcome channel.'
    )
    when2meet_command = set_commands.create_subgroup(
        'when2meet',
        'Command used to configure the auto when2meet feature.'
    )

    get_commands = discord.SlashCommandGroup(
        'get',
        "Commands used to get various information about the bot."
    )
    welcome_get_command = get_commands.create_subgroup(
        'welcome',
        'Command used for getting the current welcome channel.'
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
                sql_guild.create_category_id = channel.id
                # NOTE: Might want to be careful here of automatically setting the bot to listen.
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
                sql_guild.create_category_id, ctx.guild, default=None
            ):
                message = f'The current category set is {category.mention}.'
            else:
                if sql_guild.create_category_id:
                    message = (
                        "The previously set category channel was deleted, "
                        "please set a new one with the `/set category` command."
                    )
                else:
                    message = (
                        "This server does not currently have category, "
                        "set one using `/set category` command."
                    )
                sql_guild.create_category_id = None
        await ctx.respond(message)
        logger.info(f"{ctx.author} used the /get category command.")

    @welcome_set_command.command(
        name='channel',
        description="Use this command to set the welcome channel.",
        options=[
            Option(
                discord.TextChannel,
                name='channel',
                description="The desired welcome channel."
            )
        ]
    )
    @commands.has_guild_permissions(administrator=True)
    async def set_welcome_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, ctx.guild_id)
            sql_guild.welcome_channel_id = channel.id
            if sql_guild.welcome_message == Guild.default_message:
                sql_guild.welcome_message += (
                    '  Additionally, please review the {} channel, '
                    'so we can set up the next steps in the application process.'
                )
        await ctx.respond(f"{channel.mention} has been set as the new welcome channel.")
        logger.info(f"{ctx.author} used the /set welcome channel command to set the welcome channel to {channel}.")

    @welcome_get_command.command(
        name='channel',
        description="Use this command to find out the current welcome channel."
    )
    @commands.guild_only()
    async def get_welcome_channel(self, ctx: discord.ApplicationContext):
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, ctx.guild_id)
            if sql_guild.welcome_channel_id:
                channel = await hardened_fetch_channel(sql_guild.welcome_channel_id, ctx.guild, None)
                if channel:
                    await ctx.respond(f"{channel.mention} is currently set as the welcome channel.")
                else:
                    sql_guild.welcome_channel_id = None
                    await ctx.respond(
                        "The previously set welcome channel has been deleted! "
                        "Please set a new one with the `/set welcome channel` command."
                    )
            else:
                await ctx.respond(
                    "There is currently no welcome channel. "
                    "Set one using the `/set welcome channel` command."
                )
        logger.info(f"{ctx.author} used the /get welcome channel command.")

    @welcome_set_command.command(
        name='message',
        description="Use this command to set the welcome message in each newly created channel."
    )
    @commands.has_guild_permissions(administrator=True)
    async def set_welcome_message(self, ctx: discord.ApplicationContext):
        # TODO: Disable Edit Message button on timeout.
        logger.info(f"{ctx.author} used the /set welcome message command. ID: {id(ctx)}")
        async def edit_button_callback(interaction: discord.Interaction):
            logger.info(f'{interaction.user} clicked the Edit Message button. ID: {id(ctx)}')
            async with sessionmaker.begin() as session:
                sql_guild = await Guild.get_or_create(session, interaction.guild_id)
                modal = WelcomeModal(
                    ctx,
                    'Welcome Message',
                    'Message',
                    edit_button.og_message,
                    sql_guild.welcome_message
                )
                await interaction.response.send_modal(modal)
            logger.info(f'Successfully sent the modal. ID: {id(ctx)}')

        edit_button = discord.ui.Button(
            style=discord.ButtonStyle.blurple, label='Edit Message'
        )
        edit_button.og_message = (
            "The following is a sample welcome message:\n"
            "> {}\n\n"
            'Please click the "Edit Message" button to edit the message.\n\n'
            "Note there can be up to two placeholders in the message, "
            "one to mention the person's name and another to mention the welcome channel. "
            "These placeholders are denoted by curly braces {{}} "
            "where the first pair of curly braces is the person's mention "
            "and second pair of curly braces is for the welcome channel."
        )
        edit_button.callback = edit_button_callback

        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, ctx.guild_id)
            args = [ctx.bot.user.mention]
            if sql_guild.welcome_channel_id:
                args.append(sql_guild.mention_welcome)

            await ctx.respond(
                edit_button.og_message.format(sql_guild.welcome_message.format(*args)),
                view=discord.ui.View(edit_button, timeout=None)
            )

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
            alt_message="I am already listening for new members joining!"
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
            alt_message="I am not currently listening for new members joining."
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
                '???? Select One or Multiple Dates:',
                '??? Select a Start and End Time:'
            ],
            tz.gettz(timezone)
        )

        logger.info(f"{ctx.author} used the /create when2meet command. ID: {id(paginator)}")

        await paginator.respond(ctx.interaction)
        await paginator.ready.wait()

        when2meet = paginator.create_when2meet(event_name, timezone)
        url = await when2meet.create_event()
        logger.info(f"The when2meet was successfully created: ID {id(paginator)}")

        await ctx.interaction.edit_original_message(
            content=None,
            embed=when2meet.create_embed(),
            view=when2meet.create_view(url)
        )

    @when2meet_command.command(
        name='category',
        description="Use this command to create a when2meet.",
        options=[
            Option(
                str,
                name='template-event-name',
                description=(
                    "Use this to set the template event name, "
                    "use {} as placeholder for the person's name."
                )
            ),
            Option(
                discord.CategoryChannel,
                name="category",
                description="Use this to set the category for where automatic when2meets will be created."
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
    async def set_when2meet_category(
        self,
        ctx: discord.ApplicationContext,
        event_name: str,
        category: discord.CategoryChannel,
        timezone: str = None
    ):
        try:
            # NOTE: Test to see if their message is valid.
            event_name.format('')

            if timezone is None:
                timezone = 'America/Los_Angeles'

            paginator = When2MeetPaginator(
                [
                    '???? Select One or Multiple Dates:',
                    '??? Select a Start and End Time:'
                ],
                tz.gettz(timezone)
            )
            logger.info(f"{ctx.author} used the /set when2meet category command. ID: {id(paginator)}")
            await paginator.respond(ctx.interaction)
            await paginator.ready.wait()

            when2meet = paginator.create_when2meet(event_name, timezone)
            async with sessionmaker.begin() as session:
                sql_guild = await Guild.get_or_create(session, ctx.guild_id)
                sql_guild.when2meet_category_id = category.id
                sql_guild.when2meet = when2meet

            logger.info(
                f'{ctx.author} successfully set the when2meet and category id in the DB. ID: {id(paginator)}'
            )

            await ctx.interaction.edit_original_message(
                content=(
                    "The following is a sample of a when2meet that will be generated "
                    f"when you move a channel into the {category.mention} category."
                ),
                embed=when2meet.format(ctx.bot.user.name).create_embed(),
                view=None
            )
        except (IndexError, ValueError, KeyError) as error:
            logger.warning(
                f'{ctx.author} failed to use the /set when2meet category command '
                f'because they used the invalid template-event-name {event_name!r}.',
                exc_info=error
            )
            await ctx.respond(
                'Uh oh! It looks like your template-event-name is invalid. '
                'Please make sure you have only one pair of curly braces in your message.'
            )

    @create_when2meet.error
    @set_when2meet_category.error
    async def handle_invalid_timezone_error(
        self,
        ctx: discord.ApplicationContext,
        error: discord.ApplicationCommandInvokeError
    ):
        if isinstance(error.original, commands.BadArgument):
            logging.warning(
                f'{ctx.author} tried to use the /{ctx.command.qualified_name} '
                f'however failed to do so because they inputted the invalid timezone {error.bad_argument!r}.'
            )
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
        if ctx.cog and ctx.cog is self:
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
