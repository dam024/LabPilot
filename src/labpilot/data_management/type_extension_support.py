import enum
import json
import datetime

import labpilot._tools.dynamic_imports as di


def serialize(obj):
    """Defines a default serializer in case the json.dumps() function does not know how to serialize an object"""

    if isinstance(obj, datetime.datetime):
        return {
            "__type__": "datetime",
            "value": obj.isoformat(),
        }

    if isinstance(obj, datetime.date):
        return {
            "__type__": "date",
            "value": obj.isoformat(),
        }

    if isinstance(obj, enum.Enum):
        return {
            "__type__": "Enum",
            "__class__": obj.__class__.__name__,
            "__qualname__": obj.__class__.__qualname__,
            "__module__": obj.__class__.__module__,
            "value": obj.name,
        }

    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


def deserialize(obj):
    """Provides deserialization for the cases json.load() doesn't know how to serialize/serialize a type"""

    if obj.get("__type__") == "datetime":
        return datetime.datetime.fromisoformat(obj["value"])

    if obj.get("__type__") == "date":
        return datetime.date.fromisoformat(obj["value"])

    if obj.get("__type__") == "Enum":
        t = di.dynamic_obj_import(obj.get("__module__"), obj.get("__qualname__"))

        return t[obj.get("value")]

    return obj
