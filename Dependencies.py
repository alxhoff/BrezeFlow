from enum import Enum


class DependencyType(Enum):
    NONE = 0
    TASK = 1
    BINDER = 2

    def __str__(self):
        return "%s" % self.name


class Dependency:
    def __init__(self,
                 prev_task=None,
                 next_task=None,
                 type=DependencyType.NONE):
        self.type = type
        self.prev_task = prev_task  # earlier node
        self.next_task = next_task
