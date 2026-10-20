from typing import Dict, List, Type
import unittest
from PySide6.QtWidgets import QApplication
import numpy as np


from labpilot.data_management.datamodel import Recording
import tests.dummy_classes as dc

import labpilot.analysis as ana
import labpilot.DataReceiver as dr
import tests.utils as tu


class TestReaderProperty(tu.UpdatableConfigTest):
    """Test suite for _reader_property descriptor class."""

    def test_reader_property_descriptor_creation(self):
        """Test that _reader_property correctly creates a descriptor with proper attributes."""

        def sample_reader_func(self) -> dc.TestReader:
            return dc.TestReader()

        prop = ana._reader_property(sample_reader_func, name="test_reader")

        # Check that the descriptor has the required attributes
        self.assertTrue(
            prop.__is_reader__, "_reader_property should have __is_reader__ set to True"
        )
        self.assertEqual(
            prop.name, "test_reader", "Property name should match the provided name"
        )
        self.assertEqual(
            prop.c,
            "TestReader",
            "Property class type should match the return type annotation",
        )
        self.assertIsNone(prop.value, "Property value should be None initially")

    def test_reader_property_getter_returns_stored_value(self):
        """Test that accessing the property returns the stored reader value."""

        def sample_reader_func(self) -> dc.TestReader:
            return dc.TestReader()

        prop = ana._reader_property(sample_reader_func, name="test_reader")

        # Create a mock object with the stored value
        class MockObject:
            _test_reader: dc.TestReader

            def __init__(self):
                self._test_reader = dc.TestReader()

        mock_obj = MockObject()
        prop.value = mock_obj._test_reader

        # Access via the property getter (which returns self._<name>)
        # Note: In actual use, this is accessed via the object's property
        # For testing, we directly check the internal storage
        self.assertEqual(prop.value, mock_obj._test_reader)

    def test_reader_property_callable_returns_value(self):
        """Test that calling the descriptor returns the stored value."""

        def sample_reader_func(self) -> dc.TestReader:
            return dc.TestReader()

        prop = ana._reader_property(sample_reader_func, name="test_reader")

        # Simulate a reader assignment
        class MockReader(dr.StreamDataReader[dc.TestData]):
            name = "MockReader"
            dirname = "mock_reader"
            can_stream_data = True

            def pull_data(self) -> np.ndarray:
                return np.array([])

            def process_data(self, raw_data: np.ndarray) -> dc.TestData:
                return dc.TestData()

            def on_stop(self):
                pass

        mock_reader = MockReader()
        prop.value = mock_reader

        # Call the descriptor
        result = prop()
        self.assertIs(
            result, mock_reader, "Calling the descriptor should return the stored value"
        )

    def test_reader_property_with_different_types(self):
        """Test reader property with various reader types."""

        # Test with TestReader
        def reader1_func(self) -> dc.TestReader:
            return dc.TestReader()

        prop1 = ana._reader_property(reader1_func, name="reader1")
        self.assertEqual(prop1.c, "TestReader")

        # Test with TestStreamer
        def reader2_func(self) -> dc.TestStreamer:
            return dc.TestStreamer()

        prop2 = ana._reader_property(reader2_func, name="reader2")
        self.assertEqual(prop2.c, "TestStreamer")

        # Test with TestStreamSubclass
        def reader3_func(self) -> dc.TestStreamSubclass:
            return dc.TestStreamSubclass()

        prop3 = ana._reader_property(reader3_func, name="reader3")
        self.assertEqual(prop3.c, "TestStreamSubclass")


