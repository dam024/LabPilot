from __future__ import annotations

import logging
import os
from typing import Dict, List

# import matplotlib.pyplot as plt

from PySide6.QtCore import QMargins, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QMainWindow,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QScrollArea,
)

import labtools.analysis as ana
import labtools.MainLoopHandler as mainLoop
import labtools.GUI.internal_parameters as internal_params
from labtools.GUI.binding import Binding, Status, BindingSupport

from labtools.GUI.objects import GUILogArea, GraphCanvas

from labtools import logger, config, globalState
from labtools.data_management.local_storage import LocalStorage
from labtools.data_management.measurement_information import RecordingInfos

import labtools.utils as utils


class GUILogHandler(logging.StreamHandler):
    logArea: GUILogArea

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.INFO:
            msg = self.format(record)

            levelname = logging.getLevelName(record.levelno)
            color = self.logArea.COLORS.get(levelname, "black")

            self.logArea.add_log(
                message=msg,
                level=record.levelno,
                color=color,
            )


# --------------------------------------
# Main Loop Integration
# --------------------------------------
class MainGUILoop(mainLoop.MainLoop):
    control_plots_animation = False
    auto_start_threads = False
    run_main_thread = True

    def main_thread_loop(self):
        logger.info("Starting main GUI")

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        self.window = MainWindow(self.views, self)

        # utils._root = window
        utils._executor = utils.MainThreadExecutor(self.window)

        self.window.show()

        if self.run_main_thread:
            app.exec()


def combine_meta(*bases):
    return type("CombinedMeta", tuple(type(base) for base in bases), {})


