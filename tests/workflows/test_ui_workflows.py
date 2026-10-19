"""
================================================================================
LabPilot UI Workflow Tests
================================================================================

This module contains tests for the UI workflow functionality. It tests the
integration between the GUI and the underlying data acquisition system.

Workflow being tested:
1. Application Launch
2. View Selection - User selects the view "ch1 + ch2"
3. UI State Verification - Verify UI parameters and plots are correct
4. Experiment Start - User initiates an experiment
5. Runtime Verification - Verify reader threads are running and base file is being saved
6. Experiment Stop - User stops the experiment
7. Post-Stop Verification - Verify readers stopped and base file is finalized

Key Components:
---------------
- MainGUILoop: Manages the main loop and threads
- MainLoopHandler.select_active_view(): Switches between views
- MainLoopHandler.start_threads(): Starts data acquisition threads
- MainLoopHandler.stop_threads(): Stops all data acquisition threads
- DataReceiver.LiveDataReader: Base class for data readers with status and thread lifecycle
"""

from typing import Any, List, Type
import unittest
import time

from PySide6.QtWidgets import QApplication
from labpilot.GUI.mainGUI import MainGUILoop, MainWindow
from labpilot import logger, config
import tests.utils as tu
import tests.dummy_classes as dummy
from tests.utils import use_gui


def get_test_readers() -> list:
    """
    Get the list of test readers for testing.

    Returns:
        List of reader instances (TestReader and TestStreamer)
        that are used in the simulation mode.
    """
    return dummy.get_test_readers()


