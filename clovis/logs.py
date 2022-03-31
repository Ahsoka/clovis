from typing import List, Union

import logging, logging.handlers
import pathlib

# NOTE: Adapted from: https://github.com/Ahsoka/bdaybot/blob/master/bdaybot/logs.py
# There are major issues with the TimedRotatingFileHandler. It will be discontinued until
# until a proper fix can be found for it or until it is fixed. Either I am using it very
# incorrectly or there are major issues with. Nonetheless normal FileHandlers seems to work
# fine so they will now be used in place of the TimedRotatingFileHandler.

logs_dir = pathlib.Path('logs')

class PrettyFormatter(logging.Formatter):
    def __init__(self, *args, style='%', **kwargs):
        if style != '%':
            raise ValueError(f"__init__() does not currently accept {style} as valid style, please use %")
        super().__init__(*args, style=style, **kwargs)

    def levelname_in_front(self):
        loc = self._fmt.find('%(levelname)s')
        if loc == -1:
            return False
        return ')s' not in self._fmt[:loc]

    def format(self, record):
        unparsed = super().format(record)
        if not self.levelname_in_front():
            return unparsed
        levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        max_length = max(map(len, levels))
        for index, level in enumerate(levels):
            if level in unparsed:
                break
        end_loc = unparsed.find(level) + len(level)
        end = unparsed[end_loc]
        while end != ' ':
            end_loc += 1
            end = unparsed[end_loc]
        spaces = max_length - len(level)
        returning = (" " * spaces) +  unparsed[:end_loc] + unparsed[end_loc:]
        # print(f"returning == unparsed = {unparsed == returning}")
        return returning

def setUpHandler(
    handler: logging.Handler,
    level: int = logging.DEBUG,
    formatter: logging.Formatter = PrettyFormatter(
        fmt='%(levelname)s | %(name)s: %(asctime)s - [%(funcName)s()] %(message)s'
    )
):
    if level is not None:
        handler.setLevel(level)

    if formatter is not None:
        handler.setFormatter(formatter)

    return handler

def setUpLogger(logger: Union[str, logging.Logger], handlers: List[logging.Handler], default_level=logging.DEBUG):
    if isinstance(logger, str):
        logger = logging.getLogger(logger)

    if default_level is not None:
        logger.setLevel(default_level)

    for handler in handlers:
        logger.addHandler(handler)

    return logger

console = logging.StreamHandler()
setUpHandler(console)
