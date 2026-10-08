from tests.utils import UpdatableConfigTest
from labtools.recording_manager import RecordingManager


class TestRecordingManager(UpdatableConfigTest):
    def test_config(self):
        """Test that the recording manager is correctly configured"""
        # Must be initially None
        self.assertIsNone(RecordingManager._main)
        # self.assertIsNone(RecordingManager._RecordingManager__main)

        # Call it and it must stay
        rm = RecordingManager.main()
        self.assertEqual(rm, RecordingManager._main)

        # Makes sure it doesn't disappear when I call it again
        self.assertEqual(rm, RecordingManager.main())

        # Reset it
        RecordingManager._main = None
        self.assertNotEqual(rm, RecordingManager.main())
