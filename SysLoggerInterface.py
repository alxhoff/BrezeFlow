from enum import Enum


class SysLoggerStatus(Enum):
    INIT = 1
    SETUP = 2
    START = 3
    STOP = 4
    FINISH = 5


class SysLogger:

    def __init__(self, adb):
        self.adb = adb
        self.status = SysLoggerStatus.INIT

    def start(self):
        self.stop()
        self._setup()
        self.adb.command("./data/local/tmp/sys_logger.sh start")
        self.status = SysLoggerStatus.START

    def stop(self):
        self.adb.command("./data/local/tmp/sys_logger.sh stop")
        self.status = SysLoggerStatus.STOP
        self._finish()

    def _setup(self):
        self.adb.command("./data/local/tmp/sys_logger.sh setup -nt")
        self.status = SysLoggerStatus.SETUP

    def _finish(self):
        self.adb.command("./data/local/tmp/sys_logger.sh finish")
        self.status = SysLoggerStatus.FINISH
