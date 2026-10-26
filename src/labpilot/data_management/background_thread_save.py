import os
from pathlib import Path
import queue
import time
from typing import Tuple, TypeGuard
import numpy as np
import threading

import logging

logger = logging.getLogger(__name__)

import labpilot._tools.utility_classes as uc


def is_save_action(
    tpl: Tuple[str, np.ndarray, str, bool] | Tuple[str, str, str]
) -> TypeGuard[Tuple[str, np.ndarray, str, bool]]:
    """Returns True if the element of the queue is a 'save' action"""
    return tpl[0] == "s"


def is_move_action(
    tpl: Tuple[str, np.ndarray, str, bool] | Tuple[str, str, str]
) -> TypeGuard[Tuple[str, str, str]]:
    """Returns True if the element of the queue is a 'move' action"""
    return tpl[0] == "mv"


class BackgroundSaveThread(uc.GlobalUniqueInstance):
    save_queue = queue.Queue[Tuple[str, np.ndarray, str, bool] | Tuple[str, str, str]]()

    def __init__(self) -> None:
        self.global_thread: threading.Thread | None = None
        self.global_thread_stop_event = threading.Event()
        BackgroundSaveThread.save_queue = queue.Queue[
            Tuple[str, np.ndarray, str, bool] | Tuple[str, str, str]
        ]()
        super().__init__()

    @property
    def is_running(self) -> bool:
        """Returns True if the save thread is running"""
        return self.global_thread is not None and self.global_thread.is_alive()

    def start(self):
        """Starts the save thread"""
        if self.global_thread is None:
            self.global_thread_stop_event.clear()
            self.global_thread = threading.Thread(target=self.global_background_thread)
            self.global_thread.start()

    def stop(self):
        """Request the save thread to stop

        All the files must have been saved for the thread to stop"""
        self.global_thread_stop_event.set()

    def join(self):
        if self.global_thread is not None:
            self.global_thread.join()

    @classmethod
    def addSaveAction(cls, data: np.ndarray, path: str, force: bool):
        """Add a 'save' action to the global thread. Use this to save data asynchronously!"""
        BackgroundSaveThread.save_queue.put(item=("s", data, path, force))

    @classmethod
    def addMoveAction(cls, from_: str | Path, to_: str | Path):
        """Add a 'move' action to the global thread to add move some folders/files asynchronously. This works jointly with `addSaveAction`."""
        BackgroundSaveThread.save_queue.put(item=("mv", str(from_), str(to_)))

    def global_background_thread(self):
        """This method handles a thread that will manage long run analysis for the different readers.

        For example, saving data takes a long time, so it will be handled here
        """
        while (
            not self.global_thread_stop_event.is_set()
            or not BackgroundSaveThread.save_queue.empty()
        ):
            self._global_thread_action()

            if BackgroundSaveThread.save_queue.empty():
                time.sleep(0.5)

        self.global_thread = None

    def _global_thread_action(self):
        """Execute one action of the global thread"""
        ###### Data saving
        shouldSave = False
        tpl = None
        # Get the next action that needs to be executed
        while not BackgroundSaveThread.save_queue.empty() and not shouldSave:
            tpl = BackgroundSaveThread.save_queue.get_nowait()

            if is_save_action(tpl):
                _, data, filename, shouldSave = tpl
            else:
                shouldSave = True

        if tpl is not None:
            # Execute the appropriate action
            if is_save_action(tpl):
                # Save the data
                _, data, filename, shouldSave = tpl
                # Save the values
                if data is not None and filename is not None:
                    path = Path(filename)
                    #
                    path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        np.save(path, data)
                    except PermissionError:
                        logger.error(f"Permission denied for {path}")
            elif is_move_action(tpl):
                _, from_, to_ = tpl
                # print("move", from_, to_)
                # Rename the file/folder
                os.rename(from_, to_)
            else:
                logger.error(
                    f"Unknown action saved to the queue: {tpl[0]}. Data: {tpl}"
                )
