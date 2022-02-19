from .commands import CommandsCog

import discord

bot = discord.Bot(
    debug_guilds=[810742455745773579, 940714521335578634],
    intents=discord.Intents(guilds=True, members=True)
)
# bot = discord.Bot(intents=discord.Intents(guilds=True, members=True))
bot.add_cog(CommandsCog())
