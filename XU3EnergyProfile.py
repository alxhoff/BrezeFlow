#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__credits__ = "Anuj Pathania"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class XU3RegressionConstants:
    """ Regression constants found for the Odroid XU3 bigLITTLE board. Per/second energy is found using the
    following:
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
    """

    def __init__(self):
        self.little_reg_const = {
                "a1": (3.247824433494 * pow(10, -9)),
                "a2": 0.0587311608,
                "a3": -3.0289386864
                }
        self.big_reg_const = {
                "a1": (1.8126515073404 * pow(10, -8)),
                "a2": -0.0007888097,
                "a3": 0.3776679028
                }
        self.GPU_reg_const = {
                "a1": (2.92610941759011 * pow(10, -8)),
                "a2": 0.0153949136,
                "a3": -0.7808512506
                }
        self.little_voltages = {
                1000000000: 1.09,
                1100000000: 1.12575,
                1200000000: 1.165469,
                1300000000: 1.211875,
                1400000000: 1.259028
                }
        self.big_voltages = {
                1200000000: 1.0125,
                1300000000: 1.0375,
                1400000000: 1.0375,
                1500000000: 1.063125,
                1600000000: 1.125,
                1700000000: 1.13875,
                1800000000: 1.1775,
                1900000000: 1.22833,
                2000000000: 1.305
                }
        self.GPU_voltages = {
                177000000: 0.83875,
                266000000: 0.99375,
                350000000: 0.881314,
                420000000: 0.907031,
                480000000: 0.94475,
                543000000: 0.995345
                }
        