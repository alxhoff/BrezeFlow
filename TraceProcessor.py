#!/usr/bin/env python

from Grapher import Grapher
from SystemEvents import *

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

    def process_trace(self, metrics, tracecmd, duration, draw=None, test=None, subgraph=False):
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
        print "Processing trace"

        if not tracecmd.processed_events:
            sys.exit("Processing trace failed")

        process_tree = ProcessTree(self.pidt, metrics)
        trace_start_time = tracecmd.processed_events[0].time
        if tracecmd.processed_preprocess_events[0].time < trace_start_time:
            trace_start_time = tracecmd.processed_preprocess_events[0].time
        trace_finish_time = int(trace_start_time + float(duration) * 1000000)

        start_time = time.time()
        print "Compiling util and temp trees"

        for x, event in enumerate(tracecmd.processed_preprocess_events):
            process_tree.handle_event(event, subgraph, trace_start_time, trace_finish_time)

        print("Util trees took %s seconds to build" % (time.time() - start_time))

        start_time = time.time()
        print "Compiling cluster util tables"

        for x, cluster in enumerate(metrics.sys_util_history.clusters):  # Compile cluster utilizations
            cluster.compile_table(metrics.sys_util_history.cpu[x * 4: x * 4 + 4])

        print("Cluster util table generated in %s seconds" % (time.time() - start_time))

        num_events = len(tracecmd.processed_events)
        print "Total events: " + str(num_events)

        start_time = time.time()
        print "Processing events"

        # TODO does it matter if the first event is a mali event?
        metrics.sys_util_history.gpu.init(trace_start_time, trace_finish_time, metrics.current_gpu_util)

        if test:
            for x, event in enumerate(tracecmd.processed_events[:test]):
                print str(x) + "/" + str(num_events) + " " + str(round(float(x) / num_events * 100, 2)) + "%\r",
                if process_tree.handle_event(event, subgraph, trace_start_time, trace_finish_time):
                    break
        else:
            for x, event in enumerate(tracecmd.processed_events):
                print str(x) + "/" + str(num_events) + " " + str(round(float(x) / num_events * 100, 2)) + "%\r",
                if process_tree.handle_event(event, subgraph, trace_start_time, trace_finish_time):
                    break

        print("All events handled in %s seconds" % (time.time() - start_time))

        start_time = time.time()
        print "Finishing process tree"

        process_tree.finish_tree(self.filename)

        print("Finished tree in %s seconds" % (time.time() - start_time))

        if draw:

            start_time = time.time()
            draw_graph = Grapher(process_tree)
            draw_graph.draw_graph()

            print("Graph drawn in %s seconds" % (time.time() - start_time))

        print("Processing finished in %s seconds" % (time.time() - process_start_time))
