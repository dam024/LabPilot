# labpilot/analysis.py
# =============================================================================
# Data Analysis and View Management Module
# =============================================================================
#
# This module provides the core infrastructure for data analysis and visualization
# in the labpilot system. It enables a flexible, composable architecture for
# managing live data readers, data analysis, and plot generation.
#
# Key Concepts:
# -------------
# - **View**: A view defines what analyses should be performed and how they
#   are composed. Views are responsible for selecting the appropriate analysis
#   components for a given measurement type.
#
# - **DataAnalysis**: An abstract base class representing a single analysis
#   component. Each DataAnalysis manages a set of plots and is associated with
#   specific data readers.
#
# - **Reader Property System**: A custom property management system that
#   automatically handles reader assignment and property access. The `@reader`
#   decorator creates properties that hold references to specific LiveDataReader
#   instances.
#
# - **GraphSet**: Individual plot components that display processed data. Each
#   GraphSet manages its own data updates via `set_data()` and `update_data()`.
#
# Architecture Overview:
# ----------------------
# ```
# View (defines what analyses to use)
#     |
#     v
# [DataAnalysis] --[has]-> LiveDataReader
#     |                     (oscilloscope, laser, power meter, etc.)
#     v
# List[GraphSet] (plots)
# ```
#
# Usage Example:
# --------------
# ```python
# class MyView(View):
#     name: str = "My View"
#
#     def get_analysis(self) -> List[DataAnalysis]:
#         analysis = MyAnalysis()
#         analysis.plot_data.show = True  # Enable/disable plot
#         return [analysis]
# ```
#

from __future__ import annotations
from abc import abstractmethod
import functools
from types import ModuleType
from typing import TYPE_CHECKING, Callable, Any, Dict, List, Type
from labpilot.data_management.datamodel import Recording
import numpy as np
from PySide6.QtWidgets import QWidget


import logging

logger = logging.getLogger(__name__)

from labpilot.GUI.binding import Binding
from labpilot.GUI.objects import NumericalValueInput
import labpilot.utils as utils
import labpilot.DataReceiver as dr
import labpilot.plots.plots as plots
from labpilot.GUI.parameters import GUIParametrable, GUIParameter
from labpilot import globalState
import labpilot._tools.dynamic_imports as tools

if TYPE_CHECKING:
    import labpilot.GUI.mainGUI as mainGUI


# =============================================================================
# Reader Property System
# =============================================================================
#
# This section provides a custom property management system that enables
# type-safe, decorator-based reader assignment for DataAnalysis subclasses.
#
# The `_reader_property` class creates properties that automatically handle
# the assignment of LiveDataReader instances. When a property is accessed,
# the corresponding reader is retrieved from the readers list.


class _reader_property:  # type: ignore  # (property-like descriptor)
    """
    Internal class that provides property-like behavior for reader assignment.

    This class creates descriptors that:
    - Store a reference to a LiveDataReader instance
    - Support type annotations for better IDE support
    - Automatically handle property access via the `@reader` decorator

    Attributes:
        __is_reader__: Class attribute marking this as a reader property.
        name: The property name (used for internal storage with underscore prefix).
        c: The class name of the reader type (from type annotations).
        value: The currently assigned LiveDataReader instance.

    Example:
        >>> class MyAnalysis(DataAnalysis):
        ...     @reader
        ...     def my_reader(self) -> LaserController:
        ...         return LaserController()
        >>> my_reader = MyAnalysis().my_reader  # Automatically retrieves the reader
    """

    __is_reader__ = True

    def __init__(
        self,
        func: Callable,
        name: str = "",
    ) -> None:
        """
        Initialize the reader property descriptor.

        Args:
            func: The function that defines the property. Its return type annotation
                is used to determine the expected reader type.
            name: The property name (used for internal storage).
        """
        self.name = name
        return_type = func.__annotations__["return"]
        if not isinstance(return_type, str):
            self.c: str = return_type.__name__
        else:
            self.c: str = return_type  # fget.__annotations__["return"]
        self.value: dr.LiveDataReader | None = None
        fget = self._return()
        # super().__init__(fget, fset, fdel, doc)
        # functools.update_wrapper(self, fget)

    def _return(self):
        """
        Create a getter function that retrieves the stored reader value.

        Returns:
            A wrapper function that returns self._<name> (the underscore-prefixed
            attribute storing the actual reader instance).
        """
        name = self.name

        def wrapper(self):
            return getattr(self, "_" + name)

        return wrapper

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        """
        Allow the descriptor to be called as a property getter.

        When used with the `@reader` decorator, this method returns the
        stored reader value (self.value).

        Returns:
            The reader value stored in self.value.
        """
        return self.value


