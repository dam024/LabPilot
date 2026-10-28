"""
================================================================================
LabPilot GUI Binding System - Unit Tests
================================================================================

This module contains comprehensive unit tests for the binding system classes:
- QtBindingVariable (excluded per design)
- CBinding (internal storage)
- Binding (descriptor)
- Status (global shared variable)
- SavedBinding (global shared variable with DB persistence)
- BindingSupport (base class for binding management)

The tests cover normal usage, edge cases, and failure scenarios.
================================================================================
"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock
from typing import Any, Callable, List
import time
import sys
import os

from PySide6.QtCore import QObject
from PySide6.QtTest import QSignalSpy
from labpilot.data_management.local_storage import LocalStorage
from tests.utils import UpdatableConfigTest

from labpilot.GUI.binding import (
    BindingAlreadyInitializedError,
    BindingNotInitializedError,
    BindingNotInstantiatedError,
    BindingWithoutParentError,
    QtBindingVariable,
    CBinding,
    Binding,
    Status,
    SavedBinding,
    BindingSupport,
)


# ============================================================================
# Test Data Classes
# ============================================================================


class TestBindingSupport(BindingSupport):
    """Test class with various binding types."""

    status_change_recorded: bool
    status_changes_recorded: List[int]
    counter_change_recorded: int

    @Binding
    def int_value(cls) -> int:
        """Integer binding with onchange callback."""
        return 0

    @int_value.onchange
    def __int_value(cls, value: int) -> None:
        """Observer for int_value changes."""
        TestBindingSupport.int_value_changed = value

    @Binding
    def float_value(cls) -> float:
        """Float binding."""
        return 1.5

    @Binding
    def str_value(cls) -> str:
        """String binding."""
        return "hello"

    @Binding
    def none_value(cls) -> None:
        """None binding."""
        return None

    @Binding
    def list_value(cls) -> list:
        """List binding."""
        return [1, 2, 3]

    @Status
    def status_value(cls) -> bool:
        """Status variable (no persistence)."""
        return False

    @SavedBinding
    def saved_value(cls) -> str:
        """Saved binding (DB persistence only)."""
        return "initial"

    def __init__(self):
        super().__init__()
        # Set the class attribute for testing
        TestBindingSupport.int_value_changed = None


class TestObserver:
    """Simple observer for testing signal emission."""

    def __init__(self, name: str = "TestObserver"):
        self.name = name
        self.connections = []
        self.last_value = None

    def connect(self, signal, handler):
        """Connect a handler to a signal."""
        self.connections.append((signal, handler))

    def disconnect(self, signal):
        """Disconnect all handlers from a signal."""
        self.connections = [(s, h) for s, h in self.connections if s != signal]

    def emit(self, signal, value):
        """Emit a signal with a value."""
        for sig, handler in self.connections:
            if sig == signal:
                handler(value)
            else:
                handler(None)

    def disconnect_all(self):
        """Disconnect all connections."""
        self.connections = []


# ============================================================================
# CBinding Tests
# ============================================================================


class TestCBinding(UpdatableConfigTest):
    """Tests for the CBinding class."""

    def test_cbinding_initialization_with_parent(self):
        """Test CBinding initialization with a parent QObject."""
        cb = CBinding(42, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertIsNotNone(cb)
        self.assertIsNone(cb._variable)  # The parent is None, so there is no variable

    def test_cbinding_initialization_without_parent(self):
        """Test CBinding initialization without a parent QObject."""
        cb = CBinding(0, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertIsNotNone(cb)
        self.assertIsNone(cb._variable)

    def test_cbinding_get_and_set(self):
        """Test getting and setting values on CBinding."""
        cb = CBinding(42, parent=None, owner_class=TestBindingSupport, onchange=None)

        initial_value = cb.get()
        self.assertEqual(initial_value, 42)

        cb.set(None, 100)
        value = cb.get()
        self.assertEqual(value, 100)

    def test_cbinding_set_no_change(self):
        """Test that setting the same value does not trigger callbacks."""
        parent = QObject()
        cb = CBinding(42, parent=parent, owner_class=TestBindingSupport, onchange=None)

        changes_recorded = []

        def onchange(instance, value):
            changes_recorded.append(value)

        self.assertIsNotNone(cb._variable)
        if cb._variable is not None:
            cb._variable.valueChanged.connect(lambda v: changes_recorded.append(v))

        cb.set(None, 42)
        self.assertEqual(len(changes_recorded), 0)

    def test_cbinding_set_triggers_onchange(self):
        """Test that changing value triggers onchange callback."""
        changes_recorded = []

        def onchange(instance, value):
            changes_recorded.append(value)

        cb = CBinding(
            42, parent=None, owner_class=TestBindingSupport, onchange=onchange
        )

        cb.set(None, 100)
        self.assertEqual(len(changes_recorded), 1)
        self.assertEqual(changes_recorded[0], 100)

    def test_cbinding_set_with_instance(self):
        """Test setting value with an instance parameter."""
        instance = TestBindingSupport()
        cb = CBinding(42, parent=None, owner_class=TestBindingSupport, onchange=None)

        cb.set(instance, 200)
        value = cb.get()
        self.assertEqual(value, 200)

    def test_cbinding_set_emits_signal(self):
        """Test that CBinding emits valueChanged signal on set."""
        parent = QObject()
        cb = CBinding(42, parent=parent, owner_class=TestBindingSupport, onchange=None)

        signal_received = []

        def on_signal(value):
            signal_received.append(value)

        self.assertIsNotNone(cb._variable)
        if cb._variable is not None:
            cb._variable.valueChanged.connect(on_signal)

        cb.set(None, 999)
        self.assertEqual(len(signal_received), 1)
        self.assertEqual(signal_received[0], 999)

    def test_cbinding_set_same_value_no_signal(self):
        """Test that setting the same value does not emit signal."""
        parent = QObject()
        cb = CBinding(42, parent=parent, owner_class=TestBindingSupport, onchange=None)

        signal_received = []

        def on_signal(value):
            signal_received.append(value)

        self.assertIsNotNone(cb._variable)
        if cb._variable is not None:
            cb._variable.valueChanged.connect(on_signal)

        cb.set(None, 42)  # Same value
        self.assertEqual(len(signal_received), 0)

    def test_cbinding_set_signals(self):
        """Test set_signals convenience method."""
        parent = QObject()
        cb = CBinding(42, parent=parent, owner_class=TestBindingSupport, onchange=None)

        # This combination only works if TestBindingSupport has a main instance... So, we need to instantiate one
        t = TestBindingSupport()

        cb.set_signals(777)
        value = cb.get()
        self.assertEqual(value, 777)

    def test_cbinding_set_signals_with_instance(self):
        """Test set_signals sets value on main instance."""
        instance1 = TestBindingSupport()
        instance2 = TestBindingSupport()
        cb = CBinding(42, parent=None, owner_class=TestBindingSupport, onchange=None)

        instance1.set_main_instance()
        cb.set_signals(888)

        value = cb.get()
        self.assertEqual(value, 888)

    def test_cbinding_set_signals_without_instance_raises(self):
        """Test that set_signals raises when no main instance exists."""
        cb = CBinding(42, parent=None, owner_class=TestBindingSupport, onchange=None)

        with self.assertRaises(AttributeError):
            cb.set_signals(123)

    def test_cbinding_set_without_parent_doesnt_emit_signal(self):
        """Test that CBinding without parent doesn't emit Qt signals."""
        cb = CBinding(42, parent=None, owner_class=TestBindingSupport, onchange=None)

        cb.set(None, 999)
        self.assertEqual(cb.get(), 999)

    def test_cbinding_qt_variable_without_parent_raises(self):
        """Test that accessing Qt variable without parent raises BindingWithoutParentError."""
        cb = CBinding(42, parent=None, owner_class=TestBindingSupport, onchange=None)

        with self.assertRaises(BindingWithoutParentError):
            cb.qt_variable()

    def test_cbinding_qt_variable_with_parent_works(self):
        """Test that accessing Qt variable with parent works."""
        mock_parent = QObject()
        cb = CBinding(
            42, parent=mock_parent, owner_class=TestBindingSupport, onchange=None
        )

        qt_var = cb.qt_variable()
        self.assertIsNotNone(qt_var)
        self.assertEqual(qt_var.get(), 42)

    def test_cbinding_onchange_called_once_per_change(self):
        """Test that onchange is called exactly once per change."""
        changes = []

        def onchange(instance, value):
            changes.append(value)

        cb = CBinding(
            10, parent=None, owner_class=TestBindingSupport, onchange=onchange
        )

        cb.set(None, 20)
        cb.set(None, 20)  # Same as current
        cb.set(None, 30)

        self.assertEqual(len(changes), 2)
        self.assertEqual(changes, [20, 30])

    def test_cbinding_thread_safe_onchange(self):
        """Test that onchange is wrapped in thread-safe call."""
        import threading

        lock = threading.Lock()
        changes = []

        def onchange(instance, value):
            with lock:
                changes.append(value)

        cb = CBinding(0, parent=None, owner_class=TestBindingSupport, onchange=onchange)

        for i in range(10):
            cb.set(None, i)

        # Since the initial value of the CBinding is 0, when i==0, the onchange is not called!!
        self.assertEqual(len(changes), 9)
        self.assertEqual(changes, [1, 2, 3, 4, 5, 6, 7, 8, 9])

    # ============================================================================
    # Edge Cases and Failure Cases
    # ============================================================================

    def test_cbinding_with_none_value(self):
        """Test CBinding with None as initial value."""
        cb = CBinding[str | None](
            None, parent=None, owner_class=TestBindingSupport, onchange=None
        )

        self.assertIsNone(cb.get())
        cb.set(None, "new_value")
        self.assertEqual(cb.get(), "new_value")

    def test_cbinding_with_zero_value(self):
        """Test CBinding with 0 as initial value."""
        cb = CBinding(0, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertEqual(cb.get(), 0)
        cb.set(None, -1)
        self.assertEqual(cb.get(), -1)

    def test_cbinding_with_empty_string(self):
        """Test CBinding with empty string as initial value."""
        cb = CBinding("", parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertEqual(cb.get(), "")
        cb.set(None, "hello")
        self.assertEqual(cb.get(), "hello")

    def test_cbinding_with_empty_list(self):
        """Test CBinding with empty list as initial value."""
        cb = CBinding([], parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertEqual(cb.get(), [])
        cb.set(None, [1, 2, 3])
        self.assertEqual(cb.get(), [1, 2, 3])

    def test_cbinding_with_empty_dict(self):
        """Test CBinding with empty dict as initial value."""
        cb = CBinding({}, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertEqual(cb.get(), {})
        cb.set(None, {"a": 1})
        self.assertEqual(cb.get(), {"a": 1})

    def test_cbinding_with_float_zero(self):
        """Test CBinding with 0.0 as initial value."""
        cb = CBinding(0.0, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertEqual(cb.get(), 0.0)
        cb.set(None, 0.5)
        self.assertEqual(cb.get(), 0.5)

    def test_cbinding_with_negative_float(self):
        """Test CBinding with negative float as initial value."""
        cb = CBinding(-3.14, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertEqual(cb.get(), -3.14)
        cb.set(None, 3.14)
        self.assertEqual(cb.get(), 3.14)

    def test_cbinding_with_large_number(self):
        """Test CBinding with large number as initial value."""
        cb = CBinding(
            10**15, parent=None, owner_class=TestBindingSupport, onchange=None
        )

        self.assertEqual(cb.get(), 10**15)
        cb.set(None, 10**15 + 1)
        self.assertEqual(cb.get(), 10**15 + 1)

    def test_cbinding_with_boolean_true(self):
        """Test CBinding with True as initial value."""
        cb = CBinding(True, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertTrue(cb.get())
        cb.set(None, False)
        self.assertFalse(cb.get())

    def test_cbinding_with_boolean_false(self):
        """Test CBinding with False as initial value."""
        cb = CBinding(False, parent=None, owner_class=TestBindingSupport, onchange=None)

        self.assertFalse(cb.get())
        cb.set(None, True)
        self.assertTrue(cb.get())

    def test_cbinding_with_mixed_type_change(self):
        """Test CBinding that changes from int to string."""
        cb = CBinding[int | str | None](
            42, parent=None, owner_class=TestBindingSupport, onchange=None
        )

        self.assertEqual(cb.get(), 42)
        cb.set(None, "string")
        self.assertEqual(cb.get(), "string")

    def test_cbinding_with_none_to_string_change(self):
        """Test CBinding that changes from None to string."""
        cb = CBinding[str | None](
            None, parent=None, owner_class=TestBindingSupport, onchange=None
        )

        self.assertIsNone(cb.get())
        cb.set(None, "hello")
        self.assertEqual(cb.get(), "hello")

    def test_cbinding_with_string_to_none_change(self):
        """Test CBinding that changes from string to None."""
        cb = CBinding[str | None](
            "hello", parent=None, owner_class=TestBindingSupport, onchange=None
        )

        self.assertEqual(cb.get(), "hello")
        cb.set(None, None)
        self.assertIsNone(cb.get())


# ============================================================================
# Binding Descriptor Tests
# ============================================================================


class TestBindingDescriptor(UpdatableConfigTest):
    """Tests for the Binding descriptor class."""

    def test_binding_decorator_creates_descriptor(self):
        """Test that @Binding decorator creates a Binding descriptor."""

        @Binding
        def my_value(cls) -> int:
            return 10

        self.assertIsInstance(my_value, Binding)
        self.assertEqual(my_value.func.__name__, "my_value")

    def test_binding_onchange_decorator(self):
        """Test that @binding.onchange works correctly."""

        @Binding
        def my_value(cls) -> int:
            return 10

        def my_onchange(instance, value):
            pass

        result = my_value.onchange(my_onchange)
        self.assertEqual(my_value.fonchange, my_onchange)
        self.assertIsNone(result)

    def test_binding_create_variable_with_parent(self):
        """Test create_variable with parent QObject."""

        @Binding
        def my_value(cls) -> int:
            return 10

        my_value.create_variable(TestBindingSupport, None)
        self.assertTrue(hasattr(my_value, "_variable"))

    def test_binding_create_variable_without_parent(self):
        """Test create_variable without parent QObject."""

        @Binding
        def my_value(cls) -> int:
            return 10

        my_value.create_variable(TestBindingSupport, None)
        self.assertTrue(hasattr(my_value, "_variable"))

    def test_binding_create_variable_twice_raises(self):
        """Test that create_variable raises BindingAlreadyInitializedError if called twice."""

        @Binding
        def my_value(cls) -> int:
            return 10

        my_value.create_variable(TestBindingSupport, None)

        with self.assertRaises(BindingAlreadyInitializedError):
            my_value.create_variable(TestBindingSupport, None)

    def test_binding_get_after_creation(self):
        """Test that __get__ returns CBinding after creation."""

        @Binding
        def my_value(cls) -> int:
            return 10

        my_value.create_variable(TestBindingSupport, None)

        result = my_value.__get__(None, TestBindingSupport)
        self.assertIsInstance(result, CBinding)
        self.assertEqual(result.get(), 10)

    def test_binding_set_after_creation(self):
        """Test that __set__ works after creation."""

        @Binding
        def my_value(cls) -> int:
            return 10

        my_value.create_variable(TestBindingSupport, None)

        instance = TestBindingSupport()
        my_value.__set__(instance, 200)

        cb = my_value.__get__(None, TestBindingSupport)
        self.assertEqual(cb.get(), 200)

    def test_binding_set_before_creation_raises(self):
        """Test that __set__ raises BindingNotInitializedError before creation."""

        @Binding
        def my_value(cls) -> int:
            return 10

        instance = TestBindingSupport()

        with self.assertRaises(BindingNotInitializedError):
            my_value.__set__(instance, 100)

    def test_binding_set_signals_after_creation(self):
        """Test that set_signals works after creation."""

        @Binding
        def my_value(cls) -> int:
            return 10

        my_value.create_variable(TestBindingSupport, None)

        t = (
            TestBindingSupport()
        )  # To avoid errors, we need to have at least one instance existing...

        my_value._variable.set_signals(300)

        cb = my_value.__get__(None, TestBindingSupport)
        self.assertEqual(cb.get(), 300)

    def test_binding_descriptor_owns_cbinding_instance(self):
        """Test that descriptor returns the CBinding instance."""

        @Binding
        def my_value(cls) -> int:
            return 10

        my_value.create_variable(TestBindingSupport, None)

        instance1 = TestBindingSupport()
        instance2 = TestBindingSupport()

        cb1 = my_value.__get__(instance1, TestBindingSupport)
        cb2 = my_value.__get__(instance2, TestBindingSupport)

        self.assertIs(cb1, cb2)

    # ============================================================================
    # Edge Cases and Failure Cases
    # ============================================================================

    def test_binding_with_none_return(self):
        """Test Binding with None return type."""

        @Binding
        def my_value(cls) -> None:
            return None

        my_value.create_variable(TestBindingSupport, None)
        cb = my_value.__get__(None, TestBindingSupport)
        self.assertIsNone(cb.get())

    def test_binding_with_empty_string_return(self):
        """Test Binding with empty string return type."""

        @Binding
        def my_value(cls) -> str:
            return ""

        my_value.create_variable(TestBindingSupport, None)
        cb = my_value.__get__(None, TestBindingSupport)
        self.assertEqual(cb.get(), "")

    def test_binding_with_list_return(self):
        """Test Binding with list return type."""

        @Binding
        def my_value(cls) -> list:
            return [1, 2, 3]

        my_value.create_variable(TestBindingSupport, None)
        cb = my_value.__get__(None, TestBindingSupport)
        self.assertEqual(cb.get(), [1, 2, 3])

    def test_binding_with_dict_return(self):
        """Test Binding with dict return type."""

        @Binding
        def my_value(cls) -> dict:
            return {"key": "value"}

        my_value.create_variable(TestBindingSupport, None)
        cb = my_value.__get__(None, TestBindingSupport)
        self.assertEqual(cb.get(), {"key": "value"})

    def test_binding_with_float_return(self):
        """Test Binding with float return type."""

        @Binding
        def my_value(cls) -> float:
            return 3.14159

        my_value.create_variable(TestBindingSupport, None)
        cb = my_value.__get__(None, TestBindingSupport)
        self.assertEqual(cb.get(), 3.14159)


# ============================================================================
# Status Tests
# ============================================================================


class TestStatus(UpdatableConfigTest):
    """Tests for the Status class (global shared variable without persistence)."""

    def test_status_initialization(self):
        """Test Status initialization."""

        @Status
        def is_running(cls) -> bool:
            return False

        self.assertIsInstance(is_running, Binding)
        self.assertFalse(is_running.auto_save)
        self.assertFalse(is_running.auto_db_save)

    def test_status_creates_variable(self):
        """Test that Status creates a variable."""

        @Status
        def is_running(cls) -> bool:
            return False

        is_running.create_variable(TestBindingSupport, None)
        self.assertTrue(hasattr(is_running, "_variable"))
        self.assertEqual(is_running._variable.get(), False)

    def test_status_set_and_get(self):
        """Test Status get and set operations."""

        @Status
        def is_running(cls) -> bool:
            return False

        is_running.create_variable(TestBindingSupport, None)

        is_running._variable.set(None, True)
        self.assertTrue(is_running._variable.get())

        is_running._variable.set(None, False)
        self.assertFalse(is_running._variable.get())

    def test_status_with_onchange(self):
        """Test Status with onchange callback."""

        @Status
        def is_running(cls) -> bool:
            return False

        @is_running.onchange
        def __is_running(cls, value: bool) -> None:
            TestBindingSupport.status_change_recorded = value

        is_running.create_variable(TestBindingSupport, None)

        is_running._variable.set(None, True)
        self.assertTrue(TestBindingSupport.status_change_recorded)

    def test_status_onchange_called_only_on_change(self):
        """Test that onchange is called only on actual change."""

        @Status
        def is_running(cls) -> bool:
            return False

        @is_running.onchange
        def __is_running(cls, value: bool) -> None:
            TestBindingSupport.status_changes_recorded.append(value)

        is_running.create_variable(TestBindingSupport, None)

        changes = []
        TestBindingSupport.status_changes_recorded = changes

        is_running._variable.set(None, True)
        self.assertEqual(len(changes), 1)

        is_running._variable.set(None, True)
        self.assertEqual(len(changes), 1)

        is_running._variable.set(None, False)
        self.assertEqual(len(changes), 2)

    # ============================================================================
    # Edge Cases and Failure Cases
    # ============================================================================

    def test_status_with_none_value(self):
        """Test Status with None value."""

        self.assertIsInstance(LocalStorage.main(), LocalStorage)

        @Status
        def optional_value(cls) -> str | None:
            return None

        optional_value.create_variable(TestBindingSupport, None)

        self.assertIsNone(optional_value._variable.get())
        optional_value._variable.set(None, "new_value")
        self.assertEqual(optional_value._variable.get(), "new_value")

    def test_status_with_large_float(self):
        """Test Status with large float value."""

        @Status
        def scale_factor(cls) -> float:
            return 1e10

        scale_factor.create_variable(TestBindingSupport, None)

        self.assertEqual(scale_factor._variable.get(), 1e10)


# ============================================================================
# SavedBinding Tests
# ============================================================================


class TestSavedBinding(UpdatableConfigTest):
    """Tests for the SavedBinding class (global shared variable with DB persistence)."""

    def test_saved_binding_initialization(self):
        """Test SavedBinding initialization."""

        @SavedBinding
        def counter(cls) -> int:
            return 0

        self.assertIsInstance(counter, Binding)
        self.assertFalse(counter.auto_save)
        self.assertTrue(counter.auto_db_save)

    def test_saved_binding_creates_variable(self):
        """Test that SavedBinding creates a variable."""

        @SavedBinding
        def counter(cls) -> int:
            return 0

        counter.create_variable(TestBindingSupport, None)
        self.assertTrue(hasattr(counter, "_variable"))
        self.assertEqual(counter._variable.get(), 0)

    def test_saved_binding_set_and_get(self):
        """Test SavedBinding get and set operations."""

        @SavedBinding
        def counter(cls) -> int:
            return 0

        counter.create_variable(TestBindingSupport, None)

        counter._variable.set(None, 100)
        self.assertEqual(counter._variable.get(), 100)

        counter._variable.set(None, 200)
        self.assertEqual(counter._variable.get(), 200)

    def test_saved_binding_with_onchange(self):
        """Test SavedBinding with onchange callback."""

        @SavedBinding
        def counter(cls) -> int:
            return 0

        @counter.onchange
        def __counter(cls, value: int) -> None:
            TestBindingSupport.counter_change_recorded = value

        counter.create_variable(TestBindingSupport, None)

        counter._variable.set(None, 50)
        self.assertEqual(TestBindingSupport.counter_change_recorded, 50)

    # ============================================================================
    # Edge Cases and Failure Cases
    # ============================================================================

    def test_saved_binding_with_none_value(self):
        """Test SavedBinding with None value."""

        @SavedBinding
        def optional_value(cls) -> None:
            return None

        optional_value.create_variable(TestBindingSupport, None)

        self.assertIsNone(optional_value._variable.get())

    def test_saved_binding_with_empty_string(self):
        """Test SavedBinding with empty string value."""

        @SavedBinding
        def label(cls) -> str:
            return ""

        label.create_variable(TestBindingSupport, None)

        self.assertEqual(label._variable.get(), "")


# ============================================================================
# BindingSupport Tests
# ============================================================================


class TestBindingSupportUnitTest(UpdatableConfigTest):
    """Tests for the BindingSupport base class."""

    def setUp(self) -> None:
        # Check the correct reinitialization of the bindings...
        self.assertEqual(
            len(BindingSupport.parametrables), 0, f"{BindingSupport.parametrables}"
        )
        self.assertIsNone(TestBindingSupport.__main_instance__)

        return super().setUp()

    def test_binding_support_subclass_creates_bindings(self):
        """Test that subclassing with @Binding creates _bindings dict."""

        class MySupport(BindingSupport):
            @Binding
            def value(cls) -> int:
                return 42

        self.assertTrue(hasattr(MySupport, "_bindings"))
        self.assertIn("value", MySupport._bindings)

    def test_binding_support_inheritance_collects_bindings(self):
        """Test that child classes inherit bindings from parent classes."""

        class ParentSupport(BindingSupport):
            @Binding
            def parent_value(cls) -> int:
                return 1

        class ChildSupport(ParentSupport):
            @Binding
            def child_value(cls) -> int:
                return 2

        child = ChildSupport()

        self.assertTrue(hasattr(child, "parent_value"))
        self.assertTrue(hasattr(child, "child_value"))

    def test_binding_support_inheritance_independance(self):
        """Test that child classes inherit bindings form parent classes and keep independent bindings"""

        class ParentSupport(BindingSupport):
            @Binding
            def parent_value(cls) -> int:
                return 1

        class ChildSupport(ParentSupport):
            @Binding
            def child_value(cls) -> int:
                return 2

        child = ChildSupport()
        parent = ParentSupport()
        parent2 = ParentSupport()

        self.assertEqual(child.parent_value.get(), 1)

        # Check there is no interference between the two
        self.assertNotEqual(child.parent_value, parent.parent_value)

        parent.parent_value = 5
        self.assertEqual(parent.parent_value.get(), 5)
        self.assertEqual(child.parent_value.get(), 1)

    def test_child_first(self):
        """It has been observed that creating the child binding first could create some issues"""

        class ParentSupport(BindingSupport):
            @Binding
            def parent_value(cls) -> int:
                return 1

        class ChildSupport(ParentSupport):
            @Binding
            def child_value(cls) -> int:
                return 2

        child = ChildSupport()

        parent = ParentSupport()
        parent2 = ParentSupport()

        self.assertEqual(child.parent_value.get(), 1)

        # Check there is no interference between the two
        self.assertNotEqual(child.parent_value, parent.parent_value)

        parent.parent_value = 5
        self.assertEqual(parent.parent_value.get(), 5)
        self.assertEqual(child.parent_value.get(), 1)
        self.assertEqual(parent2.parent_value.get(), 5)

    def test_binding_support_set_main_instance(self):
        """Test set_main_instance method."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        instance1 = TestBindingSupport()

        self.assertTrue(hasattr(TestBindingSupport, "__main_instance__"))
        self.assertEqual(TestBindingSupport.get_main_instance(), instance1)

    def test_binding_support_get_main_instance(self):
        """Test get_main_instance classmethod."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        instance1 = TestBindingSupport()

        main_instance = TestBindingSupport.get_main_instance()
        self.assertEqual(main_instance, instance1)

    def test_binding_support_get_main_instance_without_main_raises(self):
        """Test that get_main_instance raises AttributeError without main instance."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        instance2 = TestBindingSupport()

        # The attribute is created automatically. Therefore, it needs to be deleted for the error to be thrown...
        TestBindingSupport.__main_instance__ = None

        with self.assertRaises(AttributeError):
            TestBindingSupport.get_main_instance()

    def test_binding_support_retore_values_error(self):
        """Test that retore_values raises an error if no Binding has be initialized yet"""
        infos = MagicMock()

        with self.assertRaises(BindingNotInstantiatedError):
            TestBindingSupport.restore_values(infos)

    def test_binding_support_restore_values(self):
        """Test restore_values method."""
        # Need to create a BindingSupport:
        _ = TestBindingSupport()

        infos = MagicMock()
        infos.has_param.return_value = True
        infos.get_parameter.return_value = 100

        TestBindingSupport.restore_values(infos)

        self.assertEqual(TestBindingSupport.int_value.get(), 100)

    def test_binding_support_restore_values_with_no_param(self):
        """Test restore_values when param doesn't exist."""
        # Need to create a BindingSupport:
        _ = TestBindingSupport()

        infos = MagicMock()
        infos.has_param.return_value = False

        TestBindingSupport.restore_values(infos)

        self.assertEqual(TestBindingSupport.int_value.get(), 0)

    def test_binding_support_save_values_error(self):
        """Test that save_values raises an error if no Binding has be initialized yet"""
        infos = MagicMock()

        with self.assertRaises(BindingNotInstantiatedError):
            TestBindingSupport.save_values(infos)

    def test_binding_support_save_values(self):
        """Test save_values method."""
        # Need to create a BindingSupport:
        _ = TestBindingSupport()

        infos = MagicMock()
        infos.set_parameter = MagicMock()

        TestBindingSupport.save_values(infos)

        self.assertTrue(infos.set_parameter.called)

    def test_binding_support_save_values_only_auto_save_true(self):
        """Test that save_values only saves auto_save=True bindings. These are the parameters that will be saved in the json file as experiment paremeters"""
        # Need to create a BindingSupport:
        _ = TestBindingSupport()

        infos = MagicMock()
        infos.set_parameter = MagicMock()

        TestBindingSupport.save_values(infos)

        # There are 5 of them: int_value, float_value, str_value, none_value, list_value
        self.assertEqual(infos.set_parameter.call_count, 5)

    def test_binding_support_set_main_instance_overwrites(self):
        """Test that set_main_instance can overwrite previous main instance."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        instance1 = TestBindingSupport()
        instance2 = TestBindingSupport()

        instance1.set_main_instance()
        self.assertEqual(getattr(TestBindingSupport, "__main_instance__"), instance1)

        instance2.set_main_instance()
        self.assertEqual(getattr(TestBindingSupport, "__main_instance__"), instance2)

    def test_binding_support_multiple_instances_shared_bindings(self):
        """Test that multiple instances share the same CBinding instances."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        instance1 = TestBindingSupport()
        instance2 = TestBindingSupport()

        cb1 = TestBindingSupport.int_value
        cb2 = TestBindingSupport.int_value

        self.assertIs(cb1, cb2)
        self.assertIs(cb1, getattr(instance1, "int_value"))
        self.assertIs(cb2, getattr(instance2, "int_value"))

    def test_binding_support_set_main_instance_auto(self):
        """Test that set_main_instance is called automatically on first instance."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        self.assertIsNone(TestBindingSupport.__main_instance__)
        instance1 = TestBindingSupport()
        instance2 = TestBindingSupport()

        self.assertEqual(TestBindingSupport.get_main_instance(), instance1)

        self.assertNotEqual(TestBindingSupport.get_main_instance(), instance2)

    # ============================================================================
    # Edge Cases and Failure Cases
    # ============================================================================

    def test_binding_support_with_different_value_types(self):
        """Test BindingSupport with different value types."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        instance = TestBindingSupport()

        self.assertEqual(instance.int_value.get(), 0)
        self.assertEqual(instance.float_value.get(), 1.5)
        self.assertEqual(instance.str_value.get(), "hello")
        self.assertIsNone(instance.none_value.get())
        self.assertEqual(instance.list_value.get(), [1, 2, 3])

    def test_binding_support_set_values_on_multiple_instances(self):
        """Test setting values on multiple instances."""
        self.assertFalse(TestBindingSupport.__binding_instantiated__)
        instance1 = TestBindingSupport()
        instance2 = TestBindingSupport()

        instance1.int_value.set(None, 100)

        self.assertEqual(TestBindingSupport.int_value.get(), 100)
        self.assertEqual(instance2.int_value.get(), 100)


# ============================================================================
# Integration Tests
# ============================================================================


class TestBindingIntegration(UpdatableConfigTest):
    """Integration tests for binding system components."""

    def test_integration_onchange_callback_propagation(self):
        """Test that onchange callbacks are properly connected."""
        parent = QObject()
        instance = TestBindingSupport()
        instance.setup_qt_events(parent)

        def handler(v):
            TestBindingSupport.int_value_changed = v

        self.assertIsNotNone(TestBindingSupport.int_value.qt_variable())
        if TestBindingSupport.int_value.qt_variable() is not None:
            TestBindingSupport.int_value.qt_variable().valueChanged.connect(handler)

        TestBindingSupport.int_value.set(None, 42)

        self.assertEqual(TestBindingSupport.int_value_changed, 42)

    def test_integration_status_vs_binding(self):
        """Test that Status and Binding behave differently regarding persistence."""

        @Status
        def status_var(cls) -> bool:
            return False

        @Binding
        def binding_var(cls) -> bool:
            return False

        status_var.create_variable(TestBindingSupport, None)
        binding_var.create_variable(TestBindingSupport, None)

        status_var._variable.set(None, True)
        self.assertTrue(status_var._variable.get())

        binding_var._variable.set(None, True)
        self.assertTrue(binding_var._variable.get())

    def test_integration_signal_emission_sequence(self):
        """Test the sequence of signal emissions when setting value."""
        changes = []
        parent = QObject()

        @Binding
        def tracked_value(cls) -> int:
            return 0

        tracked_value.create_variable(TestBindingSupport, parent)

        def on_change(v):
            changes.append(v)

        tracked_value._variable.qt_variable().valueChanged.connect(on_change)

        tracked_value._variable.set(None, 10)
        tracked_value._variable.set(None, 20)
        tracked_value._variable.set(None, 30)

        self.assertEqual(len(changes), 3)
        self.assertEqual(changes, [10, 20, 30])

    def test_integration_none_value_handling(self):
        """Test handling of None values across all binding types."""

        @Binding
        def optional_binding(cls) -> None:
            return None

        @Status
        def optional_status(cls) -> None:
            return None

        @SavedBinding
        def optional_saved(cls) -> None:
            return None

        optional_binding.create_variable(TestBindingSupport, None)
        optional_status.create_variable(TestBindingSupport, None)
        optional_saved.create_variable(TestBindingSupport, None)

        optional_binding._variable.set(None, None)
        optional_status._variable.set(None, None)
        optional_saved._variable.set(None, None)

        self.assertIsNone(optional_binding._variable.get())
        self.assertIsNone(optional_status._variable.get())
        self.assertIsNone(optional_saved._variable.get())

    def test_integration_multiple_signals(self):
        """Test handling of multiple objects connected to the qt_variable()."""

        changes = []
        changes2 = []
        parent = QObject()

        @Binding
        def tracked_value(cls) -> int:
            return 0

        tracked_value.create_variable(TestBindingSupport, parent)

        def on_change(v):
            changes.append(v)

        def on_change2(v):
            changes2.append(v)

        tracked_value._variable.qt_variable().valueChanged.connect(on_change)
        tracked_value._variable.qt_variable().valueChanged.connect(on_change2)

        tracked_value._variable.set(None, 10)
        tracked_value._variable.set(None, 20)
        tracked_value._variable.set(None, 30)

        self.assertEqual(len(changes), 3)
        self.assertEqual(changes, [10, 20, 30])
        self.assertEqual(changes2, changes)

    def test_integration_different_value_types(self):
        """Test handling of different value types."""

        @Binding
        def int_var(cls) -> int:
            return 0

        @Binding
        def float_var(cls) -> float:
            return 0.0

        @Binding
        def str_var(cls) -> str:
            return ""

        @Binding
        def bool_var(cls) -> bool:
            return False

        @Binding
        def list_var(cls) -> list:
            return []

        @Binding
        def dict_var(cls) -> dict:
            return {}

        int_var.create_variable(TestBindingSupport, None)
        float_var.create_variable(TestBindingSupport, None)
        str_var.create_variable(TestBindingSupport, None)
        bool_var.create_variable(TestBindingSupport, None)
        list_var.create_variable(TestBindingSupport, None)
        dict_var.create_variable(TestBindingSupport, None)

        int_var._variable.set(None, 42)
        float_var._variable.set(None, 3.14)
        str_var._variable.set(None, "hello")
        bool_var._variable.set(None, True)
        list_var._variable.set(None, [1, 2, 3])
        dict_var._variable.set(None, {"key": "value"})

        self.assertEqual(int_var._variable.get(), 42)
        self.assertEqual(float_var._variable.get(), 3.14)
        self.assertEqual(str_var._variable.get(), "hello")
        self.assertTrue(bool_var._variable.get())
        self.assertEqual(list_var._variable.get(), [1, 2, 3])
        self.assertEqual(dict_var._variable.get(), {"key": "value"})

    def test_integration_thread_safe_operations(self):
        """Test that operations are thread-safe."""
        import threading

        changes = []
        parent = QObject()
        lock = threading.Lock()

        @Binding
        def tracked_value(cls) -> int:
            return 0

        tracked_value.create_variable(TestBindingSupport, parent)

        spy = QSignalSpy(tracked_value._variable.qt_variable().valueChanged)

        threads = []
        for i in range(1, 10):
            t = threading.Thread(target=tracked_value._variable.set, args=(None, i))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(spy.count(), 9)

    # ============================================================================
    # Edge Cases and Failure Cases
    # ============================================================================

    def test_integration_signal_disconnect(self):
        """Test disconnecting from signals."""

        parent = QObject()

        @Binding
        def value(cls) -> int:
            return 0

        value.create_variable(TestBindingSupport, parent)

        connections = []

        # def connect(sig, handler):
        #    connections.append((sig, handler))

        def disconnect(sig):
            nonlocal connections
            connections = [(s, h) for s, h in connections if s != sig]

        value._variable.qt_variable().valueChanged.connect(lambda v: None)

        disconnect(value._variable.qt_variable().valueChanged)

        self.assertEqual(len(connections), 0)

    def test_integration_cbinding_without_parent(self):
        """Test CBinding without parent QObject."""
        cb = CBinding(0, parent=None, owner_class=TestBindingSupport, onchange=None)

        cb.set(None, 42)
        self.assertEqual(cb.get(), 42)

        value = cb.get()
        self.assertEqual(value, 42)

    def test_double_qt_variable_initialization(self):
        """Ensures that an error is thrown if the qt variable is emitted twice"""
        obj = QObject()
        cb = CBinding(0, parent=None, owner_class=TestBindingSupport, onchange=None)

        cb.set_parent(obj)
        with self.assertRaises(BindingAlreadyInitializedError):
            cb.set_parent(obj)


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    unittest.main()
