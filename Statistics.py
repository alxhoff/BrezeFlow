#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class FrequencyStats:

    def __init__(self, freq):
        self.freq = freq
        self.use_time = 0


class TaskStats:

    def __init__(self, little_freqs, big_freqs):
        self.cpu_time = [0] * 8
        self.little_freqs = []
        self.big_freqs = []

        for freq in little_freqs:
            self.little_freqs.append(FrequencyStats(freq))

        for freq in big_freqs:
            self.big_freqs.append(FrequencyStats(freq))