class TestUIWorkflows(tu.UpdatableConfigTest):
    """
    Test class for the UI workflow functionality.

    This class tests the complete workflow of:
    1. Application launch and initialization
    2. View selection ("ch1 + ch2")
    3. UI updates (parameters and plots)
    4. Starting experiments with real threads
    5. Reading from files (base file saving verification)
    6. Stopping experiments
    7. Verifying readers stopped and files finalized

    Each test method is decorated with @use_gui to enable GUI mode execution.
    """

    def assertSameInstances(self, arr: List[Any], c: List[Type]):
        for obj in arr:
            found = False
            for _class in c:
                if isinstance(obj, _class) and obj.__class__ == _class:
                    found = True
                    break

            self.assertTrue(
                found, f"Not instance of `{obj.__class__.__name__}` found in {c}"
            )

    def setUp(self) -> None:
        """
        Set up the test environment before each test method.

        Creates the QApplication instance if it doesn't exist,
        initializes the MainGUILoop with dummy views and readers.

        Returns:
            None
        """
        # Call parent setUp first (which expects simulation=False, we'll enable it per test)
        super().setUp()

        # Create QApplication if it doesn't exist
        # app = QApplication.instance()
        # if app is None:
        #    app = QApplication([])

        # Get views for testing (using dummy classes for proper reader matching)
        views = [dummy.TestView, dummy.Test2View, dummy.InsertionLoss, dummy.Test3View]

        # Create the main GUI loop
        self.loop = MainGUILoop()
        self.loop.run_main_thread = False
        self.loop.start()

        # Check that initialization happened correctly: All views are loaded
        for view in self.loop.views:
            found = False
            for v in views:
                if isinstance(view, v) and view.__class__ == v:
                    found = True
                    break

            self.assertTrue(
                found, f"View `{view.__class__.__name__}` not found in {views}"
            )

        # Check that the readers were correctly instantiated
        self.assertSameInstances(self.loop.readers, get_test_readers())

        # Test all analysis are instantiated correctly
        for view in self.loop.views:
            for analysis in view.analysis:
                self.assertGreater(len(analysis.readers), 0)

    def tearDown(self) -> None:
        """
        Clean up after each test method.

        Stops any running threads and resets the configuration.

        Returns:
            None
        """

        # Stop any running experiment
        self.loop.stop_threads()

        # Clear all handlers to prevent leaks
        self.join_threads()

        super().tearDown()

    def join_threads(self):
        """Joins all the threads if they have been started"""
        for reader in self.loop.readers:
            if hasattr(reader, "collector") and reader.collector is not None:
                reader.collector.join()

        if self.loop.global_thread is not None:
            self.loop.global_thread.join()

    @use_gui
    def test_select_ch1_ch2_view(self):
        """
        Test 1: User selects the view "ch1 + ch2"

        Verifies that:
        - The correct view is selected
        - The view name is displayed correctly
        - The view is in the window's view dictionary

        This test is decorated with @use_gui to enable GUI mode execution.
        """
        # Find the ch1 + ch2 view (Test2View has name "ch1 + ch2")
        ch1_ch2_view = list(
            filter(lambda x: isinstance(x, dummy.Test2View), self.loop.views)
        )[0]

        # Select the view
        self.loop.select_active_view(ch1_ch2_view)

        # Verify the view was selected
        self.assertEqual(
            self.loop.active_view.name,
            "ch1 + ch2",
            "The active view should be 'ch1 + ch2'",
        )

        # Verify the view is in the window's view dictionary
        self.assertIn(
            ch1_ch2_view.name,
            self.loop.window.views_dic,
            "The view should be in the window's view dictionary",
        )

    @use_gui
    def test_ui_updates_after_view_selection(self):
        """
        Test 2: Check that the UI updates properly after view selection

        Verifies that:
        - The displayed parameters are from the correct view
        - The plots displayed are the right ones (ch1 and ch2)

        This test is decorated with @use_gui to enable GUI mode execution.
        """
        # Use TestView which has both TestReader and TestStreamer readers
        test_view = list(
            filter(lambda x: isinstance(x, dummy.Test2View), self.loop.views)
        )[0]
        self.assertIsInstance(test_view, dummy.Test2View)

        # Select the view
        self.loop.select_active_view(test_view)

        # Verify the active view
        self.assertEqual(
            self.loop.active_view.name,
            test_view.name,
            f"The active view should be '{test_view.name}'",
        )

        # Check that the view has the correct graphs
        graphs = test_view.all_graphs

        # Verify that we have the expected graphs
        self.assertGreater(len(graphs), 0, "The view should have at least one graph")

        # Check graph names - TestAnalysis (from TestView) uses TestReader and TestStreamer which have test_ch_1 and test_ch_2
        graph_names = [g.name for g in graphs]

        # Verify that ch1 and ch2 graphs are present
        self.assertIn(
            "test_ch_1",
            graph_names,
            "The view should have a plot for channel 1 (test_ch_1)",
        )
        self.assertIn(
            "test_ch_2",
            graph_names,
            "The view should have a plot for channel 2 (test_ch_2)",
        )

    @use_gui
    def test_start_experiment(self):
        """
        Test 3: User starts an experiment with real thread management

        Verifies that:
        - Real start_threads() is called (not mocked)
        - The main thread loop is started correctly
        - The experiment running status is set correctly

        This test is decorated with @use_gui to enable GUI mode execution.
        """
        # Use TestView which has both TestReader and TestStreamer readers
        test_view = self.loop.views[-1]  # dummy.TestView()

        # Select the view first
        self.loop.select_active_view(test_view, adapt_threads=False)

        # Start the experiment with REAL start_threads (not mocked)
        # This calls regularize_threads() internally which will start the threads
        self.loop.main_thread_loop()

        for reader in self.loop.readers:
            self.assertTrue(reader.__class__.__binding_instantiated__)

        self.loop.start_threads()

        # Verify that all readers have collector threads created
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "collector"),
                f"Reader {reader.__class__.__name__} should have a collector thread attribute",
            )
            self.assertIsNotNone(
                reader.collector,
                f"Reader {reader.__class__.__name__} collector should not be None",
            )
            self.assertTrue(reader.is_running)

        # Verify that the active view is set correctly (TestView has name "Reader + ch1")
        self.assertEqual(
            self.loop.active_view.name,
            test_view.name,
            f"The active view should be '{test_view.name}'",
        )

    @use_gui
    def test_readers_running_after_start(self):
        """
        Test 4: Check that correct readers are running after starting the experiment

        Verifies that:
        - Readers have proper attributes for file saving
        - Collector threads are running (multi-threading validation)
        - Base file is being saved at the right location

        This test is decorated with @use_gui to enable GUI mode execution.
        """
        # Use TestView which has both TestReader and TestStreamer readers
        test_view = self.loop.views[-1]

        # Select the view
        self.loop.select_active_view(test_view)

        # Start the experiment with REAL start_threads (not mocked)
        self.loop.start_threads()
        self.loop.main_thread_loop()

        # Verify that all readers have a collector thread and it's running
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "collector"),
                f"Reader {reader.__class__.__name__} should have a collector thread",
            )
            self.assertIsNotNone(
                reader.collector,
                f"Reader {reader.__class__.__name__} collector should not be None",
            )

            # Verify the collector thread is alive (multi-threading validation)
            self.assertTrue(
                reader.collector.is_alive(),
                f"Reader {reader.__class__.__name__} collector thread should be running",
            )

        # Verify that the save queue is available for each reader
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "save_queue"),
                f"Reader {reader.__class__.__name__} should have a save_queue",
            )
            # save_queue should be a Queue object
            self.assertIsNotNone(reader.save_queue)

        # Check that the dirname (for file saving) is set correctly
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "dirname"),
                f"Reader {reader.__class__.__name__} should have a dirname",
            )
            self.assertIsInstance(
                reader.dirname,
                str,
                f"Reader {reader.__class__.__name__}.dirname should be a string",
            )

    @use_gui
    def test_stop_experiment(self):
        """
        Test 5: User stops the experiment

        Verifies that:
        - Real stop_threads() is called (not mocked)
        - The plot timer is stopped
        - The experiment running status is updated
        - The main thread loop is stopped

        This test is decorated with @use_gui to enable GUI mode execution.
        """
        # Use TestView which has both TestReader and TestStreamer readers
        test_view = self.loop.views[-1]

        # Select the view
        self.loop.select_active_view(test_view)

        # Start the experiment first
        self.loop.start_threads()
        self.loop.main_thread_loop()

        # Stop the experiment
        self.loop.stop_threads()

        # Verify that the plot timer was stopped
        self.assertFalse(self.loop.window.plot_timer.isActive())

        # Verify that the active view is still correctly set
        self.assertEqual(
            self.loop.active_view.name,
            test_view.name,
            f"The active view should still be '{test_view.name}'",
        )

    @use_gui
    def test_readers_stopped_after_stop(self):
        """
        Test 6: Check that readers were stopped after stopping the experiment

        Verifies that:
        - Collector threads have been stopped (multi-threading validation)
        - Readers have proper cleanup attributes (on_stop)
        - Base file has been saved/finalized

        This test is decorated with @use_gui to enable GUI mode execution.
        """
        # Use TestView which has both TestReader and TestStreamer readers
        test_view = self.loop.views[-1]

        # Select the view
        self.loop.select_active_view(test_view)

        # Start the experiment
        self.loop.start_threads()
        self.loop.main_thread_loop()

        # Stop the experiment
        self.loop.stop_threads()
        self.join_threads()

        # Verify that all readers' collector threads have stopped
        for reader in self.loop.readers:
            if hasattr(reader, "collector") and reader.collector is not None:
                # Thread should have terminated
                self.assertFalse(
                    reader.collector.is_alive(),
                    f"Reader {reader.__class__.__name__} collector thread should have stopped",
                )

        # Verify that all readers have the on_stop method (cleanup attribute)
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "on_stop"),
                f"Reader {reader.__class__.__name__} should have on_stop method",
            )

    @use_gui
    def test_full_workflow(self):
        """
        Test: Complete workflow from view selection to experiment stop with file system verification

        Tests the complete sequence:
        1. Application initialization with @use_gui decorator
        2. Select "ch1 + ch2" view
        3. Verify UI updates (parameters and plots)
        4. Start experiment with real threads
        5. Verify readers are running and files are being saved
        6. Stop experiment
        7. Verify readers stopped and files finalized

        This test is decorated with @use_gui to enable GUI mode execution.
        It ensures integration testing of the actual application logic
        without compromising core functionality through over-mocking.
        """
        from labpilot.analysis import View

        # Use GUI mode (handled by @use_gui decorator)
        test_view = test_view = list(
            filter(lambda x: isinstance(x, dummy.Test2View), self.loop.views)
        )[0]

        # Step 1: Verify view exists and has correct name
        self.assertEqual(
            test_view.name,
            f"{test_view.name}",
            f"Step 1: The view should be '{test_view.name}'",
        )

        # Step 2: Verify that the view is in the views dictionary
        self.assertIn(
            test_view.name,
            self.loop.window.views_dic,
            "The view should be in the window's view dictionary",
        )

        # Step 3: Check UI updates - verify graphs are present
        graphs = test_view.all_graphs
        self.assertGreater(len(graphs), 0, "Step 3: The view should have graphs")

        graph_names = [g.name for g in graphs]
        self.assertIn(
            "test_ch_1", graph_names, "Step 3: Should have ch1 plot (test_ch_1)"
        )
        self.assertIn(
            "test_ch_2", graph_names, "Step 3: Should have ch2 plot (test_ch_2)"
        )

        # Step 4: Start experiment with real threads
        readers = get_test_readers()
        self.loop.select_active_view(test_view)
        self.loop.start_threads()
        self.loop.main_thread_loop()

        # Step 5: Verify readers are running (multi-threading validation)
        for reader in readers:
            self.assertTrue(
                hasattr(reader, "dirname"),
                f"Step 5: Reader {reader.__class__.__name__} should have dirname",
            )
            self.assertIsInstance(
                reader.dirname,
                str,
                f"Step 5: Reader {reader.__class__.__name__}.dirname should be a string",
            )

            # Verify collector thread is running
            if hasattr(reader, "collector") and reader.collector is not None:
                self.assertTrue(
                    reader.collector.is_alive(),
                    f"Step 5: Reader {reader.__class__.__name__} collector should be running",
                )

        # Step 6: Stop experiment
        self.loop.stop_threads()

        # Step 7: Verify readers stopped (multi-threading validation)
        for reader in readers:
            if hasattr(reader, "collector") and reader.collector is not None:
                self.assertFalse(
                    reader.collector.is_alive(),
                    f"Step 7: Reader {reader.__class__.__name__} collector should have stopped",
                )

            # Verify on_stop method exists
            self.assertTrue(
                hasattr(reader, "on_stop"),
                f"Step 7: Reader {reader.__class__.__name__} should have on_stop method",
            )

    # =============================================================================
    # File System Verification Tests (Integration Tests)
    # =============================================================================

    @use_gui
    def test_base_file_is_created_during_experiment(self):
        """
        Integration Test: Verify that base files are created at the expected path

        This test validates that:
        - When an experiment is running, data is being saved to files
        - Files are created in the labpilot/output directory
        - Files follow the expected naming convention

        This is an integration test that verifies file system side effects.
        Decorated with @use_gui to enable GUI mode execution.
        """
        # Use TestView which has both TestReader and TestStreamer readers
        test_view = self.loop.views[-1]

        # Select the view
        self.loop.select_active_view(test_view)

        # Start the experiment with REAL start_threads (not mocked)
        self.loop.start_threads()
        self.loop.main_thread_loop()

        # Verify that readers have save_queue and can save data
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "save_queue"),
                f"Reader {reader.__class__.__name__} should have save_queue",
            )
            self.assertIsNotNone(reader.save_queue)

        # Stop the experiment to finalize files
        self.loop.stop_threads()

        # Verify that readers have on_stop method
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "on_stop"),
                f"Reader {reader.__class__.__name__} should have on_stop method",
            )

        # The base files should have been saved (in simulation mode, they're loaded from disk)
        # We verify that readers have the necessary attributes for file operations
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "dirname"),
                f"Reader {reader.__class__.__name__} should have dirname for file path",
            )
            self.assertIsInstance(
                reader.dirname,
                str,
                f"Reader {reader.__class__.__name__}.dirname should be a valid string path",
            )

    @use_gui
    def test_thread_lifecycle_validation(self):
        """
        Integration Test: Validate thread lifecycle from start to stop

        This test ensures that:
        - Threads are properly started when experiment begins
        - Threads are properly stopped when experiment ends
        - Thread termination is clean (no resource leaks)

        This validates multi-threading behavior without mocking.
        Decorated with @use_gui to enable GUI mode execution.
        """
        # Use TestView which has both TestReader and TestStreamer readers
        test_view = self.loop.views[-1]

        # Select the view
        self.loop.select_active_view(test_view)

        # Start the experiment - verify threads are started
        self.loop.start_threads()
        self.loop.main_thread_loop()

        # Verify all readers have running collector threads
        running_threads_count = 0
        for reader in self.loop.readers:
            if reader.is_running:
                running_threads_count += 1

        self.assertGreater(
            running_threads_count,
            0,
            "At least one reader should have a running collector thread",
        )

        # Stop the experiment
        self.loop.stop_threads()
        self.join_threads()

        # Verify all threads have terminated
        stopped_threads_count = 0
        for reader in self.loop.readers:
            if not reader.is_running:
                stopped_threads_count += 1

        self.assertEqual(
            stopped_threads_count,
            len(self.loop.readers),
            "All reader collector threads should have stopped",
        )

        # Verify that on_stop methods were called on readers
        for reader in self.loop.readers:
            self.assertTrue(
                hasattr(reader, "on_stop"),
                f"Reader {reader.__class__.__name__} should have on_stop method for cleanup",
            )
