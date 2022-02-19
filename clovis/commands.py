from .utils import hardened_fetch_channel
from discord.commands import Option
from discord.ext import commands
from . import sessionmaker
from .tables import Guild

import discord


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
        else:
            await ctx.respond(
                "I don't have access to create channels in this category. "
                "Please give me access, before setting it as the category."
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

    @start_commands.command(
        name='listening',
        description="Use this command to make me start listening for new members joining."
    )
    @commands.has_guild_permissions(administrator=True)
    async def start_listening(self, ctx: discord.ApplicationContext):
        async with sessionmaker.begin() as session:
            sql_guild = await Guild.get_or_create(session, ctx.guild_id)
            if sql_guild.create_channel:
                await ctx.respond("I am already listening for messages!")
            else:
                sql_guild.create_channel = True
                await ctx.respond("I will now start creating new text channels when new members join.")

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
