from enum import Enum
from typing import Callable, Dict, Generic, Tuple, TypeVar, Type

from PySide6.QtCore import QMargins
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import Column, inspect

from labpilot.data_management.database_manager import Base, DB
from sqlalchemy.engine import default
from sqlalchemy.types import TypeEngine

Entity = TypeVar("Entity", bound=Base)


class LabelRole(Enum):
    title1 = "title1"
    largeTitle = "largeTitle"
    title2 = "title2"
    title3 = "title3"
    headline = "headline"
    body = "body"
    callout = "callout"
    subheadline = "subheadline"
    footnote = "footnote"
    caption1 = "caption1"
    caption2 = "caption2"

    @property
    def style(self) -> Tuple[str, str]:
        return ("textStyle", self._value_)


class EntityWidgetHelper(Generic[Entity]):
    def __init__(self, entity: Type[Entity]):
        self.entity = entity

    @property
    def entity_name(self):
        return self.entity.__name__

    @classmethod
    def default_widget_for_type(
        cls, type: TypeEngine, default_value=None
    ) -> QWidget | None:
        widget = QLineEdit()
        widget.setText(default_value or "")

        return widget

    @classmethod
    def get_column_default(cls, column: Column):
        if column.default:
            if not column.default.has_arg:
                raise Exception(f"No args... {column}")
            if column.default.is_scalar:
                return column.default.arg
            elif column.default.is_callable:
                return column.default.arg()
            else:
                raise Exception(f"Unhandled default for {column}: {column.default}")

        else:
            return None

    def get_widget_for_column(self, name: str, column: Column, value) -> QWidget | None:
        # Skip primary keys
        if column.primary_key:
            return None

        # Get type
        t = column.type

        return self.default_widget_for_type(t, value)

    def label_for_column(self, name: str, column: Column) -> str:
        return name.capitalize() + ": "

    def _make_widgets(self, parent: QWidget, title: str, is_insert: bool):
        # Layout
        layoutMain = QVBoxLayout(parent)
        layout = QFormLayout()

        # Title of the widget
        self.title = QLabel(title)
        self.title.setProperty(*LabelRole.title1.style)

        layoutMain.addWidget(self.title)

        # Session management
        session = DB.Session()
        if not is_insert:
            entity_instance = session.get(self.entity, self.entity_id)
        else:
            entity_instance = None

        # Add the widgets
        widgets: Dict[str, QWidget] = {}
        mapped_object = inspect(self.entity)
        for name, column in mapped_object.columns.items():
            # Get the value of the column
            if is_insert:
                value = self.get_column_default(column)
            else:
                value = getattr(entity_instance, name)

            # Get the widget from the column
            widget = self.get_widget_for_column(name, column, value=value)
            label = self.label_for_column(name, column)

            if widget and label:
                layout.addRow(label, widget)
                widgets[name] = widget

        # Close the session
        session.close()

        layoutMain.addLayout(layout)

        # Add the buttons
        layout_buttoms = QHBoxLayout()
        layoutMain.addLayout(layout_buttoms)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_wrapper(widgets))
        button_box.rejected.connect(self.cancel)

        layout_buttoms.addWidget(button_box)

    def create_gui(self, parent: QWidget | None = None) -> QWidget:
        # self.entity_instance = self.entity()
        self.entity_id = None
        widget = QWidget(parent)
        title = f"New {self.entity_name}"
        widget.setWindowTitle(title)
        # Create the widgets
        self._make_widgets(widget, title, True)

        return widget

    def update_gui(self, entity_id: int, parent: QWidget | None = None) -> QWidget:
        self.entity_id = entity_id
        widget = QWidget(parent)
        title = f"Edit {self.entity_name}"
        widget.setWindowTitle(title)
        # Create the widgets
        self._make_widgets(widget, title=title, is_insert=False)

        return widget

    def save_wrapper(self, widgets: Dict[str, QWidget]) -> Callable[[], None]:
        def save():
            with DB() as session:
                # defines if we need to save or insert
                if self.entity_id:
                    entity = session.get(self.entity, self.entity_id)
                else:
                    # Build
                    entity = self.entity()
                    session.add(entity)

                # Set the attributes
                for name, widget in widgets.items():
                    setattr(entity, name, widget.text())

                if self.entity_id is None:
                    session.flush()
                    self.entity_id = entity.id

        return save

    def cancel(self):
        pass


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import (
        QApplication,
    )
    from labtools.data_management.datamodel import Experiment, Measurement

    app = QApplication(sys.argv)

    with DB() as session:
        result = session.query(Experiment).all()

        factory = EntityWidgetHelper(Experiment)
        window = factory.create_gui()
        window.show()

        if len(result) > 0:
            window2 = factory.update_gui(result[0].id)
            window2.show()

    with open("src/labtools/GUI/style.qss", "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)
    app.exec()
