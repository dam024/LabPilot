import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QWidget

from labtools.GUI.parameters import (
    GUIParametrable,
)
from labtools.GUI.binding import (
    BindingNotInitializedError,
    BindingSupport,
    QtBindingVariable,
    CBinding,
    Binding,
)
import tests.utils as tu

# ----------------------------------------------------------------------------
# QApplication fixture
# ----------------------------------------------------------------------------

APP = QApplication.instance()

if APP is None:
    APP = QApplication([])


class DummyBinding(BindingSupport):
    pass


# ----------------------------------------------------------------------------
# QtBindingVariable
# ----------------------------------------------------------------------------


class TestQtBindingVariable(tu.UpdatableConfigTest):
    def test_get_initial_value(self):
        var = QtBindingVariable("abc")
        self.assertEqual(var.get(), "abc")

    def test_set_value(self):
        var = QtBindingVariable(10)
        var.set(22)

        self.assertEqual(var.get(), 22)

    def test_signal_emitted(self):
        var = QtBindingVariable(0)

        triggered = []

        var.valueChanged.connect(lambda value: triggered.append(value))

        var.set(42)

        self.assertEqual(triggered, [42])


# ----------------------------------------------------------------------------
# CBinding
# ----------------------------------------------------------------------------


class TestCBinding(tu.UpdatableConfigTest):
    def test_get_set(self):
        parent = QObject()
        binding = CBinding(
            initial_value=5, parent=parent, onchange=None, owner_class=DummyBinding
        )

        binding.set(None, 10)

        self.assertEqual(binding.get(), 10)

    def test_callback_called(self):
        callback = Mock()

        parent = QObject()

        binding = CBinding(
            initial_value=1,
            parent=parent,
            onchange=callback,
            owner_class=DummyBinding,
        )

        owner = object()

        binding.set(owner, 2)

        callback.assert_called_once_with(owner, 2)

    def test_no_callback_when_same_value(self):
        callback = Mock()

        parent = QObject()

        binding = CBinding(
            initial_value=1,
            parent=parent,
            onchange=callback,
            owner_class=DummyBinding,
        )

        binding.set(None, 1)

        callback.assert_not_called()


# ----------------------------------------------------------------------------
# Binding descriptor
# ----------------------------------------------------------------------------


class TestBinding(tu.UpdatableConfigTest):
    def test_access_before_initialization(self):
        class Test:
            @Binding
            def value(self):
                return 5

        obj = Test()

        with self.assertRaises(BindingNotInitializedError):
            _ = obj.value

    def test_create_variable(self):
        class Test:
            @Binding
            def value(self):
                return 123

        desc = Test.__dict__["value"]

        desc.create_variable(Test, QObject())

        self.assertEqual(desc._variable.get(), 123)


# ----------------------------------------------------------------------------
# GUIParametrable
# ----------------------------------------------------------------------------


class DummyParametrable(GUIParametrable):
    def __init__(self) -> None:
        self.title = "Test"
        super().__init__()

    @Binding
    def sample(self):
        return 10

    def get_parameters(self, frame, view):
        return []


class TestGUIParametrable(tu.UpdatableConfigTest):
    def test_binding_instantiation(
        self,
    ):
        obj = DummyParametrable()

        obj.window = QObject()

        obj._instantiate_bindings()

        self.assertEqual(obj.sample.get(), 10)

    def test_restore_values(
        self,
    ):
        class Infos:
            def has_param(self, cls, name):
                return True

            def get_parameter(self, cls, name):
                return 50

        obj = DummyParametrable()

        obj.window = QObject()
        obj._instantiate_bindings()

        DummyParametrable.restore_values(Infos())

        self.assertEqual(obj.sample.get(), 50)

    def test_create_widget_without_parameters(self):
        obj = DummyParametrable()

        obj.group_main = QWidget()

        frame = QWidget()

        obj.create_widget(frame, None)

        self.assertIsNotNone(obj.group_main)


# ----------------------------------------------------------------------------
# Full integration
# ----------------------------------------------------------------------------


class TestIntegration(tu.UpdatableConfigTest):
    def test_binding_round_trip(self):
        obj = DummyParametrable()

        obj.window = QObject()
        obj._instantiate_bindings()

        obj.sample.set(obj, 20)

        self.assertEqual(obj.sample.get(), 20)


if __name__ == "__main__":
    unittest.main()
