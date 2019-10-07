#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__credits__ = "Anuj Pathania"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class XU3RegressionModel:
    """ Regression constants found for the Odroid XU3 bigLITTLE board. Per/second energy is found using the
    following:
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
    """

    migration_factor = 1.7058

    little_freqs = [
            1000000000,
            1100000000,
            1200000000,
            1300000000,
            1400000000
            ]

    big_freqs = [
            1200000000,
            1300000000,
            1400000000,
            1500000000,
            1600000000,
            1700000000,
            1800000000,
            1900000000,
            2000000000
            ]

    little_reg_const = {
            "static": -0.515404251699599,
            "freq": (5.41174112348747 * pow(10, -10)),
            "util0": 0.00118267259901383,
            "util1": 0.00116622315262943,
            "util2": 0.00115205526392148,
            "util3": 0.00108948440210533
            }
    big_reg_const = {
            "static": -7.67667467145384,
            "temp0": 0.0118551114030958,
            "temp1": 0.0394152249258119,
            "temp2": 0.0207884463414066,
            "temp3": 0.0626956921220951,
            "freq": (6.35765269142093 * pow(10, -10)),
            "util0": 0.00373561226058925,
            "util1": 0.000708146964380524,
            "util2": 0.00176904935507961,
            "util3": 0.00231972698040632
            }
    GPU_reg_const = {
            "static": -1.979703742,
            "util": 0.011911485,
            "freq": (1.73811 * pow(10, -9)),
            "temp": 0.026603022
            }

    @staticmethod
    def get_cpu_per_second_energy(cpu, freq, util, temp):
        """ Using the values calculated for the energy profile of the Odroid XU3, using a regression model,
        the per-second energy consumption (in joules) can be calculated using the found values and the
        formula:
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)

        :param cpu: CPU core index of the target CPU core. 0-3 are LITTLE cores and 4-7 are big cores.
        :param freq: The frequency of the target CPU core
        :param util: The utilisations of the target CPU cluster
        :param temp: The temperatures of the target CPU cluster
        :return: Per-second energy consumption of the target core (in Joules/Sec = Watts)
        """

        energy = [0.0, 0.0]

        try:
            if cpu in range(4):  # Little

                reg_const = XU3RegressionModel.little_reg_const

                energy[0] = reg_const["static"] + reg_const["freq"] * freq + \
                            reg_const["util0"] * util[0] + reg_const["util1"] * util[1] + reg_const["util2"] * util[
                                2] + \
                            reg_const["util3"] * util[3]

                return energy

            else:  # Big

                reg_const = XU3RegressionModel.big_reg_const

                energy[1] = reg_const["static"] + reg_const["temp0"] * temp[0] + reg_const["temp1"] * temp[1] + \
                            reg_const["temp2"] * temp[2] + reg_const["temp3"] * temp[3] + reg_const["freq"] * freq + \
                            reg_const["util0"] * util[0] + reg_const["util1"] * util[1] + reg_const["util2"] * util[
                                2] + \
                            reg_const["util3"] * util[3]

                return energy

        except ValueError:
            print "Getting CPU cycle energy invalid frequency"
        except TypeError:
            print "Getting CPU cycle energy type error"

    @staticmethod
    def get_gpu_cycle_energy(freq, util, temp):

        reg_const = XU3RegressionModel.GPU_reg_const

        energy = reg_const["static"] + reg_const["freq"] * freq + reg_const["util"] * util + reg_const[
            "temp"] * temp

        return energy
