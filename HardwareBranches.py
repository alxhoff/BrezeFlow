#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

from pydispatch import dispatcher


class CPUBranch:
    """ Each core of the system has a CPUBranch which stores the previous and current metrics for the core,
    retaining to frequency values and utilization.

    """

    def __init__(self, cpu_number, initial_freq, initial_util, graph):

        self.cpu_num = cpu_number
        self.freq = initial_freq
        self.prev_freq = initial_freq
        self.util = initial_util
        self.prev_util = initial_util
        self.events = []
        self.graph = graph
        self.signal_freq = "freq_change" + str(self.cpu_num)

    def add_event(self, event):
        """ Adds an event to the stored history of the CPU branch. Also checks if the added event updates the
        actual metrics of the CPU.

        :param event: Event to be added to the CPU branch's history
        """

        self.events.append(event)

        if event.freq != self.freq or event.util != self.util:  # Update current metrics
            self.prev_freq = self.freq
            self.freq = event.freq

            if self.util is 0:

                self.prev_util = event.util
            else:

                self.prev_util = self.util

            self.util = event.util

            self._send_change_event()

    def _send_change_event(self):

        dispatcher.send(signal=self.signal_freq, sender=dispatcher.Any)


class GPUBranch:
    """
    The GPU branch stores a chronological history of all events that relate to the
    GPU's metrics
    """

    def __init__(self, initial_freq, initial_util, graph):

        self.freq = initial_freq
        self.prev_freq = initial_freq
        self.util = initial_util
        self.prev_util = initial_util
        self.graph = graph
        self.events = []
        self.signal_change = "gpu_change"  # Dispatcher signal

    def _send_change_event(self):
        """
        Send the signal to all dispatcher listeners that the GPU has changed it stats
        """
        dispatcher.send(signal=self.signal_change, sender=dispatcher.Any)

    def add_event(self, event):
        """
        :param event: A EventMaliUtil to be added to the GPU branch
        """
        if self.events:
            if (event.freq != self.events[-1].freq) or (
                event.util != self.events[-1].util
            ):
                self.events.append(event)
        else:
            self.events.append(event)

        if event.freq != self.freq or event.util != self.util:  # Update current metrics
            self.prev_freq = self.freq
            self.freq = event.freq

            if self.util is 0:

                self.prev_util = event.util

            else:
                self.prev_util = self.util

            self.util = event.util
