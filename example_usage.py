from adbinterface import adbInterface
from pidtrace import PIDtracer
from metrics import SystemMetrics
from pytracer import tracer
from traceprocessor import traceProcessor
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("-l", "--little", nargs=5, required=True, type=float, default=None,
                    help="List of frequencies for the little core, from smallest to greatest")
parser.add_argument("-b", "--big", nargs=9, required=True, type=float, default=None,
                    help="List of frequencies for the big core, from smallest to greatest")
parser.add_argument("-g", "--gpu", nargs=6, required=True, type=float, default=None,
                    help="List of frequencies for the GPU, from smallest to greatest")

args = parser.parse_args()

def main():
    adbBridge = adbInterface()
    tp = traceProcessor()
    PIDt = PIDtracer(adbBridge, "hillclimb")

    sys_metrics = SystemMetrics(adbBridge, args.little, args.big, args.gpu)

    #combo_tracer = tracer(adbBridge,
    #                      "combo",
    #                      events=["binder_transaction", "sched_switch", "cpu_frequency", "mali_utilization_stats"],
    #                      PID_filter=PIDt,
    #                      duration=1)
    #combo_tracer.runTracer()
    #tp.process_tracer(combo_tracer, PIDt)
    tp.process_trace_file("combo_tracer.trace", PIDt)
    # tp.filterTracePID(combo_tracer, PIDt, combo_tracer.filename)


if __name__ == '__main__':
    main()
