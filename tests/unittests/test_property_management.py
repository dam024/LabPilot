"""Test that the management of properties between cython and python is correct"""
import tests.utils as tu
import labtools._tools.abstract_properties as ap


class TestAssignmentInit(ap.TestAbstractProperties):
    def __init__(self) -> None:
        self.title: str = "test_title"
        self.dirname: str = "dirname_test"
        super().__init__()


class TestAssignmentClass(ap.TestAbstractProperties):
    title: str = "test_title"
    dirname: str = "dirname_test"


class TestPropertyManagement(tu.UpdatableConfigTest):
    def test_assignment_init(self):
        """Test the case where the variable is defined in the class __init__"""
        t = TestAssignmentInit()

        # Check the existance
        self.assertEqual(t.title, "test_title")
        self.assertEqual(t.dirname, "dirname_test")

        # Check the return from self.title
        self.assertEqual(t.get_title(), "test_title")
        self.assertEqual(t.dirname, "dirname_test")

    def test_assignment_class(self):
        """Test the case where the variable is defined in the class declaration (as a class attribute)"""
        t = TestAssignmentClass()

        # Check the existance
        self.assertEqual(t.title, "test_title")
        self.assertEqual(t.dirname, "dirname_test")

        # Check the return from self.title
        self.assertEqual(t.get_title(), "test_title")
        self.assertEqual(t.dirname, "dirname_test")
