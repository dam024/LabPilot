from PySide6 import Path
from labpilot.data_management.measurement_information import RecordingInfos
from tests.utils import UpdatableConfigTest

import labpilot.recording_manager as rm
from labpilot import config


class TestRecordingManager(UpdatableConfigTest):
    def test_config(self):
        """Test that the recording manager is correctly configured"""
        # Must be initially None
        self.assertIsNone(rm.RecordingManager._main)
        # self.assertIsNone(RecordingManager._RecordingManager__main)

        # Call it and it must stay
        record_manag = rm.RecordingManager.main()
        self.assertEqual(record_manag, rm.RecordingManager._main)

        # Makes sure it doesn't disappear when I call it again
        self.assertEqual(record_manag, rm.RecordingManager.main())

        # Reset it
        rm.RecordingManager._main = None
        self.assertNotEqual(record_manag, rm.RecordingManager.main())

    def test_start_end_recording(self):
        """Test that a recording can be properly started and terminated"""
        recording_manager = rm.RecordingManager.main()

        # Start the recording
        recording_manager.start_recording(self)

        # Check the state
        self.assertIs(recording_manager.recorder, self)
        self.assertIsNotNone(recording_manager._recording)
        self.assertTrue(recording_manager.is_recording)

        # End the recording
        recording_manager.end_recording(self, save_data=False)

        # Check the state
        self.assertIsNone(recording_manager.recorder)
        self.assertIsNone(recording_manager._recording)
        self.assertFalse(recording_manager.is_recording)

    def test_save_data(self):
        """Test that saving the data work"""
        recording_manager = rm.RecordingManager.main()

        # Set a measurement
        recording_manager.measurement_id = 1

        # Start the recording
        recording_manager.start_recording(self)

        # End the recording
        foldername = "test_recording"
        infos = recording_manager.end_recording(
            self,
            save_data=True,
            foldername=foldername,
            description="test description",
        )

        # Check the state
        self.assertIsNone(recording_manager.recorder)
        self.assertIsNone(recording_manager._recording)
        self.assertFalse(recording_manager.is_recording)
        self.assertIsNotNone(infos)
        assert infos is not None

        # Test that the json file exists
        info_file = (
            Path(recording_manager.recording_path).parent / foldername / "info.json"
        )
        # Note: The path is not correct yet, it needs to be updated!!! This needs to be handled by the global state!
        self.assertTrue(info_file.exists(), info_file)

        # Check the content of the saved recording match the previous one
        infos_saved = RecordingInfos()
        infos_saved.load(str(info_file.parent))

        self.assertEqual(
            infos,
            infos_saved,
            f"Infos: {infos.to_dict()}, infos_saved: {infos_saved.to_dict()}",
        )

    def test_no_empty_record(self):
        """Test the a recording cannot be stopped if none has been started"""
        with self.assertRaises(rm.RMNoRecording):
            rm.RecordingManager().main().end_recording(self)

    def test_no_double_start(self):
        """Test that a 2nd recording cannot be started when one is already running"""
        record_manager = rm.RecordingManager.main()

        # Start a first time
        record_manager.start_recording(self)

        with self.assertRaises(rm.RMRecordingInProgress):
            record_manager.start_recording(self)

        with self.assertRaises(rm.RMRecordingInProgress):
            record_manager.start_recording(object())