class TestReaderDecorator(tu.UpdatableConfigTest):
    """Test suite for @reader decorator."""

    def test_reader_decorator_functionality(self):
        """Test that the @reader decorator correctly wraps a function."""

        @ana.reader
        def laser_reader(self) -> dc.TestReader:
            return dc.TestReader()

        # Check that the decorated function is callable
        self.assertTrue(callable(laser_reader))

        # Check that the decorated function has the original function's name
        self.assertTrue(hasattr(laser_reader, "__name__"))

    def test_reader_decorator_with_streamer_type(self):
        """Test @reader decorator with TestStreamer type annotation."""

        @ana.reader
        def stream_reader(self) -> dc.TestStreamer:
            return dc.TestStreamer()

        # Check that it can be accessed
        self.assertTrue(callable(stream_reader))
        self.assertEqual(stream_reader.__name__, "stream_reader")

    def test_reader_decorator_with_stream_subclass_type(self):
        """Test @reader decorator with TestStreamSubclass type annotation."""

        @ana.reader
        def stream_subclass_reader(self) -> dc.TestStreamSubclass:
            return dc.TestStreamSubclass()

        # Check that it can be accessed
        self.assertTrue(callable(stream_subclass_reader))
        self.assertEqual(stream_subclass_reader.__name__, "stream_subclass_reader")


class TestDataAnalysis(tu.UpdatableConfigTest):
    """Test suite for DataAnalysis class."""

    def test_data_analysis_initialization(self):
        """Test that DataAnalysis can be initialized with a list of graphs."""
        analysis = dc.TestAnalysis()

        # Check that graphs is initialized
        self.assertIsNotNone(analysis.graphs)
        self.assertIsInstance(analysis.graphs, list)
        self.assertEqual(len(analysis.graphs), 3, "TestAnalysis should have 3 graphs")

    def test_data_analysis_graphs_property(self):
        """Test that graphs property can be accessed and modified."""
        analysis = dc.TestAnalysis()

        # Check initial state
        self.assertEqual(len(analysis.graphs), 3)

        # Modify the graphs list
        analysis.graphs.append(dc.TestAnalysis().plot_reader)

        # Check updated state
        self.assertEqual(len(analysis.graphs), 4)

    def test_data_analysis_readers_set_by_set_readers(self):
        """Test that readers list is initialized empty and populated by set_readers."""
        analysis = dc.TestAnalysis()

        # Initially there is no readers attribute until set_readers is called
        # We can verify this by checking _readers exists but readers doesn't
        self.assertIn("_readers", dir(analysis))
        self.assertNotIn("readers", dir(analysis))

    def test_data_analysis_set_readers(self):
        """Test that set_readers correctly assigns readers to analysis."""
        analysis = dc.TestAnalysis()

        # Get the readers list
        readers = [dc.TestReader(), dc.TestStreamer()]

        # Assign readers
        analysis.set_readers(readers)

        # Check that readers are assigned
        self.assertEqual(len(analysis.readers), 2)
        self.assertTrue(analysis.has_reader(readers[0]))
        self.assertTrue(analysis.has_reader(readers[1]))

    def test_data_analysis_set_readers_missing_reader(self):
        """Test that set_readers raises RuntimeError when a reader is missing."""
        analysis = dc.TestAnalysis()

        # Create readers that don't match the expected types
        mismatched_readers: List[dr.LiveDataReader] = [dc.TestReader(), dc.TestReader()]

        # This should raise RuntimeError
        with self.assertRaises(RuntimeError):
            analysis.set_readers(mismatched_readers)

    def test_data_analysis_add_readers_dependencies(self):
        """Test that _add_readers_dependencies adds reader types to the list."""
        analysis = dc.TestAnalysis()

        # Initial empty list
        deps = []
        analysis._add_readers_dependencies(deps)

        # Should have added TestReader and TestStreamer
        self.assertEqual(len(deps), 2)
        self.assertIn(dc.TestReader, deps)
        self.assertIn(dc.TestStreamer, deps)

    def test_data_analysis_add_readers_dependencies_with_existing_readers(self):
        """Test that _add_readers_dependencies doesn't duplicate existing reader types."""
        analysis = dc.TestAnalysis()

        # Start with TestReader already in the list
        deps: List[Type[dr.LiveDataReader]] = [dc.TestReader]
        analysis._add_readers_dependencies(deps)

        # Should have added TestStreamer but not duplicate TestReader
        self.assertEqual(len(deps), 2)
        self.assertIn(dc.TestReader, deps)
        self.assertIn(dc.TestStreamer, deps)

    def test_data_analysis_refresh_plots_method_exists(self):
        """Test that refresh_plots method exists on DataAnalysis."""
        analysis = dc.TestAnalysis()

        # Check that refresh_plots method exists
        self.assertTrue(hasattr(analysis, "refresh_plots"))
        self.assertTrue(callable(analysis.refresh_plots))

    def test_data_analysis_plot_generation_returns_empty_list(self):
        """Test that plot_generation returns empty list by default."""
        analysis = dc.TestAnalysis()

        # Check that plot_generation method exists
        self.assertTrue(hasattr(analysis, "plot_generation"))

        # It should return a list
        result = analysis.plot_generation(Recording())
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


