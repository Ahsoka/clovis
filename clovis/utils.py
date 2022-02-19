import discord


class MissingCategoryChannel(discord.DiscordException):
    pass

sentinel = object()

async def hardened_fetch_channel(channel_id: int, guild: discord.Guild, default=sentinel):
    # NOTE: Might want to add some checking to see if the retreived channel
    # is actually a category channel but the chances someone will set
    # a channel other than a category channel as the channel is extremely
    # unlikely unless they are doing some trickery with the discord API
    error = MissingCategoryChannel(f'Could not find channel with id: {channel_id}')
    if channel_id is None:
        if default is sentinel:
            raise error
        return default
    if (channel := guild.get_channel(channel_id)):
        return channel
    try:
        channel = await guild.fetch_channel(channel_id)
    except discord.NotFound as not_found:
        if default is sentinel:
            raise error from not_found
        return default