def reader_property(name: str, *args: Any, **kwargs: Any) -> Callable:
    """
    Factory function for creating reader property descriptors.

    Args:
        name: The name of the property.
        *args, **kwargs: Additional arguments passed to _reader_property.

    Returns:
        A decorator factory that creates and returns a reader property.

    Example:
        >>> @reader_property("my_reader")
        ... def decorator_factory():
        ...     ...
    """

    def wrapper(*args: Any, **kwargs: Any):
        return _reader_property(*args, **kwargs, name=name)

    return wrapper


def reader[R: dr.LiveDataReader](func: Callable[[Any], R]) -> Callable[[Any], R]:
    """
    Decorator that creates a reader property from a function.

    This decorator wraps a function to create a property that automatically
    manages the assignment of LiveDataReader instances. When the property
    is accessed, the corresponding reader is retrieved from the readers list.

    Args:
        func: The function to decorate. Should have a return type annotation
            indicating the expected LiveDataReader type.

    Returns:
        A wrapped function that behaves as a property accessing the reader.

    Example:
        >>> @reader
        ... def laser_reader(self) -> LaserController:
        ...     return LaserController()

        The resulting `laser_reader` property will automatically be assigned
        a LaserController instance when set_readers() is called.

    Important:
        The decorated function's return type annotation determines which
        reader is assigned. For example:
        ```python
        @reader
        def my_reader(self) -> PowerMeter:
            ...
        ```
        This creates a property that will hold a PowerMeter instance.
    """

    # @property
    @functools.wraps(func)
    @reader_property(name=func.__name__)
    @functools.wraps(func)
    def wrapper(self) -> Any:
        return ""

    return wrapper


# =============================================================================
# DataAnalysis Class
# =============================================================================
#
# Abstract base class representing a single data analysis component.
#
# A DataAnalysis instance manages:
# - A list of GraphSet objects (plots to display)
# - A list of associated LiveDataReader instances
# - Methods for refreshing plots and processing data
#
# Each subclass must:
# - Implement refresh_plots() to update plots with new data
# - Optionally define reader properties using the @reader decorator
# - Set the 'graphs' property to define which plots to display


