"""
================================================================================
LabPilot GUI Binding System
================================================================================

This module implements a reactive GUI binding system that replaces tkinter's
variable classes with Qt-compatible alternatives. It provides shared, persistent
state management for GUI applications with automatic signal emission and
database persistence.

Key Features:
- Qt-compatible reactive variables with signal emission
- Persistent state across application sessions (saved to database)
- Thread-safe change notifications
- Automatic main instance management for multi-instance scenarios
- Support for global shared variables (Status) and saved variables (SavedBinding)
- Automatic cleanup and saving on application exit

Usage Pattern:
    class MyView(GUIParametrable, BindingSupport):
        @Binding
        def my_variable(cls) -> int:
            '''Definition of the variable. Returns the initial value.'''
            return 42

        @my_variable.onchange
        def __my_variable(self, value: int) -> None:
            '''Observer callback executed when the value changes.'''
            ...

================================================================================
"""

from copy import deepcopy
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Self,
    Type,
    TypeVar,
    TYPE_CHECKING,
    override,
)
import weakref

from typing_extensions import disjoint_base
import functools

from PySide6.QtCore import QObject, Signal

import logging

logger = logging.getLogger(__name__)

from labpilot.data_management.local_storage import LocalStorage
from labpilot.utils import threadSafe
from labpilot import config

if TYPE_CHECKING:
    import labpilot.GUI.mainGUI as mainGUI
    from labpilot.data_management.measurement_information import ParametrizedInfos

T = TypeVar("T")


class BindingNotInitializedError(Exception):
    pass


class BindingAlreadyInitializedError(Exception):
    pass


class BindingWithoutParentError(Exception):
    pass


class BindingNotInstantiatedError(Exception):
    pass


class BindingOverrideError(Exception):
    pass


# ============================================================================
# Qt variable replacement
# ============================================================================


class QtBindingVariable(QObject, Generic[T]):
    """
    Replacement for tkinter Variable classes.

    Provides Qt-compatible interface with signal emission for reactive updates.

    Attributes:
        valueChanged: Signal emitted whenever the value changes.

    Example:
        >>> var = QtBindingVariable(42)
        >>> var.valueChanged.connect(my_handler)
        >>> var.set(100)  # Emits valueChanged signal
        >>> var.get()    # Returns 100
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        value: T,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the Qt variable.

        Args:
            value: The initial value stored by this variable.
            parent: Parent QObject for Qt's object hierarchy.
        """
        super().__init__(parent)
        self._value = value

    def get(self) -> T:
        """Return the current value."""
        return self._value

    def set(self, value: T) -> None:
        """Set a new value and emit a change signal.

        Args:
            value: The new value to set.

        Note:
            The signal is only emitted if the value actually changes.
        """
        if self._value != value:
            self._value = value
            self.valueChanged.emit(value)


# ============================================================================
# Internal binding storage
# ============================================================================


