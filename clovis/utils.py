from discord.ext.commands import Converter, BadArgument
from typing import Dict
from dateutil import tz

import functools
import discord
import pathlib
import logging
import pandas
import json

logger = logging.getLogger(__name__)

if not hasattr(functools, 'cache'):
    # Function below is copied straight
    # from Python 3.9 GitHub
    # Reference: https://github.com/python/cpython/blob/3.9/Lib/functools.py#L650
    def functools_cache(user_function): return functools.lru_cache(maxsize=None)(user_function)
    functools.cache = functools_cache


class MissingCategoryChannel(discord.DiscordException):
    pass


class TimeZoneConverter(Converter):
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


timezones_json = pathlib.Path('timezones.json')
autocomplete = timezones_json.exists()

@functools.cache
def load_timezones():
    if autocomplete:
        with timezones_json.open() as file:
            timezones: Dict[str, pandas.Series] = json.load(file)
            for timezone in timezones:
                timezones[timezone] = pandas.Series(timezones[timezone])
        logger.debug("Detected the timezones.json file and loaded into RAM.")
        return timezones
    else:
        logger.warning(
            "The bot failed to detect the timezones.json file, "
            "autocomplete will be disabled."
        )
