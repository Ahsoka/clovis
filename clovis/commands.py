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
