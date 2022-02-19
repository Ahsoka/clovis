from .utils import hardened_fetch_channel
from discord.commands import Option
from discord.ext import commands
from . import sessionmaker
from .tables import Guild

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
        # NOTE: Still need to do more testing to determine which combination
        # of permissions will always guarantee that the bot will be able to
        # create the given channel in the category.
        if channel.permissions_for(ctx.me).manage_channels:
            async with sessionmaker.begin() as session:
                sql_guild = await Guild.get_or_create(session, ctx.guild_id)
                sql_guild.category_id = channel.id
                sql_guild.create_channel = True
            await ctx.respond(f"{channel.mention} has been set as the new category to create private channels in.")
            logger.info(f"{ctx.author} used the /set category command to set the category to {channel}.")
        else:
            await ctx.respond(
                "I don't have access to create channels in this category. "
                "Please give me access, before setting it as the category."
            )
            logger.info(
                f"{ctx.author} tried to use the /set category command "
                "but selected a category that that bot does not have access to."
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

    @commands.slash_command(
        description="Use this command to get my source code!"
    )
    async def source(self, ctx: discord.ApplicationContext):
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
        else:
            # NOTE: In this case you may want to add ping_dev function like with the bdaybot
            logger.error("The following error occured with the bot:", exc_info=error)
            await ctx.respond("Uh oh! Something went wrong on our end. Please try again later!")
