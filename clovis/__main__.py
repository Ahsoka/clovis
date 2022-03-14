from .logs import setUpLogger, set_pretty_formatter, logs_dir, PrettyFormatter
from .utils import load_timezones, autocomplete_logger
from .bot import bot
from . import config

import logging

# set_pretty_formatter('%(levelname)s | %(name)s: %(asctime)s - [%(funcName)s()] %(message)s')

pretty = PrettyFormatter(
    fmt='%(levelname)s | %(name)s: %(asctime)s - [%(funcName)s()] %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(pretty)

for name in ['bot', 'automated', 'commands', 'utils']:
    logger = logging.getLogger(f'clovis.{name}')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console)
    # setUpLogger(f'clovis.{name}', files=not config.testing)

autocomplete = autocomplete_logger
autocomplete.setLevel(logging.DEBUG)
if config.testing:
    autocomplete.addHandler(console)
else:
    file_handler = logging.FileHandler(logs_dir / 'autocomplete.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(pretty)
    autocomplete.addHandler(file_handler)

    everything = logging.FileHandler(logs_dir / 'clovis.log')
    everything.setLevel(logging.DEBUG)
    everything.setFormatter(pretty)

    errors = logging.FileHandler(logs_dir / 'ERRORS.clovis.log')
    errors.setLevel(logging.ERROR)
    errors.setFormatter(pretty)

    for name in ['bot', 'automated', 'commands', 'utils']:
        logger = logging.getLogger(f'clovis.{name}')
        logger.addHandler(everything)
        logger.addHandler(errors)

load_timezones()

with open('test-token.txt' if config.testing else 'token.txt') as file:
    bot.run(file.read())