class CBinding(Generic[T]):
    """
    Internal binding storage class.

    Encapsulates the value, Qt variable, and change notification logic for a binding.
    Separates storage concerns from the user-facing Binding descriptor.

    Attributes:
        _variable: QtBindingVariable for Qt signal emission.

    Example:
        >>> cb = CBinding(0, parent, MyClass, on_change)
        >>> cb.set(instance, 10)
        >>> cb.get()    # Returns 10
    """

    def __init__(
        self,
        initial_value: T,
        parent: QObject | None,
        owner_class: Type["BindingSupport"],
        onchange: Callable[[Any, T], None] | None,
    ) -> None:
        """Initialize the binding storage.

        Args:
            initial_value: The initial value for the binding.
            parent: Parent QObject for Qt's object hierarchy.
            owner_class: The class that owns this binding.
            onchange: Callback function to call when value changes.
        """
        self.__value = initial_value
        self.__onchange = onchange
        self.owner_class = owner_class

        if parent is not None:
            self.set_parent(parent)
        else:
            self._variable = None

    def set_parent(self, parent: QObject):
        """Register the Window that will be parent to the current Binding object"""
        self._variable = QtBindingVariable(self.__value, parent)
        self._variable.valueChanged.connect(self.__qt_change_handler__)

    def qt_variable(self) -> QtBindingVariable[T]:
        """Get the Qt variable for signal emission.

        Raises:
            BindingWithoutParentError: If called when the binding was created with no parent.
        """
        if self._variable is None:
            raise BindingWithoutParentError(
                "The Qt variable was requested before it was created."
            )

        return self._variable

    def __qt_change_handler__(self, value: T) -> None:
        """Internal handler for Qt variable change signals.

        Args:
            value: The new value received from the Qt variable.
        """
        self.__value = value

    def get(self) -> T:
        """Get the current value."""
        return self.__value

    def set(self, instance: Any, value: T) -> None:
        """Set a new value on this binding instance.

        Args:
            instance: The owner instance of this binding.
            value: The new value to set.

        Note:
            The onchange callback is only called if the value actually changes
            and an onchange callback is registered.
            The Qt variable is updated if a parent was provided.
        """
        if self.__value != value and self.__onchange is not None:
            onchange = threadSafe(self.__onchange)
            onchange(instance, value)

        self.__value = value

        if self._variable is not None:
            # update_variable = threadSafe(self.qt_variable().set)
            # update_variable(value)
            self.qt_variable().set(value)

    def set_signals(self, value: T) -> None:
        """Sets the value and calls the `onchange` of the main instance.

        This is a convenience method that uses the main instance to trigger
        callbacks, allowing consistent update behavior across all instances.

        Args:
            value: The new value to set.

        Example:
            >>> # Apply a value from saved state
            >>> my_binding.set_signals(saved_value)
        """
        self.set(self.owner_class.get_main_instance(), value)

    def _set(self, value: T) -> None:
        """Just set the value without triggering any change notifications.

        Args:
            value: The new value to set.

        Use Case:
            Internal state updates that should not trigger callbacks or GUI updates.
        """
        self.__value = value

        if self._variable is not None:
            self.qt_variable().set(value)


# ============================================================================
# Binding descriptor
# ============================================================================


def do_not_use_please(self):
    """Do not call this method directly. It will result in an error."""
    raise ReferenceError("You called a callback method. This is not allowed!")