# --------------------------------------
# Main Window
# --------------------------------------
class MainWindow(QMainWindow, BindingSupport):
    def __init__(self, views: List[ana.View], mainGUIloop: MainGUILoop):
        super().__init__()

        self.views = views
        for view in self.views:
            view._set_window(self)

        if len(self.views) > 0:
            self.active_view = mainGUIloop.active_view
        else:
            logger.warning(
                "No view found. Make sure you have declared a class and updated "
                "the `extra_code` in the configuration file! Additionally, "
                "check that the defined classes are not abstract."
            )
            self.active_view = ana.EmptyView()

        self.mainGuiLoop = mainGUIloop

        # Setup the bindigs
        self._setup(self)

        self.views_dic = {view.name: view for view in self.views}

        self.setWindowTitle("LabTools: Automatic measurement performance interface")
        self.resize(1200, 700)

        self.reset_plots_parametrables()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QHBoxLayout(self.central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar = self.build_sidebar()
        sidebar.setMinimumWidth(sidebar.minimumSizeHint().width())

        main_view = self.build_main_view()

        self.main_splitter.addWidget(sidebar)
        self.main_splitter.addWidget(main_view)

        sidebar_width = sidebar.sizeHint().width()
        # sidebar_width = sidebar.minimumSizeHint().width()

        self.main_splitter.setSizes([sidebar_width, self.width() - sidebar_width])

        layout.addWidget(self.main_splitter)

        self.plot_timer = QTimer(self)
        self.plot_timer.timeout.connect(self.update_all_plots)

        self.add_log_handler()

        # self.active_view_name = self.active_view.name
        self.update_active_view()  # Maybe not necessary

        self.build_menu()

        self.quit_shortcut = QShortcut(
            QKeySequence("Ctrl+Q"),
            self,
        )
        self.quit_shortcut.activated.connect(self.close)

    @Status
    def is_experiment_running(cls) -> bool:
        """Indicates if the experiment is running, i.e. if the readers are active and live plot update is running"""
        return False

    @is_experiment_running.onchange
    def __is_experiment_running(self, value: bool):
        if value:
            self.experiment_button_text = "Stop Experiments"
        else:
            self.experiment_button_text = "Start Experiments"

    @Status
    def experiment_button_text(cls) -> str:
        """Text shown in the Experiment Controller button"""
        return "Start Experiments"

    @Status
    def update_interval(cls) -> int:
        """Time [ms] between refresh of the plots"""
        return int(config.get("QT", "plot_refresh_rate"))

    @update_interval.onchange
    def __update_interval(self, value: int):
        if self.is_experiment_running:
            # self.plot_timer.start(value)
            self.plot_timer.setInterval(value)

    @Binding
    def active_view_name(cls) -> str:
        """Name of the view that is active"""
        return ""

    @active_view_name.onchange
    def __active_view_name(self, value: str):
        self.select_active_view(value)

    def select_active_view(self, view_name: str):
        """Set the `View` with name `view_name` active"""
        # self.active_view_name = view_name
        self.active_view = self.views_dic[view_name]

        self.mainGuiLoop.select_active_view(
            self.active_view,
            adapt_threads=self.is_experiment_running.get(),
        )

        self.update_active_view()

    def update_active_view(self):
        logger.info(f"Change active view to {self.active_view.name}")

        self.parameter_frame_view.setCurrentWidget(
            self.frame_parametrables[self.active_view.name]
        )

        self.plot_stacked_view.setCurrentWidget(self.frame_plots[self.active_view.name])

        self.plots = self.view_plots[self.active_view.name]

    def reset_plots_parametrables(self):
        self.plots = []

        self.default_parametrables = [
            internal_params.ApplicationParameters(
                update_interval=self.update_interval,
                active_view=self.active_view_name,
                is_experiment_running=self.is_experiment_running,
                experiment_button_text=self.experiment_button_text,
            )
        ]

    def closeEvent(self, event):
        self.on_close()
        super().closeEvent(event)

    def on_close(self):
        if not config.simulation:
            db = LocalStorage.main()
            db.set(
                self.mainGuiLoop,
                "active_view",
                self.active_view.name,
            )

        self.remove_log_handler()

        self.plot_timer.stop()

        # plt.close("all")
        for plot_list in self.view_plots.values():
            for plot in plot_list:
                plot.graph.close()

    def add_log_handler(self):
        """Adds a log handler to be able to show the logs on the small message box"""
        self.handler = GUILogHandler()
        self.handler.logArea = self.logArea
        formatter = logging.Formatter("%(levelname)s: %(message)s")

        self.handler.setFormatter(formatter)
        self.handler.setLevel(logger.get_level())

        logger.addHandler(self.handler)

    def remove_log_handler(self):
        logger.removeHandler(self.handler)

    # --------------------------------------------------
    # Sidebar
    # --------------------------------------------------
    def build_sidebar(self):
        main_widget = QWidget()

        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        main_widget.setLayout(layout)

        self.parameter_frame = QWidget()

        self.build_parameter_frame(self.parameter_frame)

        self.logArea = GUILogArea(self.parameter_frame)

        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(self.parameter_frame)
        splitter.addWidget(self.logArea.text)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        return main_widget

    def build_parameter_frame(self, parent: QWidget):
        parent_layout = QVBoxLayout(parent)
        parent_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        parent_layout.setContentsMargins(10, 0, 10, 0)

        general_infos = QFrame()
        general_layout = QVBoxLayout()
        general_infos.setLayout(general_layout)
        general_layout.setContentsMargins(0, 0, 0, 0)

        ###### Status interface (fix)
        self.status_interface = internal_params.StatusInterface()

        self.status_interface._setup(window=self)
        widget = self.status_interface.create_widget(frame=general_infos, view=None)

        general_layout.addWidget(widget)

        parent_layout.addWidget(general_infos)

        #### Scrollable area and movable widgets
        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)
        # Set scrollbar only vertically
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Remove default borders
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QStackedWidget()
        scroll_content.setContentsMargins(0, 0, 0, 0)

        self.frame_parametrables: Dict[str, QWidget] = {}

        for view in self.views:
            frame = QWidget()

            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame.setLayout(frame_layout)

            for param in self.default_parametrables + view.get_parametrables():
                param._setup(window=self)
                widget = param.create_widget(frame=frame, view=view)

                frame_layout.addWidget(widget)

            frame_layout.addStretch()

            scroll_content.addWidget(frame)

            self.frame_parametrables[view.name] = frame

        scroll_area.setWidget(scroll_content)
        self.parameter_frame_view = scroll_content

        parent_layout.addWidget(scroll_area)

    # --------------------------------------------------
    # Main plots
    # --------------------------------------------------
    def build_main_view(self):
        self.main_plot_frame = QWidget()

        layout = QVBoxLayout(self.main_plot_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        self.main_plot_frame.setLayout(layout)

        plots = self.build_plots(self.main_plot_frame)
        layout.addWidget(plots)

        return self.main_plot_frame

    def build_plots(self, parent: QWidget) -> QWidget:
        self.frame_plots: Dict[str, QWidget] = {}
        self.view_plots: Dict[str, List[GraphCanvas]] = {}

        self.plot_stacked_view = QStackedWidget(parent)
        self.plot_stacked_view.setContentsMargins(0, 0, 0, 0)

        for view in self.views:
            frame = QWidget(self.plot_stacked_view)

            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame_layout.setSpacing(0)
            frame.setLayout(frame_layout)

            self.view_plots[view.name] = []

            for graph in view.all_graphs:
                canvas = GraphCanvas(frame, graph)
                widget = canvas.get_widget()

                frame_layout.addWidget(widget)

                self.view_plots[view.name].append(canvas)

            self.frame_plots[view.name] = frame

            self.plot_stacked_view.addWidget(frame)

        return self.plot_stacked_view

    # --------------------------------------------------
    # Plot update
    # --------------------------------------------------
    def update_all_plots(self):
        try:
            self.active_view.refresh_plots()

            for plot in self.plots:
                plot.update_plot()

        except Exception as e:
            print(e)
            logger.error(
                f"An error occured while refreshing the plots. Plot update will be stopped: {e}"
            )
            self.plot_timer.stop()

    def stop_updates(self):
        logger.info("Stop experiments")

        self.is_experiment_running = False
        self.experiment_button_text = "Start Experiments"

        self.plot_timer.stop()

        self.mainGuiLoop.stop_threads()

    def start_updates(self):
        if self.is_experiment_running.get():
            return

        logger.info("Start experiments")

        self.mainGuiLoop.start_threads()

        self.is_experiment_running = True

        self.experiment_button_text = "Stop Experiments"

        self.plot_timer.start(self.update_interval.get())

    def ask_recording_folder(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select the folder containing the recording",
            config.output_dir_data,
        )

        if not path:
            return

        self.on_change_recording(path)

    def on_change_recording(self, new_path: str):
        """Code that must be executed each time the recording folder is changed (i.e. if we change the source of data) in simulation mode"""

        # Set the recording folder
        self.status_interface.recording = os.path.relpath(
            new_path,
            config.output_dir_data,
        )

        self.mainGuiLoop.clear_readers_data()

        self.mainGuiLoop.reload_readers_data()

        # Load the parameters
        infos = RecordingInfos()

        infos.load(
            new_path,
            apply_parameters=True,
        )

    # --------------------------------------------------
    # Menu
    # --------------------------------------------------
    def build_menu(self):
        menubar = self.menuBar()

        if config.simulation:
            simulation_menu = menubar.addMenu("Simulation Mode")

            action = QAction(
                "Select Recording Folder...",
                self,
            )

            action.triggered.connect(self.ask_recording_folder)

            simulation_menu.addAction(action)
