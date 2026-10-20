import os
import unittest
import shutil
from typing import Any, Callable, Dict, List, Tuple
from pathlib import Path

import labpilot
import logging

from labpilot.data_management.database_manager import DB

logger = logging.getLogger(labpilot.__name__ + "." + __name__)

import labpilot.utils as utils

from labpilot import config
from labpilot.GUI.binding import BindingSupport
from labpilot.data_management.local_storage import LocalStorage
from labpilot.recording_manager import RecordingManager


class UpdatableConfigTest(unittest.TestCase):
    """Test case for managing and resetting updatable configuration settings.

    This test class provides utilities for testing configuration-dependent behavior
    by allowing temporary configuration changes and automatic cleanup after tests.
    """

    def setUp(self) -> None:
        """Initialize test configuration state before each test method.

        Sets up an empty config history and ensures simulation mode is disabled.

        Returns:
            None
        """
        # Register the cleanups. They are executed AFTER the tearDown(). These methods will ensure proper reset of global states of the application
        self.addCleanup(self._reset_config)
        self.addCleanup(self._reset_bindings)
        self.addCleanup(self._reset_recording_manager)

        # Create local storage path
        path = Path(config.get("GENERAL", "local_storage_path"))
        path.mkdir(parents=True, exist_ok=True)

        # print(self.__class__.__name__)
        self.assertEqual(
            len(logger.handlers),
            0,
            f"All log handlers must be deleted for this!!! {logger.handlers}",
        )
        self.config: List[Tuple[str, str, str]] = []
        self.assertFalse(config.simulation)
        self.assertFalse(config.use_gui)
        return super().setUp()

    def config_set(self, section: str, option: str, value: str) -> None:
        """Records and applies a configuration change for testing purposes.

        Stores the original value of the configuration option before changing it,
        allowing for proper rollback in tearDown.

        Args:
            section: Configuration section name (e.g., "GENERAL")
            option: Configuration option name within the section
            value: New value to set for the option
        """
        val = config.get(section, option)
        self.config.append((section, option, val))
        config.set(section, option, value)

    def _reset_config(self):
        """Resets the configuration that may have been modified for the test purposes"""
        # Reset the config
        for section, option, value in self.config:
            config.set(section, option, value)

    def _reset_recording_manager(self):
        """Reset the Recording Manager state"""
        RecordingManager._main = None

    def tearDown(self) -> None:
        """Clean up configuration and resources after each test method.

        Restores configuration to original state, clears bindings, and removes
        temporary data directories created during testing.

        Returns:
            None
        """
        # Execute code that was supposed to be executed on the main thread
        # self.assertFalse(self.has_thread_jobs())
        self.main_thread_execute()

        # Clean the output directory
        data_path = Path(config.output_dir)
        if data_path.exists():
            shutil.rmtree(data_path)

        # Delete local storage
        path = config.get("GENERAL", "local_storage_path")
        if path is not None and Path(path).exists():
            # Close the database
            db = LocalStorage.main()
            db.__del__()
            del db
            shutil.rmtree(Path(path))

        # Assertion
        self.assertFalse(config.simulation)
        self.assertFalse(config.use_gui)

        return super().tearDown()

    def _reset_bindings(self) -> None:
        """Resets all the `BindingSupport` instances.

        In the normal phase of the program, the Bindings live always and should never be reset.
        For the tests, since they need to be independent, this method resets the variables to prevent
        contamination between tests.

        Returns:
            None
        """
        # Reset the Bindings...
        for bindingInstance in BindingSupport.parametrables.values():
            if bindingInstance.__class__.__binding_instantiated__:
                bindingInstance.__class__.__binding_instantiated__ = False
                for _, binding in bindingInstance.__class__._bindings.items():
                    if hasattr(binding, "_variable"):
                        del binding._variable

            # Clean up any remaining state
            if bindingInstance.__class__.__main_instance__ is not None:
                bindingInstance.__class__.__main_instance__ = None
            self.assertIsNone(bindingInstance.__class__.__main_instance__)

        BindingSupport.parametrables.clear()

    ## Mark: Thread management functions specific for tests
    def main_thread_execute(self):
        """Executes all the methods that were called from the main thread to be executed on the main thread"""
        assert isinstance(
            utils._executor, utils.TestThreadExecutor
        ), f"Obtained class: {utils._executor}"

        utils._executor.main_thread_execute()

    def has_thread_jobs(self) -> bool:
        """Returns a boolean indicating if one or multiple methods need to be executed on the main thread"""
        assert isinstance(utils._executor, utils.TestThreadExecutor)

        return utils._executor.has_main_thread_func()


def simulation(func):
    """Decorator to mark test functions for simulation mode execution.

    Wraps a test function to temporarily enable simulation mode during execution,
    then restores the original state afterwards.

    Args:
        func: The test function to wrap

    Returns:
        Callable: The wrapped function with simulation mode handling
    """

    def wrapper(*args, **kwargs):
        # Set simulation
        config.simulation = True
        # Execute the test
        try:
            func(*args, **kwargs)
        finally:
            # Set back the simulation
            config.simulation = False  # val

    return wrapper


def use_gui(func):
    """Decorator to mark test functions for GUI mode execution. It will adapt the configuration for this purpose

    Wraps a test function to temporarily enable GUI mode during execution,
    then restores the original state afterwards.

    Args:
        func: The test function to wrap

    Returns:
        Callable: The wrapped function with gui mode handling
    """

    def wrapper(*args, **kwargs):
        # Set GUI
        config.use_gui = True
        # Execute the test
        try:
            func(*args, **kwargs)
        finally:
            # Set back the GUI
            config.use_gui = False

    return wrapper
