import unittest

from labpilot.data_management.measurement_information import RecordingInfos
import tests.utils as tu

from labpilot.GUI.binding import Binding, BindingNotInstantiatedError, BindingSupport


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
        """Test that if I deleate an instance of a Binding that wasn't setup, it won't cause an error while dumping the parameters"""

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
