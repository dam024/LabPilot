from labtools._logging import ConsoleLogger
import logging
from labtools._config import generalConfig as config
from labtools._config import globalState
from labtools.main import main
from labtools._tools.updates import get_version


def getLogger(name: str) -> ConsoleLogger:
    logger = logging.getLogger(__name__ + "." + name)

    assert isinstance(logger, ConsoleLogger)

    return logger
