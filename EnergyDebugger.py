#!/usr/bin/env python

import argparse
import time
import os
import sys

import MainInterface

from PyQt5.QtWidgets import QMainWindow, QApplication

from ADBInterface import ADBInterface
from PIDTools import PIDTool
from SysLoggerInterface import SysLogger
from SystemMetrics import SystemMetrics
from TraceCMDParser import TracecmdProcessor
from TraceProcessor import TraceProcessor
from Tracer import Tracer

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

parser = argparse.ArgumentParser()

parser.add_argument("-a", "--app", required=False,
                    help="Specifies the name of the game to be traced")
parser.add_argument("-d", "--duration", required=False, type=float,
                    help="The duration to trace")
parser.add_argument("-e", "--events", required=False,
                    help="Events that are to be traced")
parser.add_argument("-s", "--skip-clear", action='store_true',
                    help="Skip clearing trace settings")
parser.add_argument("-g", "--draw", action='store_true',
                    help="Enables the drawing of the generated graph")
parser.add_argument("-te", "--test", action='store_true',
                    help="Tests only a few hundred events to speed up testing")
parser.add_argument("-sub", "--subgraph", action='store_true',
                    help="Enable the drawing of node subgraphs")
parser.add_argument("-p", "--preamble", required=False,
                    help="Specifies the number of seconds that be discarded at the begining of tracing")

args = parser.parse_args()


class MainInterface(QMainWindow, MainInterface.Ui_MainWindow):

    def __init__(self, parent=None):
        super(QMainWindow, self).__init__(parent)

        self.setupUi(self)
        self.setupbuttons()
        self.show()

    def setupbuttons(self):
        self.pushButtonRun.clicked.connect(self.buttonrun)
        self.pushButtonKillADB.clicked.connect(self.buttonkilladb)

    def checkrun(self):
        if not self.lineEditApplication.text() and not args.app:
            return False

        if self.doubleSpinBoxDuration.value() == 0 and args.duration:
            return False

        return True

    def buttonrun(self):
        if not self.checkrun():
            return
        

    def buttonkilladb(self):
        pass

class EnergyDebugger:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.UI = MainInterface()
        # self.main()
        sys.exit(self.app.exec_())

    def main(self):
        """ Entry point into the debugging tool.
        """


        """ Required objects for tracking system metrics and interfacing with a target system, connected
        via an ADB connection.
        """

        start_time = time.time()

        self.adb = ADBInterface()
        self.pid_tool = PIDTool(self.adb, args.app)
        self.trace_processor = TraceProcessor(self.pid_tool, args.app)
        sys_metrics = SystemMetrics(self.adb)

        """ The tracer object stores the configuration for the ftrace trace that is to be performed on the
        target system.
        """

        print "Creating tracer, starting sys_logger and running trace"

        preamble = int(args.preamble)

        self.tracer = Tracer(self.adb,
                        args.app,
                        metrics=sys_metrics,
                        events=args.events.split(','),
                        duration=args.duration
                        )

        """ As the energy debugger depends on the custom trace points implemented in the syslogger module,
        it must be loaded before tracing begins. It must then be unloaded and finished before the results
        are pulled from the target system.
        """

        if args.duration > 6:
            print "WARNING: Running traces over 6 seconds can cause issue due to data loss from trace buffer size " \
            "limitations"

        self.sys_logger = SysLogger(self.adb)
        self.sys_logger.start()
        self.tracer.run_tracer(preamble, args.skip_clear)
        self.sys_logger.stop()
        self.tracer.get_trace_results()

        """ The tracecmd data pulled (.dat suffix) is then iterated through and the trace events are systematically
        processed. Results are generated into a CSV file, saved to the working directory under the same name as the target
        application with the suffix _results.csv.
        """

        print "Loading tracecmd data and processing"

        dat_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.app + ".dat")

        self.tc_processor = TracecmdProcessor(dat_path, preamble)
        self.tc_processor.print_event_count()
        self.trace_processor.process_trace(sys_metrics, self.tc_processor, args.duration, args.draw, args.test, args.subgraph)

        print "Run took a total of %s seconds to run" % (time.time() - start_time)

if __name__ == '__main__':
    app = EnergyDebugger()