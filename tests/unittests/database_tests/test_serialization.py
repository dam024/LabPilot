import json
import enum
import unittest


import labpilot.data_management.type_extension_support as tes


class TestSerialization(unittest.TestCase):
    class TestEnum(enum.Enum):
        A = "a"
        B = "b"
        C = "c"

    def test_enum_serialization(self):
        t = self.TestEnum.A

        encoded = json.dumps(t, default=tes.serialize)

        decoded = json.loads(encoded, object_hook=tes.deserialize)

        self.assertEqual(t, decoded)