class DataAnalysis(GUIParametrable):
    """
    Abstract base class for data analysis components.

    This class provides the infrastructure for managing data visualization
    components. Each DataAnalysis instance:
        - Contains a list of GraphSet objects (self.graphs)
        - Manages associated LiveDataReader instances through properties
        - Provides methods for refreshing plots and processing data
        - Supports dynamic reader assignment via the _readers dictionary

    Attributes:
        graphs: List of GraphSet objects to display in this analysis.
        _readers: Dictionary mapping reader property names to their descriptors.
        readers: List of associated LiveDataReader instances (populated via set_readers()).

    Subclass Responsibilities:
        1. Implement `refresh_plots()` to update plot data
        2. Define reader properties using the `@reader` decorator
        3. Initialize `graphs` with appropriate GraphSet instances

    Example:
        >>> class LaserTransmissionAnalysis(DataAnalysis):
        ...     graphs: List[plots.GraphSet] = []
        ...     def __init__(self):
        ...         self.plot_ch1 = plots.SimplePlot(...)
        ...         self.plot_ch2 = plots.MaximizationPlot(...)
        ...         self.graphs.append(self.plot_ch1)
        ...         self.graphs.append(self.plot_ch2)
        ...
        ...     @reader
        ...     def laser_reader(self) -> LaserController:
        ...         return LaserController()
        ...
        ...     @reader
        ...     def oscilloscope_reader(self) -> OscilloscopeReader:
        ...         return OscilloscopeReader()
        ...
        ...     def refresh_plots(self):
        ...         # Update plots with data from readers
        ...         pass

    Note:
        The reader property system uses underscore-prefixed internal attributes
        (e.g., _laser_reader) to store the actual reader instances. The decorated
        methods (e.g., laser_reader) act as property getters that access these
        internal attributes.
    """

    graphs: List[plots.GraphSet]

    def __init_subclass__(cls) -> None:
        """
        Subclass hook that automatically discovers and registers reader properties.

        This method scans the class MRO (Method Resolution Order) for all
        _reader_property instances and stores them in cls._readers. This enables
        the reader system to work even when readers are defined in parent classes.

        The MRO is traversed in reverse order (from base to derived) to ensure
        that more specific reader definitions take precedence.

        Example:
            If class A inherits from B, and both define reader properties:
            - B._readers will contain readers from A
            - A._readers will contain readers from A and B
        """
        super().__init_subclass__()

        # Get all the readers, taking into account the parent classes
        cls._readers = {
            name: attr  # .fget()
            for base in reversed(cls.__mro__)
            if issubclass(base, DataAnalysis)  # To avoid going too far...
            for name, attr in base.__dict__.items()
            if isinstance(attr, _reader_property)
        }

        # print(f"Readers for: {cls.__name__}")
        # for name, reader in cls._readers.items():
        #    print(f"\t{name}: {reader.c}")

    def __init__(self) -> None:
        """
        Initialize a DataAnalysis instance.

        Must be called after __init_subclass__ has registered all reader properties.

        Raises:
            AttributeError: If 'graphs' property is not defined.
        """
        self._check_for_property("graphs")
        self._make_attribute_instance("graphs", [])
        super().__init__()
        return

    def _add_readers_dependencies(
        self, existing_readers: List[Type[dr.LiveDataReader]]
    ):
        """
        Checks in the `existing_readers` if all the dependencies for this analysis are available.
        Adds them if necessary.

        Args:
            existing_readers: List of reader types that have already been added.

        Returns:
            List[Type[dr.LiveDataReader]]: The updated list including this analysis's readers.

        Raises:
            RuntimeError: If a reader property is not a subclass of LiveDataReader.

        Example:
            >>> existing_readers = [OscilloscopeReader]
            >>> existing_readers = analysis._add_readers_dependencies(existing_readers)
            >>> assert PowerMeterReader in existing_readers
        """
        module_str = self.__module__

        for name, reader in self._readers.items():
            # Loads the class
            # print(module_str, reader.c, reader.name)

            r: Type[Any] = tools.dynamic_obj_import(module_str, reader.c)
            if not issubclass(r, dr.LiveDataReader):
                raise RuntimeError(
                    f"Cannot use the `reader` decorator property if the return type is not of type `LiveDataReader`. Property `{name}` of class `{self.__class__.__name__}`"
                )
            if r not in existing_readers:
                existing_readers.append(r)

    def set_readers(self, readers: List[dr.LiveDataReader]):
        """
        Obtain the reader dependency from the given list and assigns it to its corresponding property.

        This method matches reader property types (from type annotations) with
        the actual LiveDataReader instances and assigns them appropriately.

        Args:
            readers: List of all available LiveDataReader instances.

        Example:
            >>> readers = [laser_reader, oscilloscope_reader, power_meter_reader]
            >>> analysis.set_readers(readers)
            >>> assert analysis.laser_reader is laser_reader
        """
        self.readers: List[dr.LiveDataReader] = []
        for name, prop in self._readers.items():
            # Get the correct reader
            found = False
            for r in readers:
                if r.__class__.__name__ == prop.c:
                    # Assign value to the property
                    prop.value = r
                    # Add update method to the reader
                    # r.update_methods.append(self._update_data_wrapper(name))
                    self.readers.append(r)
                    found = True
                    break

            if not found:
                raise RuntimeError(f"Not found {prop} in {readers}")

    def has_reader_dep(self, reader: dr.LiveDataReader) -> bool:
        """
        Returns a boolean indicating whether the given reader is a dependency of the current `DataAnalysis`.

        Args:
            reader: The reader instance to check.

        Returns:
            True if the reader is assigned to one of this analysis's reader properties, False otherwise.

        Example:
            >>> assert analysis.has_reader(laser_reader)
            >>> assert not analysis.has_reader(invalid_reader)
        """
        return reader in self.readers

    def _update_data_wrapper_deprecated(
        self, property_name: str
    ) -> Callable[[np.ndarray], None]:
        """
        DEPRECATED: Creates a wrapper function that calls a property's process_data method.

        Args:
            property_name: Name of the property (without the reader suffix).

        Returns:
            A wrapper function that takes raw data and calls the corresponding
            process_data method on the property.

        Example:
            >>> def process_data(data):
            ...     self._current_data.process_data(data)
            >>> update_func = self._update_data_wrapper_deprecated("current")
            >>> update_func(data)  # Calls current.process_data(data)
        """
        func_name = property_name + "_" + "process_data"
        func = getattr(self, func_name)

        def wrapper(data: np.ndarray):
            func(
                data,
            )

        return wrapper

    def get_parameters(self, frame: QWidget, view: View | None) -> List[GUIParameter]:
        """
        Returns a list of GUI parameters for the DataAnalysis.

        Default implementation returns an empty list. Subclasses should override
        this method to provide custom parameters.

        Args:
            frame: The parent frame widget.
            view: The active view, if available.

        Returns:
            List[GUIParameter]: Empty list by default.

        Raises:
            NotImplementedError: If a subclass does not implement this method.
        """
        l: List[GUIParameter] = []
        return l

    def start(self, animate_plots: bool):
        """
        Starts the plots animation.

        Args:
            animate_plots: Whether to initialize animations. Animation is deprecated
                and should not be used in new implementations.

        Note:
            Animation support is deprecated. For new implementations, only
            initialize plots without animation.
        """

        # Init all the plots
        for plot in self.graphs:
            plot.init_plots()
            if animate_plots:
                plot.init_animation()

    @abstractmethod
    def refresh_plots(self):
        """
        Refresh all the plots with the correct data.

        This abstract method must be implemented by subclasses. It is responsible
        for updating all plots with the latest data from their associated readers.

        Args:
            None

        Returns:
            None

        Example:
            >>> def refresh_plots(self):
            ...     oscilloscope_data = self.oscilloscope_reader().get_data()
            ...     if oscilloscope_data is not None:
            ...         self.plot_ch1.set_data(oscilloscope_data.t, oscilloscope_data.ch1)
            ...         self.plot_ch2.set_data(oscilloscope_data.t, oscilloscope_data.ch2)
            ...         return super().refresh_plots()
        """

        # You can access the data from the readers using `self.reader().get_data()`
        # and then call the `update_data()` method from the corresponding `GraphSet` object
        pass

    def plot_generation(self, infos: Recording) -> List[plots.GraphSet]:
        """
        Allows for the generation of extra plots during the post processing.

        Args:
            infos: Measurement information for the current recording.

        Returns:
            List[plots.GraphSet]: Empty list by default. Override to return custom plots.
        """
        ## ToDo: Give the correct type to the infos parameter and adapt to the use case...
        return []


