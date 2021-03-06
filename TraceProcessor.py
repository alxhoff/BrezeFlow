#!/usr/bin/env python

import sys
import time
import numpy as np

from Grapher import Grapher
from ProcessTree import ProcessTree

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class TraceProcessor:
    """ After a trace is run the trace data is retrieved from the target Android system. This binary trace
    data must be parsed and processed. The TraceProcessor class loads the data using the provided filename,
    then processing the stored trace events, compiling required metric histories and process branches as
    well as the final process tree.
    """
    def __init__(self, pidt, filename):
        """
        :param pidt: PID tool object that has all the PIDs relevant to the target application stored
        :param filename: Filename for storing the results of the processed trace
        """
        self.pidt = pidt
        self.filename = filename

    def process_trace(
            self,
            governor,
            progress_signal,
            metrics,
            tracecmd,
            duration,
            draw=None,
            test=None,
            subgraph=False,
            subdir=None,
    ):
        """ There are a number of steps required in processing a given trace. This is outlined below.

        - Idle and temperature events are preprocessed and removed from the pending events to be processed. This
        is so that the per core temperature and utilization lookup timelines can be generated before the events that
        depending on them to calculate energy consumptions are processed.
        - Events are handled by their respective PID branches
        - The process tree is finished, this generates the results of the energy debugger from the data stored in the
        process branches
        - The visual graph is drawn, if required

        :param metrics: The SystemMetrics object that stores all metric timelines and actual values for the target
        system
        :param tracecmd: The tracecmd processor object
        :param duration: The duration for which the trace should be processed, required as the tracing duration
        is not exact, due to overhead in loading and unloading the trace framework
        :param draw: Boolean to signal if the visual .dot graph file should be drawn or not
        :param test: Boolean to signal if the trial is a test of not, test runs only parse 300 events such that they
        can complete the processing process quickly
        :param subgraph: Boolean to signal if the subgraphs of the graph's task nodes should be drawn
        """

        process_start_time = time.time()

        if not tracecmd.processed_events:
            sys.exit("Processing trace failed")

        process_tree = ProcessTree(self.pidt, metrics)
        trace_start_time = tracecmd.processed_events[0].time
        if len(tracecmd.idle_events) == 0:
            raise Exception("No idle events to process")

        if tracecmd.idle_events[0].time < trace_start_time:
            trace_start_time = tracecmd.idle_events[0].time
        if tracecmd.temp_events[0].time < trace_start_time:
            trace_start_time = tracecmd.temp_events[0].time
        trace_finish_time = int(trace_start_time + float(duration) * 1000000)

        try:
            start_time = time.time()
            sys.stdout.write("Building temp trees")
            if len(tracecmd.temp_events):
                metrics.sys_temp_history.initial_time = tracecmd.temp_events[
                    0].time
                metrics.sys_temp_history.end_time = tracecmd.temp_events[
                    -1].time
            else:
                raise Exception("No temp events")

            temp_history = []
            no_temp_events = len(tracecmd.temp_events)
            temp_history.append(
                process_tree.handle_temp_event(tracecmd.temp_events[0], None))
            for x in range(len(tracecmd.temp_events[1:])):
                if progress_signal:
                    progress_signal.emit(
                        (round(float(x) / no_temp_events * 100, 2)))
                temp_history.append(
                    process_tree.handle_temp_event(tracecmd.temp_events[x + 1],
                                                   tracecmd.temp_events[x]))
            if progress_signal:
                progress_signal.emit(100)
            metrics.sys_temp_history.temps = np.block(temp_history)
            print(" --- COMPLETED in %s seconds" % (time.time() - start_time))
        except Exception, e:
            print("Error processing temperatures: %s" % e)
            return

        try:
            start_time = time.time()
            no_idle_events = len(tracecmd.idle_events)
            sys.stdout.write("Building utilization trees")
            for x, event in enumerate(tracecmd.idle_events):
                if progress_signal:
                    progress_signal.emit(
                        round(float(x) / no_idle_events * 100, 2))
                process_tree.handle_idle_event(event)
            if progress_signal:
                progress_signal.emit(100)
            print(" --- COMPLETED in {} seconds".format(time.time() -
                                                        start_time))
        except Exception, e:
            print("Error building utilization trees: %s" % e)
            return

        try:
            start_time = time.time()
            num_events = len(tracecmd.processed_events)
            sys.stdout.write("Processing %d events" % num_events)

            # TODO does it matter if the first event is a mali event?
            metrics.sys_util_history.gpu.init(trace_start_time,
                                              trace_finish_time,
                                              metrics.current_gpu_util)
        except Exception, e:
            print("Error initializing GPU util: %s" % e)
            return

        try:
            error_event = 0
            if test:
                for x, event in enumerate(tracecmd.processed_events[:test]):
                    if (progress_signal and trace_start_time <= event.time <=
                            trace_finish_time):
                        progress_signal.emit(round(float(x) / test * 100, 2))
                    try:
                        if process_tree.handle_event(event, subgraph):
                            break
                    except Exception, e:
                        error_event = x
                        e = str(e) + " event {}".format(error_event)
                        raise Exception(e)
            else:
                for x, event in enumerate(tracecmd.processed_events):
                    if (progress_signal and trace_start_time <= event.time <=
                            trace_finish_time):
                        progress_signal.emit(
                            round(float(x) / num_events * 100, 2))
                    try:
                        if process_tree.handle_event(event, subgraph):
                            break
                    except Exception, e:
                        error_event = x
                        e = str(e) + " event {}".format(error_event)
                        raise Exception(e)
            if progress_signal:
                progress_signal.emit(100)
            print(" --- COMPLETED in %s seconds" % (time.time() - start_time))
            print(" ------ Sched switch events in %s seconds" %
                  process_tree.sched_switch_time)
            print(" ------ Binder events in %s seconds" %
                  process_tree.binder_time)
            print(" ------ Freq events in %s seconds" % process_tree.freq_time)
        except Exception, e:
            print("Error processing event {}: {}".format(error_event, e))
            return

        try:
            start_time = time.time()
            sys.stdout.write("Finishing process tree")
            optimizations_found = process_tree.finish_tree(
                self.filename, governor, subdir)
            print(" --- COMPLETED in {} seconds".format(time.time() -
                                                        start_time))
            print(
                "Found {} B2L realloc, {} DVFS, {} Intra-cluster realloc, {} DVFS after realloc"
                .format(optimizations_found[0], optimizations_found[1],
                        optimizations_found[2], optimizations_found[3]))
        except Exception, e:
            print("Error finishing tree: %s" % e)
            return

        if draw:
            sys.stdout.write("Drawing graph")
            start_time = time.time()
            draw_graph = Grapher(process_tree, subdir)
            draw_graph.draw_graph()
            print(" --- COMPLETED in %s seconds" % (time.time() - start_time))

        print("** Processing finished in %s seconds **" %
              (time.time() - process_start_time))
