from enum import Enum


class DependencyType(Enum):
    NONE = 0
    TASK = 1
    BINDER = 2

    def __str__(self):
        return "%s" % self.name


class Dependency:

    def __init__(self, dependee=None, depender=None, type=DependencyType.NONE):
        self.type = type
        self.dependee = dependee  # earlier node
        self.depender = depender
