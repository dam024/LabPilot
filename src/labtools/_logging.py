from __future__ import annotations
from colorama import Fore, Style, just_fix_windows_console
import logging
from typing import Optional
import sys
import inspect
from labtools import _config as config

just_fix_windows_console()  # Initialize colorama for Windows compatibility


def get_caller_infos(caller_extra: int) -> str:
    """Summary

    Returns:
        str: Description
    """
    stack = inspect.stack()
    additional = ""
    if len(stack) > caller_extra + 2:
        i = caller_extra + 1
        additional = f"Function called: {stack[i].filename} in line {stack[i].lineno}"

    return additional


def warning(message: str, add_caller_infos: bool = True, caller_extra: int = 1):
    """
    Print a warning message with colored text.

    Parameters:
        message (str): The warning message to display.
        add_caller_infos (bool, optional): Indicates if we need to include informations about where the warning comes from
        caller_extra (int, optional): Indicates how many parent calls starting from the line calling this function we must use. Note that a caller_extra of 0 will refer to the line of the warning!
    """
    additional = ""
    if add_caller_infos:
        additional = f" {get_caller_infos(caller_extra=caller_extra+1)}"
    print(f"{Fore.YELLOW}Warning: {message}{additional}{Style.RESET_ALL}")


just_fix_windows_console()  # Initialize colorama for Windows compatibility


## New log level
DEV_WARNING = 15
logging.addLevelName(DEV_WARNING, "DEV_WARNING")


class ColoredFormatter(logging.Formatter):
    """
    A custom logging formatter that adds color to log messages based on their level.

    Color scheme:
        - DEBUG: Blue
        - INFO: White
        - WARNING: Yellow
        - ERROR: Red
        - CRITICAL: Magenta
    """

    # ANSI color codes for terminal output
    COLORS = {
        "DEBUG": Fore.BLUE,  # "\033[34m",  # Blue
        "INFO": Fore.GREEN,  # "\033[37m",  # White
        "WARNING": Fore.YELLOW,  # "\033[93m",  # Yellow
        "DEV_WARNING": Fore.YELLOW,  # "\033[93m",  # Yellow
        "ERROR": Fore.RED,  # "\033[91m",  # Red
        "CRITICAL": Fore.MAGENTA,  # "\033[95m",  # Magenta
    }

    RESET = Fore.RESET  # "\033[0m"  # Reset color code

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        """
        Initialize the ColoredFormatter.

        Args:
            fmt: Log message format string (default: standard format with color)
            datefmt: Date/time format for log messages
        """
        super().__init__(fmt, datefmt)
        self._fmt = fmt or "%(asctime)s - %(levelname)s - %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record with appropriate color codes.

        Args:
            record: The logging.LogRecord to format

        Returns:
            Formatted log message string with color codes
        """
        levelname = record.levelname.upper()
        color = self.COLORS.get(levelname, self.RESET)

        try:
            record.levelname = f"{color}{levelname}{self.RESET}"

            return super().format(record)
        finally:
            record.levelname = levelname


class ConsoleLogger(logging.Logger):
    """
    A console-based logger with colored output and level filtering.

    Features:
        - Color-coded log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - Configurable minimum log level
        - Console output with timestamps
    """

    def __init__(self, name: str = "ConsoleLogger", level: int = logging.NOTSET):
        """
        Initialize the ConsoleLogger.

        Args:
            name: Name of the logger instance
            level: Minimum log level to display (default: INFO)
        """
        self.config: config.GeneralConfig | None = None
        super().__init__(name, level)
        self._setup_console_handler()

    def _setup_console_handler(self) -> None:
        """
        Set up the console handler with color formatting.
        """
        # Clear any existing handlers
        self.handlers.clear()

        # Create console handler
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(self.level)

        # Set up formatter with color support
        formatter = ColoredFormatter(
            fmt="%(levelname)s [%(filename)s:%(lineno)d]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.console_handler.setFormatter(formatter)

        # Add handler to logger
        self.addHandler(self.console_handler)

    def makeRecord(self, *args, **kwargs) -> logging.LogRecord:
        return super().makeRecord(*args, **kwargs)

    def config_logger(self, config: config.GeneralConfig):
        self.config = config
        log_level = self.config.log_level

        self.setLevel(log_level)

    def newline(self):
        print(f"\n")

    def get_level(self) -> int:
        """
        Get the current minimum log level.

        Returns:
            The current log level as an integer
        """
        return self.level

    def is_enabled(self, level: int) -> bool:
        """
        Check if a specific log level is enabled.

        Args:
            level: Log level to check (e.g., logging.DEBUG, logging.INFO)

        Returns:
            True if the level is enabled, False otherwise
        """
        return self.isEnabledFor(level)

    def clear_handlers(self) -> None:
        """
        Remove all handlers from the logger.
        """
        self.handlers.clear()

    def dev_warning(self, message, *args, **kwargs):
        if self.isEnabledFor(DEV_WARNING):
            self._log(DEV_WARNING, message, args, **kwargs)


logging.setLoggerClass(ConsoleLogger)


def setup_logging(
    name: str = "AppLogger", level: int = logging.NOTSET
) -> ConsoleLogger:
    """
    Setup and return a configured ConsoleLogger instance.

    Args:
        name: Name of the logger instance
        level: Minimum log level (default: INFO)
        color: Enable color output (default: True)

    Returns:
        Configured ConsoleLogger instance

    Example:
        logger = setup_logging(level='DEBUG')
        logger.info('Application started')
    """
    root = logging.getLogger()
    root.setLevel(level)
    logger: ConsoleLogger = ConsoleLogger(name=name, level=level)
    return logger


logger = setup_logging(level=logging.INFO)

# Example usage and demonstration
if __name__ == "__main__" and False:
    # Create logger with default settings
    logger = setup_logging()

    # Demonstrate different log levels
    logger.debug("This is a DEBUG message (may be hidden by default)")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message (shown in yellow)")
    logger.error("This is an ERROR message (shown in red)")
    logger.critical("This is a CRITICAL message (shown in magenta)")

    # Demonstrate level filtering
    print("\n--- Setting level to WARNING (hiding DEBUG and INFO) ---")
    logger.setLevel(logging.WARNING)
    logger.debug("This DEBUG message will be hidden")
    logger.info("This INFO message will be hidden")
    logger.warning("This WARNING message will be shown")

    print("\n--- Setting level to DEBUG (showing all messages) ---")
    logger.setLevel(logging.DEBUG)
    logger.debug("This DEBUG message is now visible")
    logger.info("This INFO message is now visible")
    logger.warning("This WARNING message is still visible")

    # Demonstrate checking if level is enabled
    print(f"\n--- Level check (current level: {logger.get_level()}) ---")
    print(f"DEBUG enabled: {logger.is_enabled(logging.DEBUG)}")
    print(f"INFO enabled: {logger.is_enabled(logging.INFO)}")
    print(f"WARNING enabled: {logger.is_enabled(logging.WARNING)}")
