from typing import Any, Type
from rocksdict import DbClosedError, Rdict
import os

import logging

logger = logging.getLogger(__name__)

from labtools import config


class LocalStorage:
    """This class handles storage of data locally.

    Note:
    Data are stored in the `.local_storage` folder at the root of the project
    """

    _global = None

    def __init__(self):
        """NEVER instantiate this class directly! Always use the `main()` class method!"""
        try:
            self.db = Rdict(self.location)
        except Exception:
            logger.error(
                f"Another instance is probably already running. Please, close it and try again"
            )
            exit()

    def __del__(self):
        try:
            if hasattr(self, "db"):
                self.db.close()
        except DbClosedError:
            pass
        finally:
            self.__class__._global = None

    @property
    def location(self) -> str:
        return os.path.join(
            config.get("GENERAL", "local_storage_path", fallback=".local_storage"),
            "preferences",
        )

    @classmethod
    def main(cls) -> "LocalStorage":
        """Returns the main instance of the local storage.

        NEVER instantiate this class directly. Always use this method!
        """
        if cls._global is None:
            cls._global = LocalStorage()

        return cls._global

    def _build_key(self, owner: object | Type, key: str) -> str:
        if isinstance(owner, Type):
            return f"{owner.__name__}.{key}"
        else:
            return f"{owner.__class__.__name__}.{key}"

    def set(self, owner: object | Type, key: str, value: Any):
        full_key = self._build_key(owner, key)
        self.db[full_key] = value

    def get(self, owner: object | Type, key: str) -> object:
        full_key = self._build_key(owner, key)
        return self.db[full_key]

    def has_value(self, owner: object | Type, key: str) -> bool:
        """Indicates if the current key is saved for the given object in the local storage"""
        full_key = self._build_key(owner, key)
        return full_key in self.db