@disjoint_base
class Binding(Generic[T]):
    """
    Creates a method decorator that creates a Binding value to the current class.

    A Binding value is a property that is unique and shared among all instances
    of a class. The default value and initial value of the property will be the
    value returned by the method.

    Architecture:
        - Binding is a descriptor that intercepts attribute access
        - When a class is subclassed, the decorator collects all @Binding methods
          and stores them in cls._bindings
        - On __init__, BindingSupport._instantiate_bindings() creates CBinding
          instances for all decorators
        - Access via getattr returns the CBinding instance for that owner

    Note:
        - In order for the decorator to work, the class holding the method must
          be a subclass of `BindingSupport`
        - The last value of a binding is remembered from one session to the other!
          It means that if you close the application, they will take the value
          they had before closing the application!

    Example:
        ```python
        class Test(BindingSupport):
            @Binding
            def IP(cls) -> str:
                '''Defines the IP address'''
                # The returned value will be the initial value of the variable.
                # Note: Once you close the application, the last value is saved and
                # restituted. So this value is only the initial value for the first
                # time the app is open!
                return "127.0.0.1"

            @IP.onchange
            def __IP(self, value: str) -> None:
                '''Observer callback executed when IP changes.

                Convention: use __IP naming pattern.
                Note: self.__IP will be inaccessible and set to `None`. The onchange
                mechanism is triggered automatically when setting a new value to
                self.IP.
                '''
                print(f"IP changed to {value}")

        # Usage:
        test = Test()
        print(test.IP)  # Returns CBinding with initial value "127.0.0.1"
        test.IP.set_signals("192.168.1.1")  # Sets IP, triggers onchange
        ```
    """

    def __init__(
        self,
        func: Callable[[Any], T],
        fonchange: Callable[[Any, T], None] | None = None,
        auto_save: bool = True,
        auto_db_save: bool = True,
    ) -> None:
        """Initialize a new Binding.

        Args:
            func: Definition of the variable. Must be a method returning the
                initial value. The method receives the instance as `cls` in its
                signature.
            fonchange: Function to execute if the value changes. See onchange()
                for adding this after initialization.
            auto_save: Indicates if this value is saved automatically as a parameter
                in the info.json file. Default: True.
            auto_db_save: Indicates if the value of this Binding must be saved in the
                local database and retrieved automatically. Default: True.

        Example:
            @Binding(auto_save=True, auto_db_save=True)
            def my_param(cls) -> float:
                return 1.5
        """
        functools.update_wrapper(self, func)

        self.func = func
        self.fonchange = fonchange
        self.auto_save = auto_save
        self.auto_db_save = auto_db_save
        self.__wrapped__ = func

    def onchange(
        self,
        fonchange: Callable[[Any, T], None],
    ):
        """Decorator to add an onchange callback.

        Code executed when the value of the `Binding` is changed.

        Note:
            - This method is called only once per class. Therefore, if many instances
            of a class is created, one of them will be set as 'main' and the others
            will just apply the changes decided by the main instance.
            - This method is called BEFORE the value in the `CBinding` is changed. Therefore, if you can access the old value by calling the `CBinding.get()` method

        Args:
            fonchange: The callback function to execute on value change.

        Example:
        ```python
            @Binding
            def my_value(cls) -> int:
                return 0

            @my_value.onchange
            def __my_value(self, value: int) -> None:
                print(f"Value changed to {value}") # New value
                print(f"Old value was:", self.my_value.get())
        ```
        Convention:
            Use __NAME pattern for onchange callbacks (e.g., __my_value).
        """
        self.fonchange = fonchange
        # setattr(fonchange, "__binding_callback__", True)
        functools.update_wrapper(do_not_use_please, fonchange)
        return None

    def create_variable(
        self,
        owner_class: Type["BindingSupport"],
        parent: QObject | None,
    ) -> None:
        """Creates the CBinding when the class is instantiated.

        This method should be called once per class (typically in BindingSupport._instantiate_bindings).

        Args:
            owner_class: The class that owns this binding.
            parent: Parent QObject for Qt's object hierarchy.

        Raises:
            BindingAlreadyInitializedError: If called multiple times on the same binding.
        """
        if hasattr(self, "_variable"):
            raise BindingAlreadyInitializedError(
                f"Property `{self.func.__name__}` has already been instantiated in class `{owner_class.__name__}`. "
                "You cannot call it again!"
            )

        local_storage = LocalStorage.main()

        # Retrieve saved value from database if available
        if local_storage.has_value(owner_class, self.func.__name__):
            default_value: T = local_storage.get(
                owner_class,
                self.func.__name__,
            )
        else:
            # Otherwise use the default from the method
            default_value = self.func(owner_class)

        # Create variable
        self._variable = CBinding(
            initial_value=default_value,
            parent=parent,
            owner_class=owner_class,
            onchange=self.fonchange,
        )

    def __get__(self, instance, owner) -> CBinding[T]:
        """Descriptor __get__ protocol.

        Returns the CBinding instance for the given owner class.

        Args:
            instance: The owner instance (not strictly used, but part of descriptor protocol).
            owner: The owner class.

        Raises:
            BindingNotInitializedError: If called before application initialization.
        """
        if not hasattr(self, "_variable"):
            raise BindingNotInitializedError(
                "You cannot call this variable before it has been instantiated. "
                "Please, make sure the main application windows was created before "
                "you call it. For example, the `__init__` function is NOT an appropriate location!"
            )

        return self._variable

    def __set__(self, instance, value: T) -> None:
        """Descriptor __set__ protocol.

        Sets the value on the binding, triggering callbacks.

        Args:
            instance: The owner instance.
            value: The new value to set.

        Raises:
            BindingNotInitializedError: If called before application initialization.
        """
        if not hasattr(self, "_variable"):
            raise BindingNotInitializedError(
                f"Binding accessed before application initialization ({instance.__class__.__name__})."
            )

        # self.set(instance, value)
        self._variable.set(instance, value)


# ============================================================================
# Status
# ============================================================================


class Status(Binding[T]):
    """
    A `Status` is a global shared variable.

    It behaves in the exact same way as a `Binding`, except that it is not saved
    in the parameters nor in the local storage for later retrieval.

    Usage:
        Use this for runtime state that should not be persisted across sessions.

    Attributes:
        auto_save: Always False (inherited from Binding).
        auto_db_save: Always False (inherited from Binding).

    Example:
        @Status
        def is_experiment_running(cls) -> bool:
            return False

        @is_experiment_running.onchange
        def __is_experiment_running(self, value: bool) -> None:
            if value:
                start_threads()
            else:
                stop_threads()
    """

    def __init__(
        self,
        func: Callable[[Any], T],
        fonchange: Callable[[Any, T], None] | None = None,
    ):
        super().__init__(
            func=func, fonchange=fonchange, auto_save=False, auto_db_save=False
        )


