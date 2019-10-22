#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

from enum import Enum


class OptimizationInfoType(Enum):
    NONE = 0
    LONG_EXEC_DURATION = 0b1
    POSSIBLE_DVFS = 0b10
    POSSIBLE_REALLOC = 0b100

    def __str__(self):
        return "%s" % self.name


class OptimizationInfo:

    def __init__(self, graph_node, optim_type=OptimizationInfoType.NONE.value, message=""):
        self.graph_node = graph_node
        self.optim_type = optim_type
        self.message = message

    def __str__(self):
        ret = ""

        if self.optim_type & OptimizationInfoType.LONG_EXEC_DURATION.value:
            ret += "Long execution duration"

        if self.optim_type & OptimizationInfoType.POSSIBLE_DVFS.value:
            if ret != "":
                ret += ", "
            ret += "Possible DVFS"

        if self.optim_type & OptimizationInfoType.POSSIBLE_REALLOC.value:
            if ret != "":
                ret += ", "
            ret += "Possible Reallocation"

        return ret

    def set_message(self, message):
        self.message = message

    def add_optim_type(self, optim_type):
        self.optim_type |= optim_type.value



