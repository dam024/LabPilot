from types import TracebackType
from typing import Any, Callable, Generic, Type, TypeVar, Dict
import os
import json
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

import logging

logger = logging.getLogger(__name__)
from labpilot import config
from labpilot.GUI.binding import BindingSupport


class Base(DeclarativeBase):
    pass


"""Base class from which every model object must inherit"""

T = TypeVar("T")
C = TypeVar("C")


class classlazyproperty(Generic[T, C]):

    """A method decorator that allows to create a lazy property at class level.

    The value of the lazy property is created only at first call and the same value is kept for the rest of the execution of the program. Note that this property exists at class level!
    """

    def __init__(self, fget: Callable[[Any], T]) -> None:
        self.fget = fget
        self.value: T | None = None

    def __get__(
        self,
        obj: C | None,
        owner: type[C] | None = None,
    ) -> T:
        if self.value is not None:
            return self.value

        if owner is None:
            assert obj is not None
            owner = type(obj)

        self.value = self.fget(owner)
        return self.value


class DB:
    @classlazyproperty
    def engine(cls) -> Engine:
        """Engine used for the connexion to the database"""
        logger.info(f"Database: {config.database_url}")
        eng = create_engine(config.database_url, echo=False)
        return eng

    @classlazyproperty
    def Session(cls):
        """Session class used to interact with the database"""
        cls.sync_model_with_db()
        return sessionmaker(bind=cls.engine)

    def __init__(self) -> None:
        self.session = None

    def __enter__(self):
        try:
            self.session = self.Session()
            return self.session
        except:
            raise

    def __exit__(
        self,
        exc_type: Type[Exception] | None,
        exc_value: str | None,
        exc_traceback: TracebackType | None,
    ):
        if self.session:
            # If there was an exception, rollback. Otherwise, commit
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()

            # Close the session
            self.session.close()

            if exc_type:
                raise exc_type(exc_value)

    @classmethod
    def sync_model_with_db(cls):
        """Ensures that the database model used matches the current database scheme"""
        Base.metadata.create_all(cls.engine)
