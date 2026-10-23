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
        """Test that the serialization of the enum works as expected"""
        t = self.TestEnum.A

        encoded = json.dumps(t, default=tes.serialize)

        decoded = json.loads(encoded, object_hook=tes.deserialize)

        self.assertEqual(t, decoded)

    def test_enum_serialization_2(self):
        """Test serialization of the enum with another value"""
        t = self.TestEnum.B

        encoded = json.dumps(t, default=tes.serialize)

        decoded = json.loads(encoded, object_hook=tes.deserialize)

        self.assertEqual(t, decoded)