# =============================================================================
# View Class
# =============================================================================
#
# A View defines a set of DataAnalysis components that should be used together
# for a particular measurement type or visualization purpose.
#
# Each View:
# - Has a name that identifies it
# - Implements get_analysis() to return its DataAnalysis instances
# - Optionally defines refresh_delay for controlling plot update frequency
#
# Views are responsible for:
# - Defining which analyses to use (via get_analysis())
# - Configuring which plots to show (by setting GraphSet.show = True/False)
# - Providing GUI parameters for user control
#
# View lifecycle:
# 1. get_analysis() is called to create DataAnalysis instances
# 2. load_components() initializes the analyses
# 3. add_readers_dependencies() registers reader types
# 4. set_readers() assigns actual reader instances
# 5. refresh_plots() updates plots with new data


class View(GUIParametrable, tools.IgnorableClass):
    """
    Base class for measurement views that define data analysis components.

    A View is a container that organizes DataAnalysis instances for a specific
    measurement type or visualization purpose. Each View:
        - Has a `name` attribute for identification
        - Implements `get_analysis()` to define its analyses
        - Optionally supports a `refresh_delay` for controlling plot update rate
        - Loads components via load_components()

    Attributes:
        name: String identifier for the view.
        ignore: If True, this view will be ignored during recording/playback.
        refresh_delay: Time in seconds between plot updates. Can be a Binding.

    View Subclass Responsibilities:
        1. Implement `get_analysis()` to return a list of DataAnalysis instances
        2. Configure GraphSet.show flags to enable/disable specific plots
        3. Optionally implement `load_plot_data()` for loading saved data
        4. Optionally define `refresh_delay` property for automatic control

    Example:
        >>> class LaserView(View):
        ...     name: str = "Laser Infos"
        ...     ignore: bool = False
        ...
        ...     def get_analysis(self) -> List[DataAnalysis]:
        ...         transmission = LaserOnlyAnalysis()
        ...         transmission.plot_current.show = True
        ...         transmission.plot_temperature.show = True
        ...         transmission.plot_voltage.show = True
        ...         return [transmission]

    Lifecycle:
        >>> view = LaserView()
        >>> view.load_components()  # Creates analyses via get_analysis()
        >>> view.add_readers_dependencies([...])  # Registers reader types
        >>> view.set_readers([...])  # Assigns reader instances
        >>> view.refresh_plots()  # Updates plots

    See Also:
        - DataAnalysis: The base class for analysis components
        - measurement_procedure.MeasurementProcedure: A view that also performs measurements
    """

    name: str
    ignore: bool = False

    refresh_delay: float | Binding[float] | None = None

    __all_readers: List[dr.LiveDataReader]
    """List of all available `LiveDataReader`. It also contains the ones that are NOT present in the current view!"""

    def __init__(self) -> None:
        """
        Initialize a View instance.

        Calls parent initializer and loads components.

        Raises:
            AttributeError: If 'name' property is not defined.
        """
        self._check_for_property("name", str)
        self.title = self.name
        super().__init__()
        self.load_components()

    def _set_window(self, window: mainGUI.MainWindow):
        """
        Set the main window reference for this view.

        Args:
            window: The main window instance.

        Raises:
            NameError: If window module is not imported.
        """
        self._window = window

    def load_plot_data(self):
        """This method is called during simulation, when the data of the view must be loaded. This includes loading the plots of readers that are not DataStreamer"""
        logger.dev_warning("Need to implement this method")
        ## To Do: Each reader must have a `load` method. This load method will be responsible to load all the data saved during a recording. There will be two modes, controlled by a global parameter:
        #   - Show all data (= no stream) in each plot. The DataStreamer will load all the data that were saved for them and display everything in a single plot. No thread will be active
        #   - DataStreamers will stream the data (= like this is now). Threads for these readers will be active
        # In each cases, normal readers and measurement procedures will display their data and no thread will have to be run.
        # This modification requires to update the `MainLoop.regularize_threads` method to account for the new parameter

        if not globalState.stream_values:
            for reader in self.__all_readers:
                if self.has_reader(reader):
                    if (
                        isinstance(reader, dr.StreamDataReader)
                        or not reader.can_stream_data
                    ):
                        if not reader.has_data:
                            try:
                                reader.load_data()
                            except dr.NoDataError as e:
                                logger.error(
                                    f"No data is available for reader `{reader.__class__.__name__}`"
                                )
                    else:
                        # NOTE: This implementation should be close to the one for StreamDataReader. In fact, it should almost be the same, with only difference being the aggregation function (could even do all the same...).
                        # For now, I've implemented the StreamDataReader version, but maybe they should use the exact same method
                        logger.error("Unimplemented case...")
                        raise NotImplementedError(
                            "You must implement data loading for the `LiveDataReader`. Follow the instructions above for this!"
                        )

    @abstractmethod
    def get_analysis(self) -> List[DataAnalysis]:
        """Returns the different analysis required for the current View

        Note:
            This method is responsible for creating the different analysis

        Important:
            The data readers are NOT accessible from this method. They are added later
        """

    @property
    def all_graphs(self) -> List[plots.GraphSet]:
        """
        Returns all graphs from all analyses in the view that are enabled for display.

        Returns:
            List[plots.GraphSet]: All graphs where GraphSet.show is True.

        Example:
            >>> graphs = view.all_graphs
            >>> assert len(graphs) > 0
        """
        g: List[plots.GraphSet] = []
        # print(f"{self.__class__.__name__}:")

        for analysis in self.analysis:
            # for graph in analysis.graphs:
            # print(f"\t{graph.name}: {graph.show}")
            g += [graph for graph in analysis.graphs if graph.show]
        return g

    def get_parameters(self, frame: QWidget, view: "View | None") -> List[GUIParameter]:
        """
        Returns GUI parameters for the view.

        Creates a refresh delay slider if refresh_delay is defined but not bound
        in the view.

        Args:
            frame: The parent frame widget.
            view: The active view, if available.

        Returns:
            List[GUIParameter]: List of GUI parameters including refresh delay slider if applicable.
        """
        l: List[GUIParameter] = []
        if "refresh_delay" in self._bindings and self.refresh_delay is not None:
            slider_delay = NumericalValueInput(
                frame,
                from_=0.0,
                to=100.0,
                value=self.refresh_delay,
                text="Delay between samples [s]:",
                increment=0.1,
            )

            l.append(GUIParameter(slider_delay))
        return l

    def get_parametrables(self) -> List[GUIParametrable]:
        """
        Returns all parametrables for the view and its analyses.

        Note:
            Each instance must exist only once per array.

        Returns:
            List[GUIParametrable]: List of parametrables including the view,
                analyses, readers, and graphs.

        Raises:
            RuntimeError: If the view or an analysis is a LiveDataReader.
        """
        l: List[GUIParametrable] = []

        # Remark: Each instance must exist only once per array
        if not isinstance(self, DataAnalysis) and not isinstance(
            self, dr.LiveDataReader
        ):
            l.append(self)

        for analysis in self.analysis:
            l.append(analysis)
            l += analysis.readers
            l += [
                graph
                for graph in analysis.graphs
                if graph.show and isinstance(graph, GUIParametrable)
            ]
        return l

    def load_components(self):
        """
        Load the components required by the view.

        This method:
        - Calls get_analysis() to create DataAnalysis instances
        - Sets up the analyses for later reader assignment

        Raises:
            RuntimeError: If get_analysis() raises an exception.
        """
        # Load the analysis
        self.analysis = self.get_analysis()

        # Sets the readers to the analysis
        # self.readers = [reader() for reader in readers_types]

    def add_readers_dependencies(self, dependencies: List[Type[dr.LiveDataReader]]):
        """
        Returns all the readers being dependency of this View (= the analysis of this View).

        This method registers all reader types needed by the analyses in the
        view with the global dependencies list.

        Args:
            dependencies: List of reader types that have already been registered.

        Returns:
            List[Type[dr.LiveDataReader]]: The updated list including this view's readers.

        Example:
            >>> dependencies = [OscilloscopeReader]
            >>> dependencies = view.add_readers_dependencies(dependencies)
            >>> assert LaserController in dependencies
        """
        # Load the different readers required for the view
        for analysis in self.analysis:
            analysis._add_readers_dependencies(dependencies)

    def set_readers(self, readers: List[dr.LiveDataReader]):
        """
        Receives a list of all globally managed readers and sets them to the analyses.

        This method assigns actual reader instances to the reader properties of
        each analysis in the view.

        Args:
            readers: List of all available LiveDataReader instances.

        Raises:
            RuntimeError: If a reader property cannot find a matching reader instance.
        """
        self.__all_readers = readers
        for analysis in self.analysis:
            DataAnalysis.set_readers(analysis, readers)

    def has_reader(self, reader: dr.LiveDataReader) -> bool:
        """
        Returns a boolean indicating whether the given reader is a dependency of the current `View`.

        Args:
            reader: The reader instance to check.

        Returns:
            True if any analysis in the view has this reader assigned, False otherwise.

        Example:
            >>> assert view.has_reader(laser_reader)
            >>> assert not view.has_reader(invalid_reader)
        """
        for analysis in self.analysis:
            if analysis.has_reader_dep(reader):
                return True
        return False

    @classmethod
    def get_all_readers_dependencies(
        cls, views: "List[View]"
    ) -> List[Type[dr.LiveDataReader]]:
        """
        Returns all the readers found to be a dependency of at least one of the given view

        Args:
            views (List[View]): List of views to get the reader dependencies from

        Raises:
            AttributeError: If two views have the same name or are the same
        """
        # Get the readers dependencies. Additionnally, check that all readers have a unique name
        readers_names: Dict[str, View] = {}
        readers_types: List[Type[dr.LiveDataReader]] = []
        for view in views:
            view.add_readers_dependencies(readers_types)
            if view.name not in readers_names:
                readers_names[view.name] = view
            else:
                raise AttributeError(
                    f"Subclasses of `{View.__module__}.View` must have a unique name. `{readers_names[view.name].__class__.__module__}.{readers_names[view.name].__class__.__name__}` and `{view.__class__.__module__}.{view.__class__.__name__}` have the same name '{view.name}'"
                )

        return readers_types

    def refresh_plots(self):
        """
        Refreshes all the plots of the analysis.

        This method calls refresh_plots() on each analysis in the view, which
        updates all enabled plots with the latest data from their readers.

        Args:
            None

        Example:
            >>> view.refresh_plots()
            >>> # All enabled plots in all analyses are updated
        """
        for analysis in self.analysis:
            analysis.refresh_plots()


class EmptyView(View):
    """
    A placeholder view that returns no analyses.

    This class is provided for convenience when a view is needed but no
    analyses should be created.

    Example:
        >>> view = EmptyView()
        >>> view.get_analysis()  # Returns empty list
        >>> assert len(view.analysis) == 0
    """

    name: str = "--"

    def get_analysis(self) -> List[DataAnalysis]:
        """
        Returns an empty list of analyses.

        Returns:
            List[DataAnalysis]: Empty list.
        """
        return []
