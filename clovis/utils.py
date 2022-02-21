from discord.ext.commands import Converter, BadArgument
from datetime import datetime, timedelta
from typing import Dict, Set, List

import functools
import discord
import pathlib
import logging
import pandas
import json

logger = logging.getLogger(__name__)

num_to_clock_emoji = {
    0: '🕛',
    1: '🕐',
    2: '🕑',
    3: '🕒',
    4: '🕓',
    5: '🕔',
    6: '🕕',
    7: '🕖',
    8: '🕗',
    9: '🕘',
    10: '🕙',
    11: '🕚'

}

if not hasattr(functools, 'cache'):
    # Function below is copied straight
    # from Python 3.9 GitHub
    # Reference: https://github.com/python/cpython/blob/3.9/Lib/functools.py#L650
    def functools_cache(user_function): return functools.lru_cache(maxsize=None)(user_function)
    functools.cache = functools_cache


class MissingCategoryChannel(discord.DiscordException):
    pass


class TimeZoneConverter(Converter):
    async def convert(self, ctx: discord.ApplicationContext, argument: str):
        format_tz_str = lambda tz_str: tz_str.replace(' ', '_').title()

        for timezone, series in load_timezones().items():
            if not (filtered := series[series.isin([argument.lower()])]).empty:
                timezone_str = f"{format_tz_str(timezone)}/{format_tz_str(filtered.iloc[0])}"
                return timezone_str
        bad_argument = BadArgument(f"'{argument}' is not a valid timezone.")
        bad_argument.bad_argument = argument
        raise bad_argument


class TimeSelect(discord.ui.Select):
    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        paginator,
        row: int,
        placeholder: str = "Select a start time and an end time.",
        disabled: bool = False
    ):
        options = []
        for hour in range((end_time - start_time).seconds // 3600 + 1):
            new_time = start_time + timedelta(hours=hour)
            options.append(
                discord.SelectOption(
                    label=format(new_time, '%I %p'),
                    emoji=num_to_clock_emoji[new_time.hour % 12],
                    value=str(hour)
                )
            )

        super().__init__(
            placeholder=placeholder,
            min_values=2,
            max_values=2,
            options=options,
            disabled=disabled,
            row=row
        )

        self.paginator = paginator
        self.start_time = start_time
        self.end_time = end_time

    def values_as_int(self, sort: bool = True) -> List[int]:
        values = map(lambda string: int(string), self.values)
        return list(sorted(values) if sort else values)


class DateButton(discord.ui.Button):
    def __init__(
        self,
        date: datetime,
        paginator,
        store_selected: Set[datetime],
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        disabled: bool = False,
        custom_id: str = None,
        row: int = None,
        date_format: str = '%A %m/%d',
    ):
        if not isinstance(store_selected, set):
            raise TypeError(f'store_selected parameter must be a set, not {type(store_selected)!r}')

        super().__init__(
            style=style,
            label=format(date, date_format),
            disabled=disabled,
            custom_id=custom_id,
            row=row
        )
        self.paginator = paginator
        self.date = date
        self.date_format = date_format
        self.store_selected = store_selected

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

async def autocomplete_timezones(ctx: discord.AutocompleteContext):
    timezones = load_timezones()
    starting = []
    for full_timezone in timezones:
        timezone = full_timezone
        if '/' in timezone:
            timezone = timezone.split('/')[-1]
        if timezone.startswith(ctx.value.lower()):
            starting += timezones[full_timezone].str.title().to_list()

    if starting:
        return starting

    for series in timezones.values():
        starting += series[series.str.startswith(ctx.value.lower())].str.title().to_list()

    return starting
