import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from labtools.GUI.mainGUI import (
    GUILogHandler,
    MainWindow,
)
from tests.utils import UpdatableConfigTest

from labtools import config


class TestGUILogHandler(UpdatableConfigTest):
    def test_emit_calls_log_area(self):
        handler = GUILogHandler()

        handler.logArea = MagicMock()
        handler.logArea.COLORS = {"INFO": "blue"}

        record = MagicMock()
        record.levelno = 20

        handler.format = MagicMock(return_value="INFO: test")

        handler.emit(record)

        handler.logArea.add_log.assert_called_once()


class TestMainWindow(UpdatableConfigTest):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "_window"):
            self._window.remove_log_handler()
        return super().tearDown()

    def create_window(self):
        view = MagicMock()
        view.name = "view1"
        view.all_graphs = []
        view.get_parametrables.return_value = []

        loop = MagicMock()
        loop.active_view = view

        self._window = MainWindow(
            [view],
            loop,
        )

        return self._window

    def test_initial_view(self):
        window = self.create_window()

        self.assertEqual(
            window.active_view.name,
            "view1",
        )

    def test_start_updates(self):
        window = self.create_window()

        window.mainGuiLoop.start_threads = MagicMock()

        window.start_updates()

        self.assertTrue(window.is_experiment_running)

        window.mainGuiLoop.start_threads.assert_called_once()

    def test_stop_updates(self):
        window = self.create_window()

        window.mainGuiLoop.stop_threads = MagicMock()

        window.is_experiment_running = True

        window.stop_updates()

        self.assertFalse(window.is_experiment_running.get())

        window.mainGuiLoop.stop_threads.assert_called_once()

    def test_update_all_plots(self):
        window = self.create_window()

        plot = MagicMock()

        window.plots = [plot]

        window.active_view.refresh_plots = MagicMock()

        window.update_all_plots()

        window.active_view.refresh_plots.assert_called_once()

        plot.update_plot.assert_called_once()

    @patch("labtools.GUI.mainGUI.QFileDialog.getExistingDirectory")
    @patch("labtools.GUI.mainGUI.RecordingInfos")
    def test_ask_recording_folder(
        self,
        infos_cls,
        dialog_mock,
    ):
        dialog_mock.return_value = config.output_dir_data

        window = self.create_window()

        window.status_interface = MagicMock()

        window.ask_recording_folder()

        infos_instance = infos_cls.return_value

        infos_instance.load.assert_called_once()
