from .logs import setUpLogger, setUpHandler, logs_dir, console
from .utils import load_timezones, autocomplete_logger
from .bot import bot
from . import config

import logging

handlers = [console]
if config.testing:
    setUpLogger(autocomplete_logger, [console])
else:
    setUpLogger(
        autocomplete_logger,
        [
            setUpHandler(
                logging.FileHandler(logs_dir / 'autocomplete.log')
            )
        ]
    )
    everything = setUpHandler(logging.FileHandler(logs_dir / 'clovis.log'))
    errors = setUpHandler(
        logging.FileHandler(logs_dir / 'ERRORS.clovis.log'),
        level=logging.ERROR
    )
    handlers += [everything, errors]

for name in ['bot', 'automated', 'commands', 'utils']:
    setUpLogger(f'clovis.{name}', handlers=handlers)

load_timezones()

with open('test-token.txt' if config.testing else 'token.txt') as file:
    bot.run(file.read())
