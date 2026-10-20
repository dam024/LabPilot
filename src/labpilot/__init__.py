from labpilot._logging import ConsoleLogger
import logging
from labpilot._config import generalConfig as config
from labpilot._config import globalState
from labpilot.main import main
from labpilot._tools.updates import get_version


def getLogger(name: str) -> ConsoleLogger:
    logger = logging.getLogger(__name__ + "." + name)

    assert isinstance(logger, ConsoleLogger)

    return logger
