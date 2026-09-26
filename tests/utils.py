import unittest
import shutil
from typing import Any, Dict, List, Tuple
from pathlib import Path

from labtools import config
from labtools.DataReceiver import LiveDataReader
from labtools.GUI.binding import BindingSupport
from labtools.data_management.local_storage import LocalStorage


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

    def tearDown(self) -> None:
        """Clean up configuration and resources after each test method.

        Restores configuration to original state, clears bindings, and removes
        temporary data directories created during testing.

        Returns:
            None
        """
        self.assertFalse(config.simulation)
        self.assertFalse(config.use_gui)

        # Reset the config
        for section, option, value in self.config:
            config.set(section, option, value)

        # Reset the bindings
        self._reset_bindings()

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
            # Automatically pause the readers
            if isinstance(bindingInstance, LiveDataReader):
                if (
                    hasattr(bindingInstance, "collector")
                    and bindingInstance.collector is not None
                ):
                    bindingInstance.pause()
                    bindingInstance.collector.join()
            # Reset the binding
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
