from typing import Self


class GIInstantiationException(Exception):
    """Error to indicate that only a single instance of the recording manager can be instantiated"""

    pass


class GlobalUniqueInstance:
    _main: "Self | None" = None

    def __init__(self) -> None:
        if self.__class__._main is not None:
            raise GIInstantiationException(
                f"You can only instantiate ONCE the class `{self.__class__.__name__}`! Please, use `{self.__class__.__name__}.main()` to access it!!!"
            )

        self.__class__._main = self

    @classmethod
    def main(cls) -> "Self":
        if cls._main is None:
            cls._main = cls()

        return cls._main