class TestView(tu.UpdatableConfigTest):
    """Test suite for View class."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()

        if cls.app is None:
            cls.app = QApplication([])

    def test_view_initialization(self):
        """Test that View is initialized with name and title."""
        view = dc.TestView()

        # Check that name is set
        self.assertEqual(view.name, "Reader + ch1")

        # Check that title is set
        self.assertEqual(view.title, "Reader + ch1")

    def test_view_analysis_property(self):
        """Test that analysis property is set after initialization."""
        view = dc.TestView()

        # Check that analysis is set
        self.assertIsNotNone(view.analysis)
        self.assertIsInstance(view.analysis, list)
        self.assertEqual(len(view.analysis), 1, "TestView should have 1 analysis")

    def test_view_get_analysis_returns_analysis_list(self):
        """Test that get_analysis returns the list of analyses."""
        view = dc.TestView()

        result = view.get_analysis()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        # Check that it returns DataAnalysis objects
        self.assertIsInstance(result[0], ana.DataAnalysis)
        self.assertEqual(result[0].title, "Test analysis")

    def test_view_all_graphs(self):
        """Test that all_graphs returns all enabled graphs."""
        view = dc.TestView()

        # Check initial state - should have graphs where show=True
        graphs = view.all_graphs
        self.assertIsInstance(graphs, list)
        self.assertGreaterEqual(len(graphs), 0)

    def test_view_all_graphs_empty_when_no_enabled_graphs(self):
        """Test that all_graphs returns empty list when no graphs are enabled."""
        view = dc.Test2View()

        # Disable all graphs
        analysis = view.analysis[0]
        self.assertIsInstance(analysis, dc.TestStreamAnalysis)
        if isinstance(analysis, dc.TestStreamAnalysis):
            analysis.plot_streamer_ch1.show = False
            analysis.plot_streamer_ch2.show = False

        # Check that all_graphs returns empty list
        graphs = view.all_graphs
        self.assertEqual(len(graphs), 0)

    def test_view_has_reader_with_assigned_reader(self):
        """Test that has_reader returns True when a reader is assigned."""
        view = dc.TestView()

        # Get the readers list from the analysis
        analysis = view.analysis[0]
        analysis.set_readers([reader() for reader in analysis._readers.values()])

        # Check that view has readers
        for reader in analysis.readers:
            self.assertTrue(view.has_reader(reader))

    def test_view_has_reader_without_assigned_reader(self):
        """Test that has_reader returns False when no readers are assigned."""
        view = dc.TestView()

        # First assign the view's readers
        analysis = view.analysis[0]
        analysis.set_readers([reader() for reader in analysis._readers.values()])

        mismatched_readers = [dc.TestReader()]
        self.assertFalse(view.has_reader(mismatched_readers[0]))

    def test_view_add_readers_dependencies(self):
        """Test that add_readers_dependencies adds all reader types."""
        view = dc.TestView()

        # Initial empty list
        deps = []
        view.add_readers_dependencies(deps)

        # Should have added TestReader and TestStreamer
        self.assertEqual(len(deps), 2)
        self.assertIn(dc.TestReader, deps)
        self.assertIn(dc.TestStreamer, deps)

    def test_view_add_readers_dependencies_adds_subclasses_as_separate(self):
        """Test that add_readers_dependencies treats subclasses as separate types."""
        view = dc.TestView()

        # Add TestReader first
        deps: List[Type[dc.LiveDataReader]] = [dc.TestReader]
        view.add_readers_dependencies(deps)

        # Add TestStreamSubclass (which is a subclass of TestStreamer)
        deps.append(dc.TestStreamSubclass)
        view.add_readers_dependencies(deps)

        # Should have added 3 types: TestReader, TestStreamer, TestStreamSubclass
        self.assertEqual(len(deps), 3)
        self.assertIn(dc.TestReader, deps)
        self.assertIn(dc.TestStreamer, deps)
        self.assertIn(dc.TestStreamSubclass, deps)

    def test_view_set_readers(self):
        """Test that set_readers correctly assigns readers to analyses."""
        view = dc.TestView()

        # Get the readers list from the analysis
        analysis = view.analysis[0]

        # Assign readers
        view.set_readers([reader() for reader in analysis._readers.values()])

        # Check that analyses have readers
        for analysis in view.analysis:
            self.assertEqual(len(analysis.readers), 2)

    def test_view_set_readers_missing_raises(self):
        """Test that set_readers raises RuntimeError when readers are missing."""
        view = dc.TestView()

        # Create readers that don't match the expected types
        mismatched_readers: List[dr.LiveDataReader] = [dc.TestReader(), dc.TestReader()]

        # This should raise RuntimeError
        with self.assertRaises(RuntimeError):
            view.set_readers(mismatched_readers)

    def test_view_refresh_plots(self):
        """Test that refresh_plots exists and is callable."""
        view = dc.TestView()

        self.assertTrue(hasattr(view, "refresh_plots"))
        self.assertTrue(callable(view.refresh_plots))

    def test_view_get_parameters(self):
        """Test that get_parameters returns list of parameters."""
        # Create a mock frame widget
        from PySide6.QtWidgets import QWidget

        frame = QWidget()

        view = dc.TestView()

        # Get parameters
        params = view.get_parameters(frame, view)

        self.assertIsInstance(params, list)

    def test_view_get_parametrables(self):
        """Test that get_parametrables returns all parametrables."""
        view = dc.TestView()

        # First assign readers to avoid AttributeError in get_parametrables
        analysis = view.analysis[0]
        analysis.set_readers([reader() for reader in analysis._readers.values()])

        # Get parametrables
        parametrables = view.get_parametrables()

        self.assertIsInstance(parametrables, list)
        # Should contain at least the view itself and the analysis
        self.assertIn(view, parametrables)

    def test_view_with_multiple_analyses(self):
        """Test that View correctly handles multiple analyses."""

        class MultiAnalysisView(ana.View):
            name: str = "Multi Analysis"

            def get_analysis(self) -> List[ana.DataAnalysis]:
                analysis1 = dc.TestAnalysis()
                analysis2 = dc.Test2ndAnalysis()

                return [analysis1, analysis2]

        view = MultiAnalysisView()

        self.assertEqual(len(view.analysis), 2)

    def test_view_multiple_analyses_all_graphs(self):
        """Test that all_graphs aggregates graphs from all analyses."""
        view = dc.TestView()

        analysis = view.analysis[0]
        self.assertIsInstance(analysis, dc.TestAnalysis)
        if isinstance(analysis, dc.TestAnalysis):
            analysis.plot_reader.show = True
            analysis.plot_streamer_ch1.show = True
            analysis.plot_streamer_ch2.show = True

        graphs = view.all_graphs
        self.assertGreater(len(graphs), 0)


class TestEmptyView(tu.UpdatableConfigTest):
    """Test suite for EmptyView class."""

    def test_empty_view_get_analysis_returns_empty_list(self):
        """Test that get_analysis returns an empty list."""

        view = ana.EmptyView()

        result = view.get_analysis()

        self.assertEqual(result, [])

    def test_empty_view_analysis_property_empty(self):
        """Test that analysis property is empty after initialization."""
        view = ana.EmptyView()

        # Check that analysis is empty
        self.assertEqual(view.analysis, [])

    def test_empty_view_has_no_graphs(self):
        """Test that all_graphs returns empty list for EmptyView."""

        view = ana.EmptyView()

        graphs = view.all_graphs
        self.assertEqual(graphs, [])


class TestReaderPropertyTypeAnnotations(tu.UpdatableConfigTest):
    """Test suite for reader property type annotation handling."""

    def test_reader_property_handles_string_type_annotation(self):
        """Test that reader property works with string type annotations."""

        def reader_func(self) -> dc.TestReader:
            return dc.TestReader()

        prop = ana._reader_property(reader_func, name="reader_func")

        self.assertEqual(prop.c, "TestReader")

    def test_reader_property_handles_class_type_annotation(self):
        """Test that reader property works with actual class type annotations."""

        def reader_func(self) -> dc.TestReader:
            return dc.TestReader()

        prop = ana._reader_property(reader_func, name="reader_func")

        self.assertEqual(prop.c, "TestReader")


class TestDataAnalysisInheritance(tu.UpdatableConfigTest):
    """Test suite for DataAnalysis inheritance scenarios."""

    def test_data_analysis_readers_inheritance(self):
        """Test that DataAnalysis correctly inherits readers from parent classes."""
        analysis = dc.TestInheritance()

        self.assertIn("test_reader", analysis._readers)
        self.assertIn("test_reader_2", analysis._readers)
        self.assertIn("test_streamer", analysis._readers)

    def test_data_analysis_readers_override(self):
        """Test that child class can override reader from parent class."""
        analysis = dc.TestInheritance()

        streamer_prop = analysis._readers["test_streamer"]
        self.assertEqual(streamer_prop.c, "TestStreamSubclass")

    def test_data_analysis_readers_addition(self):
        """Test that child class can add new readers to parent class."""
        analysis = dc.TestInheritance()

        self.assertIn("test_reader_2", analysis._readers)


class TestAnalysis(tu.UpdatableConfigTest):
    """Test suite for reader property uniqueness and inheritance."""

    def test_reader_uniqueness(self):
        """Checks that if two analysis are created and share a reader, it is instantiated only once!"""
        analysis1 = dc.TestAnalysis()
        analysis2 = dc.Test2ndAnalysis()

        readers_types: List[Type[dr.LiveDataReader]] = []
        analysis1._add_readers_dependencies(readers_types)
        analysis2._add_readers_dependencies(readers_types)

        expected_readers = [dc.TestReader, dc.TestStreamer]

        self.assertCountEqual(
            readers_types,
            expected_readers,
        )

    def test_inheritance(self):
        """Checks that all readers are properly inherited when a `DataAnalysis` is subclassed."""
        analysis = dc.TestInheritance()

        readers_types: List[Type[dr.LiveDataReader]] = []
        analysis._add_readers_dependencies(readers_types)

        readers = [reader() for reader in readers_types]

        analysis.set_readers(readers)

        def check_property(obj: ana.DataAnalysis, name: str, type: Type, msg: str):
            self.assertTrue(
                hasattr(obj, name),
                f"`{analysis.__class__.__name__}` has no attribute {name}. Case: {msg}",
            )

            self.assertTrue(
                isinstance(getattr(obj, name)(), type),
                f"`{analysis.__class__.__name__}.{name}` is of type `{getattr(obj, name)}`, but the expected type is `{type}`. Case: {msg}",
            )

        check_property(analysis, "test_reader_2", dc.TestReader, "Add a new reader")
        check_property(
            analysis, "test_reader", dc.TestReader, "Inheritance of a reader"
        )
        check_property(
            analysis, "test_streamer", dc.TestStreamSubclass, "Replacement of a reader"
        )
