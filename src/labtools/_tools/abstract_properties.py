import copy
from typing import Tuple, Type
import cython
import types
import io
from rich import Any, Optional
import rich.console
import rich.syntax


class AttributeShadowingError(Exception):
    pass


@cython.cclass
class AbstractProperties:
    """This class provides a mecanism to ensure that some properties are declared in subclasses.

    Subclasses must call the methods of this class to ensure that the desired properties are defined in subclasses
    """

    __dict__: dict

    @cython.ccall
    def _check_for_property(self, name: str, type: Type | None = None):
        """Check that the current instance possesses a given property

        Args:
            name (str): Name of the property to check
            type (Type): Type of the property
        """
        if not hasattr(self, name):
            raise AttributeError(
                f"You must define the property `{name}` in class {self.__class__.__name__}. If you have defined it in the __init__(), you must do it BEFORE calling super().__init__()"
            )

        self._keep_only_cython_attribute(name)

        value = getattr(self, name)

        if type is not None and not isinstance(value, type):
            raise TypeError(
                f"The type of the property `{name}` must be `{type}` in class {self.__class__.__name__}. Obtained type: {value}"
            )

    @cython.cfunc
    def _keep_only_cython_attribute(self, name: str):
        # Check if we are in a situation where there are both a python and a cython attribute having the same name

        # If this is a python attribute, returns its value. Otherwise, returns the
        if hasattr(self.__class__, name):
            value_python = getattr(self.__class__, name)

            # If this is already a descriptor, we don't need to go further
            if isinstance(value_python, types.GetSetDescriptorType):
                # return
                value_python = value_python.__get__(self, self.__class__)

            # Get the cython value
            owner, descriptor = self._find_cython_descriptor(name)

            if descriptor is not None:
                value_cython = descriptor.__get__(self, owner)
            else:
                return

            # This is the case where we have both a python and a cython property
            if value_cython != value_python:
                code = f"""
class {self.__class__.__name__}(...):

    {name} = ... # ❌ Do not define it like this

    def __init__(self,...):
        self.{name} = ... # ✅ Do it like this
        super().__init__(...)
                """

                # Format the code:
                output = io.StringIO()
                console = rich.console.Console(file=output, record=True)

                console.print(
                    rich.syntax.Syntax(
                        code, "python", theme="dracula", line_numbers=True
                    )
                )

                formatted = console.export_text(styles=True)

                raise AttributeShadowingError(
                    f"""The attribute `{self.__class__.__module__}.{self.__class__.__name__}.{name}` is shadowing the attribute you were supposed to initialized:\n{formatted}
                    """
                )

                # setattr(self, name, value_python)

    @cython.cfunc
    def _find_cython_descriptor(
        self, name: str
    ) -> Tuple[Optional[type], Optional[types.GetSetDescriptorType]]:
        for cls in type(self).__mro__:
            value = cls.__dict__.get(name)

            if isinstance(value, types.GetSetDescriptorType):
                return cls, value

        return None, None

    @cython.ccall
    def _set_if_not_defined(self, name: str, value):
        """Set the value for a property if it is not already defined

        Args:
            name (str): Name of the property
            value (Any): Value to assign if the property is not already defined
        """
        if not hasattr(self, name):
            setattr(self, name, value)
        self._check_for_property(name)

    @cython.ccall
    def _make_attribute_instance(self, attr: str, default: Any):
        """Make the given attribute local to the class


        Args:
            attr (str): Name of the attribute
            default (Any): Value to reset the class attribute to


        It is possible to define the class attributes:
            ```python
            class MyClass(AbstractProperties):
                graphs: List[AnObject] = []
            ```

            When we do this, the array `graphs` is shared among all instances of `MyClass`.

        One solution is the following:
            ```python
            class MyClass(AbstractProperties):

                def __init__(self) -> None:
                    self.graphs: List[AnObject] = []
            ```
            However, if subclasses must modify the `graphs` array, this should normally be done BEFORE the `__init__`, so the modifications can could be removed.

            This method provides a way to make the `graphs` array (and any objects saved as reference in memory) being declared as class attribute, while keeping them local to each instance.

        """

        if attr in type(self).__dict__ and attr not in vars(self):
            setattr(self, attr, copy.copy(getattr(type(self), attr)))
            setattr(type(self), attr, default)


@cython.cclass
class _TestAbstractProperties(AbstractProperties):
    _test = cython.declare(cython.unicode, visibility="public")

    def __init__(self) -> None:
        self._check_for_property("dirname", str)
        super().__init__()


class TestAbstractProperties(_TestAbstractProperties):
    def __init__(self) -> None:
        self._check_for_property("title", str)
        super().__init__()

    @property
    def title(self) -> str:
        return self._test

    @title.setter
    def title(self, value: str):
        self._test = value

    def get_title(self):
        return self.title
