import os
from pathlib import Path
import unittest
import numpy as np

from labpilot.data_management.background_thread_save import BackgroundSaveThread
from labpilot.data_management.measurement_information import RecordingInfos
import tests.utils as tu

from labpilot.GUI.binding import Binding, BindingNotInstantiatedError, BindingSupport
from labpilot import config


class TestRecordingInfos(tu.UpdatableConfigTest):
    def test_recording_info_save(self):
        """Test the normal process of saving the experiment parameters"""

        # Defines two classes
        class TestBindingSupport(BindingSupport):
            def __init__(self) -> None:
                super().__init__()

            @Binding
            def value(self) -> int:
                return 0

        # Instantiate one Binding and change its value
        b = TestBindingSupport()
        b.value = 5

        # Now, dump the parameters
        info = RecordingInfos()
        info.dump_parameters()
        self.assertDictEqual(info["parameters"], {"TestBindingSupport.value": 5})

        # Reset the bindings -> Like if I restart the app
        self._reset_bindings()

        # Create a new binding and check initial state
        b = TestBindingSupport()
        self.assertEqual(b.value.get(), 0)

        # Load the parameters
        info.apply_parameters()

        self.assertEqual(b.value.get(), 5)

    def test_recording_info_save_with_deleted_bindings(self):
        """Test that if I delete an instance of a Binding that wasn't setup, it won't cause an error while dumping the parameters"""

        # Defines two classes
        class TestBindingSupport(BindingSupport):
            def __init__(self) -> None:
                super().__init__()

            @Binding
            def value(self) -> int:
                return 0

        # Extra class
        class DeletedBinding(BindingSupport):
            @Binding
            def val(self) -> int:
                return 1

        # Instantiate one Binding and change its value
        b = TestBindingSupport()
        # b1 = DeletedBinding()
        b.value = 5

        # Check the initial state
        self.assertIn(TestBindingSupport.__name__, BindingSupport.parametrables.keys())
        # self.assertIn(DeletedBinding.__name__, BindingSupport.parametrables.keys())

        self.assertEqual(DeletedBinding.__binding_instantiated__, False)
        # del b1

        # Now, dump the parameters
        info = RecordingInfos()
        # with self.assertRaises(BindingNotInstantiatedError):
        #    info.dump_parameters()
        info.dump_parameters()


class TestBackgroundSaveThread(tu.UpdatableConfigTest):
    def test_save_action_no_force(self):
        bg = BackgroundSaveThread.main()

        path = Path(config.output_dir_data)

        a = np.array([0.0, 1.0, 2.0])

        # Save 10 files
        for i in range(10):
            bg.addSaveAction(a, str(path / f"output_{i}.npy"), False)

        # Executes 30 times to make sure we have executed everything
        for i in range(30):
            bg._global_thread_action()

        # Only one file must have been saved, since they were all with force=False
        f = path / f"output_9.npy"
        # print(os.listdir(path))
        self.assertTrue(f.exists())

    def test_save_action_force(self):
        bg = BackgroundSaveThread.main()

        path = Path(config.output_dir_data)

        a = np.array([0.0, 1.0, 2.0])

        # Save 10 files
        for i in range(10):
            bg.addSaveAction(a, str(path / f"output_{i}.npy"), True)

        # Executes 30 times to make sure we have executed everything
        for i in range(30):
            bg._global_thread_action()

        # All files must exist
        for i in range(10):
            f = path / f"output_{i}.npy"
            self.assertTrue(f.exists(), f)

    def test_save_action_mixed(self):
        bg = BackgroundSaveThread.main()

        path = Path(config.output_dir_data)

        a = np.array([0.0, 1.0, 2.0])

        # Save 10 files
        bg.addSaveAction(a, str(path / f"output_0.npy"), False)
        bg.addSaveAction(a, str(path / f"output_1.npy"), False)
        bg.addSaveAction(a, str(path / f"output_2.npy"), True)
        bg.addSaveAction(a, str(path / f"output_3.npy"), False)
        bg.addSaveAction(a, str(path / f"output_4.npy"), True)
        bg.addSaveAction(a, str(path / f"output_5.npy"), False)

        # Executes 30 times to make sure we have executed everything
        for i in range(30):
            bg._global_thread_action()

        # Only files 2,4,5 must exist
        for i in range(10):
            f = path / f"output_{i}.npy"
            if i in [2, 4, 5]:
                self.assertTrue(f.exists(), f)
            else:
                self.assertFalse(f.exists(), f)

    def test_save_move_action_mixed(self):
        """Test that having some move actions in the middle of save actions won't change anything"""
        bg = BackgroundSaveThread.main()

        path = Path(config.output_dir_data)
        new_path = Path(config.output_dir) / "saved_data"

        a = np.array([0.0, 1.0, 2.0])

        # Save a few files
        bg.addSaveAction(a, str(path / f"output_0.npy"), True)
        bg.addSaveAction(a, str(path / f"output_1.npy"), True)

        # Move
        bg.addMoveAction(path, new_path)

        # Add some more files in both repository
        bg.addSaveAction(a, str(path / f"output_0.npy"), True)
        bg.addSaveAction(a, str(path / f"output_1.npy"), True)
        bg.addSaveAction(a, str(new_path / f"output_2.npy"), True)

        # Executes 30 times to make sure we have executed everything
        for i in range(30):
            bg._global_thread_action()

        # Only files 0,1 must exist in `path`
        for i in range(10):
            f = path / f"output_{i}.npy"
            if i in [0, 1]:
                self.assertTrue(f.exists(), f)
            else:
                self.assertFalse(f.exists(), f)

        # Only files 0,1,2 must exist in `new_path`
        for i in range(10):
            f = new_path / f"output_{i}.npy"
            if i in [0, 1, 2]:
                self.assertTrue(f.exists(), f)
            else:
                self.assertFalse(f.exists(), f)
