#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

from enum import Enum

optimization_ID = 0


class OptimizationInfoType(Enum):

    NONE = 0
    B2L_REALLOC = 0b1
    DVFS = 0b10
    SAME_CLUSTER_REALLOC = 0b100
    DVFS_AFTER_REALLOC = 0b1000

    def __str__(self):
        return "%s" % self.name


class OptimizationInfo:
    def __init__(self,
                 graph_node,
                 optim_type=OptimizationInfoType.NONE.value,
                 message=""):

        self.ID = 0
        self.graph_node = graph_node
        self.optim_type = optim_type
        self.message = message

    def __str__(self):
        ret = ""

        if self.optim_type & OptimizationInfoType.DVFS.value:
            if ret != "":
                ret += ", "
            ret += "DVFS"

        if self.optim_type & OptimizationInfoType.B2L_REALLOC.value:
            if ret != "":
                ret += ", "
            ret += "Task Reallocation"

        if self.optim_type & OptimizationInfoType.SAME_CLUSTER_REALLOC.value:
            if ret != "":
                ret += ", "
            ret += "Reallocated within cluster"

        if self.optim_type & OptimizationInfoType.DVFS_AFTER_REALLOC.value:
            if ret != "":
                ret += ", "
            ret += "DVFS possible after reallocation"

        return ret

    def set_message(self, message):
        self.message = message

    def add_optim_type(self, optim_type):
        global optimization_ID

        if self.ID == 0:
            self.ID = optimization_ID
            optimization_ID += 1
        self.optim_type |= optim_type.value

    def dvfs_possible(self):
        if self.optim_type & OptimizationInfoType.DVFS.value:
            return True
        return False

    def realloc_possible(self):
        if self.optim_type & OptimizationInfoType.B2L_REALLOC.value:
            return True
        return False

    def cluster_realloc_possible(self):
        if self.optim_type & OptimizationInfoType.SAME_CLUSTER_REALLOC.value:
            return True
        return False

    def dvfs_after_realloc_possible(self):
        if self.optim_type & OptimizationInfoType.DVFS_AFTER_REALLOC.value:
            return True
        return False
