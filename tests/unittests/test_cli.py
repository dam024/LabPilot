import tests.utils as utils
from labtools.config import generalConfig as config


class TestCLI(utils.UpdatableConfigTest):
    def test_init(self):
        """Test that the initialization of a project works as expected"""
