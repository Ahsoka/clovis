from discord.ext.pages import Paginator, PaginatorButton
from discord.ext.commands import Converter, BadArgument
from datetime import datetime, timedelta
from more_itertools import chunked
from typing import Dict, Set, List

import functools
import asyncio
import discord
import pathlib
import logging
import pandas
import pprint
import json
import time

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

commands = logging.getLogger('clovis.commands')


class MissingCategoryChannel(discord.DiscordException):
    pass


class HTMLChangeError(Exception):
    pass


class TimeZoneConverter(Converter):
    async def convert(self, ctx: discord.ApplicationContext, argument: str):
        format_tz_str = lambda tz_str: tz_str.replace(' ', '_').title()

        for timezone, series in load_timezones().items():
            if not (filtered := series[series.isin([argument.lower()])]).empty:
                timezone_str = f"{format_tz_str(timezone)}/{format_tz_str(filtered.iloc[0])}"
                commands.debug(f'Converted {argument} to valid timezone: {timezone_str}')
                return timezone_str
        bad_argument = BadArgument(f"'{argument}' is not a valid timezone.")
        bad_argument.bad_argument = argument
        raise bad_argument


class When2MeetPaginator(Paginator):
    ROWS = 3
    DAYS_PER_ROW = 4

    _dates: List[datetime] = []

    @classmethod
    def dates(cls, timezone, rows: int = None, days_per_row: int = None):
        if rows is None:
            rows = cls.ROWS
        if days_per_row is None:
            days_per_row = cls.DAYS_PER_ROW

        if not cls._dates:
            # NOTE: Here for some reason
            # the order of the for loop
            # is reversed from the conventional
            # set up.
            cls._dates = [
                datetime.now(timezone) + timedelta(days=days + row * days_per_row)
                for row in range(rows)
                for days in range(days_per_row)
            ]
        elif datetime.now(timezone).date() > cls._dates[0].astimezone(timezone).date():
            cls._dates.pop(0)
            cls._dates.append(cls._dates[-1] + timedelta(days=1))

        return cls._dates

    def __init__(
        self,
        pages,
        timezone,
        author_check: bool = True
    ) -> None:
        # NOTE: For the future if you are up for it
        # add the initially proposed time updating
        # so for example if it is 11:59 pm
        # and then it turns to 12:00 am
        # the bot will automatically remove
        # old day from the options.

        self.ready = asyncio.Event()

        self.selected_dates = set()
        self.date_buttons = []
        for row, button_row in enumerate(chunked(self.dates(timezone), self.DAYS_PER_ROW)):
            for date in button_row:
                self.date_buttons.append(DateButton(date, self, self.selected_dates, row=row))

        self.back_button = PaginatorButton(
            'prev',
            emoji='🔙',
            disabled=True,
            style=discord.ButtonStyle.primary
        )
        self.next_button = PaginatorButton(
            'next',
            emoji='🔜',
            disabled=True,
            style=discord.ButtonStyle.primary
        )
        self.submit_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            emoji='✔',
            disabled=True
        )

        self.submit_button.callback = self.sumbit_button_callback

        super().__init__(
            pages,
            custom_buttons=[self.back_button, self.next_button],
            author_check=author_check,
            use_default_buttons=False,
            disable_on_timeout=False,
            show_indicator=False,
            show_disabled=True,
            timeout=None
        )

        self.time_select = TimeSelect(
            datetime.min,
            datetime.max,
            paginator=self,
            row=0
        )

    async def sumbit_button_callback(self, interaction: discord.Interaction):
        commands.info(f"{interaction.user} submitted the paginator. ID: {id(self)}")
        self.ready.set()

    def create_payload(self, event_name: str, timezone: str):
        return {
            'NewEventName': event_name,
            'DateTypes': 'SpecificDates',
            'PossibleDates': '|'.join(
                map(lambda date: format(date, '%Y-%m-%d'), self.selected_dates)
            ),
            'NoEarlierThan': self.time_select.earliest,
            'NoLaterThan': self.time_select.latest,
            'TimeZone': timezone
        }

    async def goto_page(self, page_number=0) -> discord.Message:
        commands.info(f"Page {page_number} is being requested. ID: {id(self)}")
        return await super().goto_page(page_number)

    async def update(self, *args, **kwargs):
        raise NotImplementedError()

    def update_buttons(self) -> Dict:
        super().update_buttons()

        if self.current_page == 0:
            for key, button_dict in self.buttons.items():
                self.remove_item(button_dict['object'])
                button_dict['object'].row = self.ROWS
                if key == 'next':
                    button_dict['hidden'] = not bool(self.selected_dates)
                    button_dict['object'].disabled = not bool(self.selected_dates)
                self.add_item(button_dict['object'])

            self.submit_button.row = self.ROWS
            self.add_item(self.submit_button)

            for button in self.date_buttons:
                self.add_item(button)
        elif self.current_page == 1:
            self.add_item(self.time_select)
            for button_dict in self.buttons.values():
                self.remove_item(button_dict['object'])
                button_dict['object'].row = 1
                self.add_item(button_dict['object'])
            self.submit_button.row = 1
            self.add_item(self.submit_button)


class TimeSelect(discord.ui.Select):
    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        paginator: When2MeetPaginator,
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

    async def callback(self, interaction: discord.Interaction):
        commands.info(f"{interaction.user} selected {self.values} ID: {id(self.paginator)}")
        for option in self.options:
            option.default = False
            for value in self.values:
                if value == option.value:
                    option.default = True

        if len(self.values) == 2:
            self.paginator.submit_button.disabled = False
            await self.paginator.goto_page(1)

    def values_as_int(self, sort: bool = True) -> List[int]:
        values = map(lambda string: int(string), self.values)
        return list(sorted(values) if sort else values)

    @property
    def earliest(self) -> int:
        return self.values_as_int()[0]

    @property
    def latest(self) -> int:
        return self.values_as_int()[1]


class DateButton(discord.ui.Button):
    def __init__(
        self,
        date: datetime,
        paginator: When2MeetPaginator,
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

    async def callback(self, interaction: discord.Interaction):
        commands.info(f"{interaction.user} selected the {self.label} button. ID: {id(self.paginator)}")
        if self.style == discord.ButtonStyle.secondary:
            self.store_selected.add(self.date)
            self.style = discord.ButtonStyle.success
        elif self.style == discord.ButtonStyle.success:
            self.store_selected.remove(self.date)
            self.style = discord.ButtonStyle.secondary

        self.paginator.next_button.disabled = not bool(self.store_selected)

        self.paginator.submit_button.disabled = not (
            bool(self.store_selected)
            and len(self.paginator.time_select.values) == 2
        )

        await self.paginator.goto_page()

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

autocomplete_logger = logging.getLogger('clovis.autocomplete')

async def autocomplete_timezones(ctx: discord.AutocompleteContext):
    start = time.perf_counter()
    message = f"Autocomplete received {ctx.value!r} as input and took {{}} seconds to respond. It is returning "
    timezones = load_timezones()
    starting = []
    for full_timezone in timezones:
        timezone = full_timezone
        if '/' in timezone:
            timezone = timezone.split('/')[-1]
        if timezone.startswith(ctx.value.lower()):
            starting += timezones[full_timezone].str.title().to_list()

    if starting:
        autocomplete_logger.info(message.format(time.perf_counter() - start) + pprint.pformat(starting))
        return starting

    for series in timezones.values():
        starting += series[series.str.startswith(ctx.value.lower())].str.title().to_list()

    autocomplete_logger.info(message.format(time.perf_counter() - start) + pprint.pformat(starting))
    return starting