class SavedBinding(Binding[T]):
    """
    A `SavedBinding` is a global shared variable. It represents a parameter for the application.

    It behaves in the exact same way as a `Binding`, except that it is not saved
    in the parameters (info.json) but is saved in the local storage!
    Usage:
        Use this for variables that need persistence across sessions but should not appear in measurement parameter files.

    Attributes:
        auto_save: Always False (inherited from Binding).
        auto_db_save: Always True (inherited from Binding).

    Example:
        @SavedBinding
        def internal_counter(cls) -> int:
            return 0
    """

    def __init__(
        self,
        func: Callable[[Any], T],
        fonchange: Callable[[Any, T], None] | None = None,
    ):
        super().__init__(
            func=func, fonchange=fonchange, auto_save=False, auto_db_save=True
        )


# ============================================================================
# Decorator helper
# ============================================================================


# def binding(auto_save: bool = True):
#    def wrapper(func):
#        return Binding(func, auto_save=auto_save)
#
#    return wrapper


# ============================================================================
# BindingSupport
# ============================================================================


class BindingSupport:
    """
    Base class that provides automatic binding instantiation and management.

    All classes that use @Binding decorators must inherit from BindingSupport.
    The class collects all binding decorators and manages their lifecycle.

    Attributes:
        parametrables: Dictionary mapping class names to their BindingSupport instances.

    Lifecycle:
        1. Class definition: @Binding methods are collected in cls._bindings
        2. Instance creation: BindingSupport.__init__ sets up main instance tracking
        3. _setup() call: Creates all CBinding instances for the owner class
        4. Usage: Access bindings via getattr(instance, 'binding_name')
        5. Exit: Automatic saving of auto_db_save=True bindings

    Example:
        class MyView(BindingSupport):
            @Binding
            def my_param(cls) -> float:
                return 1.0

            def __init__(self, window):
                super().__init__()
                self._setup(window)  # Required!

            # Now self.my_param is accessible
            param = self.my_param
    """

    parametrables: Dict[str, "BindingSupport"] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        # @cython.cfunc
        # @classmethod
        # def init_subclass(cls) -> cython.void:
        """Class-level initialization.

        Collects all @Binding/@Status/@SavedBinding decorators from the class
        and its base classes into cls._bindings.

        Note:
            Decorators are collected in MRO order (from base to derived),
            with duplicates from base classes being deepcopied for each subclass.
        """

        def add_global_local(
            name: str,
            attr: Binding,
            base: Type,
        ):
            if base != cls:
                # Not the first definition of this binding
                copied = deepcopy(attr)
                setattr(cls, name, copied)
                return name, copied

            return name, attr

        cls._bindings = dict(
            add_global_local(name, attr, base)
            for base in reversed(cls.__mro__)
            for name, attr in base.__dict__.items()
            if isinstance(attr, Binding) and not hasattr(attr, "__binding_callback__")
        )

        cls.__binding_instantiated__ = False
        cls.__main_instance__ = None

    def __init__(self) -> None:
        """Instance-level initialization.

        Sets up the main instance tracking and registers the class in the
        parametrables dictionary for later lookup.
        """
        super().__init__()
        self.window = None

        # When the class is destroyed, it performs cleaning and saving of Binding values
        self._finalizer = weakref.finalize(
            self,
            self._on_exit,
        )

        BindingSupport.parametrables[self.__class__.__name__] = self

        # main instance management
        if self.__class__.__main_instance__ is None:
            self.set_main_instance()

        if not self.__class__.__binding_instantiated__:
            self._setup()

    def set_main_instance(self):
        """Sets the current object to be the main instance of the class.

        The main instance will receive the updates from the change bindings.
        In a multi-instance scenario (e.g., multiple readers), the first instance
        becomes the main instance and all subsequent instances delegate callback
        execution to it.

        Note:
            This is automatic - typically you should not call this method.
        """
        self.__class__.__main_instance__ = self

    @classmethod
    def get_main_instance(cls) -> Self:
        """Get the main instance of the class.

        Returns:
            The main instance that should receive callback updates.

        Raises:
            AttributeError: If no main instance has been set yet.
        """
        if cls.__main_instance__ is None:
            raise AttributeError(
                f"You must create an instance of `{cls.__module__}.{cls.__name__}` before calling this method"
            )
        return cls.__main_instance__

    def _on_exit(self) -> None:
        """Cleanup and save bindings when the object is destroyed.

        If we are not in simulation mode, saves the values for all bindings that
        must be saved in the local storage for later retrieval.

        Note:
            This is called automatically when the object is garbage collected
            via weakref.finalize.
        """
        if config.use_gui and not config.simulation and self.__binding_instantiated__:
            db = LocalStorage.main()

            for name, binding in self._bindings.items():
                if binding.auto_db_save:
                    value = getattr(self, name).get()
                    db.set(self, name, value)

    @classmethod
    def save_values(cls, infos: "ParametrizedInfos") -> None:
        """Saves the values for all Bindings with auto_save=True.

        This corresponds to all parameters of the application that should be
        included in the measurement info files.

        Args:
            infos: The ParametrizedInfos object to save parameters to.


        Raises:
            BindingNotInstantiatedError: If no instance of `BindingSupport` was initialized yet.

        Example:
            infos = ParametrizedInfos()
            MyView.save_values(infos)
        """
        if not cls.__binding_instantiated__:
            raise BindingNotInstantiatedError(
                f"You must create an instance of `{cls.__module__}.{cls.__name__}` before you can call this method. You also need to `_setup()` the instance!"
            )
        for name, binding in cls._bindings.items():
            if binding.auto_save:
                value = getattr(cls, name).get()
                infos.set_parameter(cls, name, value)

    @classmethod
    def restore_values(cls, infos: "ParametrizedInfos") -> None:
        """Restores saved values from measurement info for all bindings.

        Loads previously saved values and applies them to all bindings with
        auto_db_save=True.

        Args:
            infos: The ParametrizedInfos object containing saved parameters.

        Raises:
            BindingNotInstantiatedError: If no instance of `BindingSupport` was initialized yet.

        Example:
            infos = ParametrizedInfos()
            infos.load("/path/to/measurement/info.json")
            MyView.restore_values(infos)
        """
        if not cls.__binding_instantiated__:
            raise BindingNotInstantiatedError(
                f"You must create an instance of `{cls.__module__}.{cls.__name__}` before you can call this method. You also need to `_setup()` the instance!"
            )
        for name, binding in cls._bindings.items():
            if infos.has_param(cls, name):
                value = infos.get_parameter(cls, name)
                # getattr(cls, name)._set(value)
                getattr(cls, name).set_signals(value)

    @classmethod
    def _instantiate_bindings(cls) -> None:
        """Creates all the CBinding instances for the current class.

        This method should be called once per instance in the __init__ method.
        It retrieves saved values from the database (if available) or uses
        the default values from the decorator methods.

        Note:
            This method is already called automatically by _setup(), so you
            typically don't need to call it directly.

        Example:
            def __init__(self, window):
                super().__init__()
                self._setup()  # Calls _instantiate_bindings internally
        """
        if cls.__binding_instantiated__:
            return

        cls.__binding_instantiated__ = True

        logger.debug(f"Instantiate bindings for " f"'{cls.__name__}'")

        for _, binding in cls._bindings.items():
            binding.create_variable(
                cls,
                None,
            )

    @classmethod
    def _setup(
        cls,
    ) -> None:
        """Setup the `Binding`s and create them.

        YOU MUST CALL THIS METHOD in your __init__! It is your responsibility!

        This method:
        1. Stores the window reference
        2. Calls _instantiate_bindings() which creates all CBinding instances
        3. Saves all auto_save=True values to the info file

        Args:
            window: The main GUI window instance. Used as parent for Qt variables.

        Example:
            class MyView(BindingSupport):
                @Binding
                def my_param(cls) -> int:
                    return 0

                def __init__(self, window):
                    super().__init__()
                    self._setup(window)  # Required!

                # Now self.my_param is accessible
                print(self.my_param.get())
        """
        cls._instantiate_bindings()

    def set_window(self, window: "mainGUI.MainWindow"):
        self.window = window
        self.setup_qt_events(window)

    def setup_qt_events(self, parent: QObject):
        """Setup the `Binding`s so that they will respond to QT signals."""
        for _, binding in self._bindings.items():
            binding._variable.set_parent(parent)
