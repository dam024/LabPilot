import json
import datetime


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

    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


def deserialize(obj):
    """Provides deserialization for the cases json.load() doesn't know how to serialize/serialize a type"""

    if obj.get("__type__") == "datetime":
        return datetime.datetime.fromisoformat(obj["value"])

    if obj.get("__type__") == "date":
        return datetime.date.fromisoformat(obj["value"])

    return obj
