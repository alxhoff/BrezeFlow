#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__credits__ = "Anuj Pathania"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

import sys


class XU3RegressionModel:
    """ Regression constants found for the Odroid XU3 bigLITTLE board. Per/second energy is found using the
    following:
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
    """

    little_reg_const = {
            "a1": (3.247824433494 * pow(10, -9)),
            "a2": 0.0587311608,
            "a3": -3.0289386864
            }
    # big_reg_const = {
    #         "a1": (1.8126515073404 * pow(10, -8)),
    #         "a2": -0.0007888097,
    #         "a3": 0.3776679028
    #         }
    big_reg_const = {
            "static": -7.67667467145395,
            "temp0": 0.0118551114030954,
            "temp1": 0.0394152249258121,
            "temp2": 0.0207884463414049,
            "temp3": 0.0626956921220966,
            "freq": (6.35765269142174 * pow(10,-7)),
            "util0": 0.00373561226058926,
            "util1": 0.00070814696438041,
            "util2": 0.00176904935507982,
            "util3": 0.00231972698040641
            }

    GPU_reg_const = {
            "a1": (2.92610941759011 * pow(10, -8)),
            "a2": 0.0153949136,
            "a3": -0.7808512506
            }
    little_voltages = {
            1000000000: 1.09,
            1100000000: 1.12575,
            1200000000: 1.165469,
            1300000000: 1.211875,
            1400000000: 1.259028
            }
    big_voltages = {
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
    GPU_voltages = {
            177000000: 0.83875,
            266000000: 0.99375,
            350000000: 0.881314,
            420000000: 0.907031,
            480000000: 0.94475,
            543000000: 0.995345
            }

    @staticmethod
    def get_cpu_per_second_energy(cpu, freq, util, temp):
        """ Using the values calculated for the energy profile of the Odroid XU3, using a regression model,
        the per-second energy consumption (in joules) can be calculated using the found values and the
        formula:
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)

        :param cpu: CPU core index of the target CPU core. 0-3 are LITTLE cores and 4-7 are big cores.
        :param freq: The frequency of the target CPU core
        :param util: The utilizations of the target CPU cluster
        :param temp: The temperatures of the target CPU cluster
        :return: Per-second energy consumption of the target core (in Joules/Sec = Watts)
        """
        try:
            if cpu in range(4):  # Little

                try:
                    voltage = XU3RegressionModel.little_voltages[freq]
                except IndexError:
                    print "Couldn't get voltage for little core at freq: %d" % freq
                    sys.exit(-1)
                a1 = XU3RegressionModel.little_reg_const["a1"]
                a2 = XU3RegressionModel.little_reg_const["a2"]
                a3 = XU3RegressionModel.little_reg_const["a3"]
                energy = voltage * (a1 * voltage * freq * util[cpu] + a2 * temp[cpu] + a3)

                return energy

            else:  # Big

                reg_const = XU3RegressionModel.big_reg_const

                energy = reg_const["static"] + reg_const["temp0"] * temp[0] + reg_const["temp1"] * temp[1] + \
                         reg_const["temp2"] * temp[2] + reg_const["temp3"] * temp[3] + reg_const["freq"] * freq + \
                         reg_const["util0"] * util[0] + reg_const["util1"] * util[1] + reg_const["util2"] * util[2] + \
                         reg_const["util3"] * util[3]

                return energy

        except ValueError:
            print "Getting CPU cycle energy invalid frequency"
        except TypeError:
            print "Getting CPU cycle energy type error"

    @staticmethod
    def get_gpu_cycle_energy(freq, util, temp):
        try:
            voltage = XU3RegressionModel.GPU_voltages[freq]
        except IndexError:
            print "Attempted to get GPU voltage with invalid freq"
            sys.exit(1)
        a1 = XU3RegressionModel.GPU_reg_const["a1"]
        a2 = XU3RegressionModel.GPU_reg_const["a2"]
        a3 = XU3RegressionModel.GPU_reg_const["a3"]
        energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
        return energy
