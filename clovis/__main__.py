from .logs import setUpLogger, set_pretty_formatter, logs_dir, PrettyFormatter
from .utils import load_timezones, autocomplete_logger
from .bot import bot
from . import config

import logging

set_pretty_formatter('%(levelname)s | %(name)s: %(asctime)s - [%(funcName)s()] %(message)s')
for name in ['bot', 'automated', 'commands', 'utils']:
    setUpLogger(f'clovis.{name}', files=not config.testing)

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
    file_handler = logging.FileHandler(logs_dir / 'autocomplete.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(pretty)
    autocomplete.addHandler(file_handler)

load_timezones()

with open('test-token.txt' if config.testing else 'token.txt') as file:
    bot.run(file.read())
