import unittest
import logging

import labpilot
from labpilot._logging import ConsoleLogger


class TestLoggingConfiguration(unittest.TestCase):
    # Make a test out of this
    def find_loggers(self, my_loggers: bool = True) -> list[str]:
        def is_my_logger(name: str) -> bool:
            return name == ConsoleLogger.get_app_logger_name() or name.startswith(
                ConsoleLogger.get_app_logger_name() + "."
            )

        return sorted(
            name
            for name in logging.Logger.manager.loggerDict
            if (my_loggers and is_my_logger(name))
            or (not my_loggers and not is_my_logger(name))
        )

    def test_app_logger_name(self):
        self.assertEqual(
            ConsoleLogger.get_app_logger_name(),
            labpilot.__name__,
            "This test is correct, this is a convention defined for the application",
        )

    def test_all_logger_class(self):
        """Makes sure that all loggers are of the correct class"""
        for l in self.find_loggers():
            log = logging.getLogger(l)
            self.assertIsInstance(log, ConsoleLogger, f"Logger name: {log.name}")

    def test_no_handlers(self):
        """Test that no handler is left in the loggers for the tests"""
        for l in self.find_loggers():
            log = logging.getLogger(l)
            self.assertEqual(
                len(log.handlers),
                0,
                f"Must have removed all handlers for `{l}`: {log.handlers}",
            )
