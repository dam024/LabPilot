import unittest
from unittest.mock import Mock, PropertyMock, patch

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtTest import QTest, QSignalSpy

from labpilot.GUI.binding import BindingSupport, CBinding
from labpilot.GUI.objects import (
    Combobox,
    NumericalValueInput,
    ButtonWidget,
    GUILogArea,
)
from tests.utils import UpdatableConfigTest


class DummyBinding(BindingSupport):
    pass


class TestQtWidgets(UpdatableConfigTest):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()

        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.parent = QWidget()
        super().setUp()

    # ----------------------------------
    # Combobox
    # ----------------------------------

    def test_combobox_initial_values(self):
        combo = Combobox(self.parent, "Items", ["A", "B", "C"], "A")

        self.assertEqual(combo.widget.count(), 3)

    def test_combobox_update_values(self):
        combo = Combobox(self.parent, "Items", ["A", "B"], "A")

        combo.update_values(["X", "Y", "Z"])

        self.assertEqual(
            combo.widget.count(),
            3,
        )

        self.assertEqual(
            combo.widget.itemText(0),
            "X",
        )

    # ----------------------------------
    # NumericalValueInput (integer)
    # ----------------------------------

    def test_integer_spinbox_updates_slider(self):
        widget = NumericalValueInput(
            self.parent,
            from_=0,
            to=100,
            value=50,
            text="Value",
        )

        widget.spinbox.setValue(80)

        self.assertEqual(
            widget.spinbox.value(),
            80,
        )

    def test_slider_updates_spinbox(self):
        widget = NumericalValueInput(
            self.parent,
            from_=0,
            to=100,
            value=0,
            text="Value",
        )

        widget.slider.setValue(1000)

        self.assertEqual(
            widget.spinbox.value(),
            100,
        )

    def test_value_signal_emitted(self):
        callback = Mock()

        parent = QObject()

        d = (
            DummyBinding()
        )  # We need to have at least one instantiated to allow normal usage...

        binding = CBinding(
            initial_value=1,
            parent=parent,
            onchange=callback,
            owner_class=DummyBinding,
        )

        widget = NumericalValueInput(
            self.parent,
            0,
            100,
            binding,
            "Value",
        )

        # Change the value
        spy = QSignalSpy(widget.spinbox.editingFinished)

        widget.spinbox.lineEdit().selectAll()
        QTest.keyClicks(widget.spinbox.lineEdit(), "42")
        QTest.keyClick(widget.spinbox.lineEdit(), Qt.Key.Key_Return)

        # Detect if the signal was launched
        self.assertEqual(spy.count(), 1)

        self.assertTrue(callback.called)
        self.assertEqual(widget.value(), 42)

        ## Change the value of the slider now
        callback.reset_mock()
        spy = QSignalSpy(widget.slider.sliderReleased)
        spy_changed = QSignalSpy(widget.slider.valueChanged)

        slider_rect = widget.slider.geometry()
        center_pos = QPoint(slider_rect.center())
        width = slider_rect.width()

        start_pos = QPoint(center_pos.x() - int(0.25 * width), center_pos.y())
        end_pos = QPoint(center_pos.x() + int(0.25 * width), center_pos.y())
        # print("Width: ", slider_rect.width(), center_pos)

        QTest.mousePress(widget.slider, Qt.MouseButton.LeftButton, pos=start_pos)
        QTest.mouseMove(widget.slider, pos=QPoint(center_pos.x() + 10, center_pos.y()))
        QTest.mouseRelease(widget.slider, Qt.MouseButton.LeftButton, pos=end_pos)

        self.assertGreaterEqual(spy_changed.count(), 1)
        self.assertTrue(callback.called)
        self.assertEqual(spy.count(), 1)

    # ----------------------------------
    # ButtonWidget
    # ----------------------------------

    def test_button_click_calls_action(self):
        action = Mock()

        button = ButtonWidget(
            self.parent,
            "Run",
            action,
        )

        QTest.mouseClick(
            button.get_widget(),
            Qt.MouseButton.LeftButton,
        )

        action.assert_called_once()

    # ----------------------------------
    # GUILogArea
    # ----------------------------------

    def test_add_log(self):
        log = GUILogArea(self.parent)

        log.add_log(
            level=20,
            message="Hello",
            color="green",
        )

        self.assertIn(
            "Hello",
            log.text.toPlainText(),
        )

    @patch("PySide6.QtWidgets.QMessageBox.critical")
    # @patch(
    #    "config.GeneralConfig.show_errors",
    #    new_callable=PropertyMock,
    #    return_value=True,
    # )
    def test_error_popup(
        self,
        # mock_show_errors,
        mock_critical,
    ):
        log = GUILogArea(self.parent)

        log.add_log(
            level=40,
            message="ERROR: failure",
            color="orangered",
        )

        mock_critical.assert_called_once()


if __name__ == "__main__":
    unittest.main()
