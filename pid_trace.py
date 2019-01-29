import logging

class PID:

    def __init__(self, pid, user, time, name, ppid=0):
        self.pid = pid
        self.user = user
        self.time = time
        self.name = name


class PIDtracer:

    def __init__(self, adb_device, name):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("PID tracer created")

        self.adb_device = adb_device
        self.name = name
        self.mainPID = self.findMainPID()
        self.allPID = []
        self.findAllPID()

    def __del__(self):
        self.logger.debug("PID tracer closed")

    def findMainPID(self):
        res = self.adb_device.runCommand("ps | grep " + self.name)
        res = res.split()
        self.logger.debug("Found main PID of " + res[1] + " for process "
                + res[8])
        ret = PID(res[1], res[0], 0, res[7])

    def findAllPID(self):
        res = self.adb_device.runCommand("busybox ps -T | grep " + self.name)
        res = res.splitlines()
        for line in res:
            split_line = line.split()
            print split_line
            for x in split_line:
                self.allPID.append(PID(x[0], x[1], x[2], x[3]))
            self.logger.debug("Found related process " + x[0] + "  "
                    + x[3])



