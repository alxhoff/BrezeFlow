from SystemEvents import *
from Grapher import *


class TraceProcessor:

    def __init__(self, pidt, filename):
        self.pidt = pidt
        self.filename = filename

    def process_trace(self, metrics, tracecmd, duration, draw=None, test=None, subgraph=False):

        process_start_time = time.time()
        print "Processing trace"

        processed_events = tracecmd.processed_events

        if not processed_events:
            sys.exit("Processing trace failed")

        # generate pointers to most recent nodes for each PID (branch heads)
        process_tree = ProcessTree(self.pidt, metrics)
        trace_start_time = processed_events[0].time
        trace_finish_time = trace_start_time + int(duration) * 1000000

        # Create CPU core utilization trees first
        start_time = time.time()
        print "Compiling util and temp trees"
        i = 0
        length = len(processed_events)
        while i < length:
            if isinstance(processed_events[i], EventIdle) or isinstance(processed_events[i], EventTempInfo):
                process_tree.handle_event(processed_events[i], subgraph, trace_start_time, trace_finish_time)
                del processed_events[i]
                length -= 1
            elif processed_events[i] is None:
                del processed_events[i]
                length -= 1
            else:
                i += 1
        print ("Util trees took %s seconds to build" % (time.time() - start_time))

        # Init GPU util tree
        # set initial time as first event in log as mali util is able to be found via sysfs
        # and as such is available from the start and must not be calculated
        # TODO does it matter if the first event is a mali event?
        metrics.sys_util.gpu_utils.init(trace_start_time, trace_finish_time, metrics.gpu_util)

        # Compile cluster utilizations
        start_time = time.time()
        print "Compiling cluster util tables"
        for x, cluster in enumerate(metrics.sys_util.cluster_utils):
            cluster.compile_table(metrics.sys_util.core_utils[x * 4: x * 4 + 4])
        print ("Cluster util table generated in %s seconds" % (time.time() - start_time))

        start_time = time.time()
        print "Compiling temp tables"
        SystemMetrics.current_metrics.compile_temps_table()
        print ("Temp table generated in %s seconds" % (time.time() - start_time))

        num_events = len(processed_events)
        print "Total events: " + str(num_events)

        start_time = time.time()
        print "Processing events"
        if test:
            for x, event in enumerate(processed_events[:300]):
                print str(x) + "/" + str(num_events) + " " + str(round(float(x) / num_events * 100, 2)) + "%\r",
                process_tree.handle_event(event, subgraph, trace_start_time, trace_finish_time)
        else:
            for x, event in enumerate(processed_events):
                print str(x) + "/" + str(num_events) + " " + str(round(float(x) / num_events * 100, 2)) + "%\r",
                process_tree.handle_event(event, subgraph, trace_start_time, trace_finish_time)
        print ("All events handled in %s seconds" % (time.time() - start_time))

        start_time = time.time()
        print "Finishing process tree"
        process_tree.finish_tree(self.filename)
        print ("Finished tree in %s seconds" % (time.time() - start_time))

        if draw:
            start_time = time.time()
            draw_graph = Grapher(process_tree)
            draw_graph.draw_graph()
            print ("Graph drawn in %s seconds" % (time.time() - start_time))

        print ("Processing finished in %s seconds" % (time.time() - process_start_time))
