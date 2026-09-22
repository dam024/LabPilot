from typing import Any, List, Type, TypeVar, TYPE_CHECKING

import importlib
import importlib.util
from types import ModuleType
import inspect
import sys


def dynamic_import(module_name: str, file_path: str):
    """
    Dynamically imports a Python module from the specified file path.

    Parameters:
        module_name (str): The name of the module to be imported.
        file_path (str): The full path to the Python file.

    Returns:
        module: The imported module object.

    Raises:
        ImportError: Description
    """

    # If the module has already been imported, returns it
    if module_name in sys.modules:
        return sys.modules[module_name]

    # Check if the file exists
    try:
        with open(file_path, "r") as f:
            pass  # Just check if the file can be opened
    except FileNotFoundError:
        raise ImportError(f"The module file was not found at {file_path}")

    # Create a module spec
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not create a module spec for {module_name} at {file_path}"
        )

    # Create the module
    module = importlib.util.module_from_spec(spec)

    # Add the module to sys.modules
    sys.modules[module_name] = module

    # Execute the module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"Error while executing module {module_name}: {e}")

    return module


def dynamic_obj_import(module_name: str, component: str):
    # Import the module
    module = importlib.import_module(module_name)

    # Get the component
    obj = module
    for attr in component.split("."):
        obj = getattr(obj, attr)

    return obj


T = TypeVar("T")


def list_classes_inheriting_from(
    module: ModuleType, base_class: Type[T], take_abstract_classes: bool = False
) -> List[Type[T]]:
    """
    List all classes in the given module that inherit from the specified base class.

    Parameters:
        module (ModuleType): The module to inspect.
        base_class (type): The base class to check inheritance against.

    Returns:
        List[GraphModule]: A list of classes in the module that inherit from base_class.
    """
    lst: List[Type[T]] = list()
    duplication_test = {}
    # print("Test")
    # Iterate over all members of the module
    for name, obj in inspect.getmembers(module):
        # Check if the member is a class and not the base class itself
        # print(name, obj)
        if inspect.isclass(obj) and obj != base_class:
            # Check if the class inherits from the base class
            if issubclass(obj, base_class):
                if obj.__name__ in duplication_test:
                    raise RuntimeError(
                        f"2 classes have the same name: `{obj.__name__}` in module {module.__file__}"
                    )

                duplication_test[obj.__name__] = True
                if take_abstract_classes or not inspect.isabstract(obj):
                    lst.append(obj)

    return lst


class IgnorableClass:
    ignore: bool


T = TypeVar("T", bound=IgnorableClass)


def get_all_views(
    module_location: str,
    cls_type: Type[T],
    excluded_modules: List[str] = [],
    exclude_ignored: bool = False,
) -> List[T]:
    """Collect all readers available

    Args:
        module_location (str): Path to the module
        excluded_modules (List[str], optional): ´List of modules to exclude from the inspected modules.
        exclude_ignored (bool, optional): If True, will filter out the views having `ignore` == True from the list
    """

    # Load the module with the correct name
    module_name = module_location.split(".")[0].replace(
        "/", "."
    )  # .split("/")[-1].split(".")[0]
    # module = dynamic_import("specific_modules", module_location)
    module = dynamic_import(module_name, module_location)

    # Get all the possible objects
    views_list = list_classes_inheriting_from(module, cls_type, True)

    # For each graph module, create it and execute it
    views: List[T] = []
    for view in views_list:
        # Don't take into account
        if view.__module__ not in excluded_modules and (
            not exclude_ignored or not view.ignore
        ):
            views.append(view())

    return views
