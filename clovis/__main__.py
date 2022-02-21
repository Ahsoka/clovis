from clovis.utils import load_timezones, autocomplete_logger
from .logs import setUpLogger, PrettyFormatter
from .bot import bot
from . import config

import logging
import pathlib

for name in ['bot', 'automated', 'commands', 'utils']:
    setUpLogger(
        f'clovis.{name}',
        '%(levelname)s | %(name)s: %(asctime)s - [%(funcName)s()] %(message)s',
        files=not config.testing
    )

autocomplete = autocomplete_logger
autocomplete.setLevel(logging.DEBUG)
pretty = PrettyFormatter(
    fmt='%(levelname)s | %(name)s: %(asctime)s - [%(funcName)s()] %(message)s'
)
if config.testing:
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(pretty)
    autocomplete.addHandler(console)
else:
    file_handler = logging.FileHandler(pathlib.Path('logs') / 'autocomplete.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(pretty)
    autocomplete.addHandler(file_handler)

load_timezones()

with open('test-token.txt' if config.testing else 'token.txt') as file:
    bot.run(file.read())
