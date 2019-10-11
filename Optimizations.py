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

    def __init__(self, graph_node, error_type=OptimizationInfoType.NONE, message=""):
        self.graph_node = graph_node
        self.error_type = error_type
        self.message = message

    def set_info(self, error_type, message):
        self.error_type
        self.message

