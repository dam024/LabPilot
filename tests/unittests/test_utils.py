import unittest
import numpy as np

import labtools.utils as utils


class TestResampling(unittest.TestCase):
    def test_no_extra_shape(self):
        d = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 4.0, 4.0])

        np.testing.assert_array_equal(
            utils.resample(d, 3), np.array([1.0, 2.0, 3.0, 4.0])
        )

    def test_no_extra_shape_2(self):
        d = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 4.0, 4.0])

        np.testing.assert_array_equal(utils.resample(d, 4), np.array([1.25, 2.5, 3.75]))

    def test_extra_shape(self):
        d = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 4.0, 4.0])

        np.testing.assert_array_equal(utils.resample(d, 5), np.array([1.4, 23 / 7]))

    def test_2D_array_no_extra_shape(self):
        d = np.array(
            [
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            ]
        )

        np.testing.assert_array_equal(
            utils.resample(d, 3), np.array([[2.0, 5.0], [2.0, 5.0], [2.0, 5.0]])
        )

    def test_2D_array_extra_shape(self):
        d = np.array(
            [
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            ]
        )

        np.testing.assert_array_equal(
            utils.resample(d, 3), np.array([[2.0, 5.5], [2.0, 5.5], [2.0, 5.5]])
        )
