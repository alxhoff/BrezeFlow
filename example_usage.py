from adbinterface import adbInterface
from pidtrace import PIDtracer
from metrics import SystemMetrics
from pytracer import Tracer
from traceprocessor import TraceProcessor
import argparse
from constants_xu3 import EnergyProfile

# parser = argparse.ArgumentParser()
#
# parser.add_argument("-l", "--little", nargs=5, required=True, type=int, default=None,
#                     help="List of frequencies for the little core, from smallest to greatest")
# parser.add_argument("-le", "--little_energy", nargs=5, required=True, type=float, default=None,
#                     help="List of clock cycle energy for the little core frequencies")
# parser.add_argument("-b", "--big", nargs=9, required=True, type=int, default=None,
#                     help="List of frequencies for the big core, from smallest to greatest")
# parser.add_argument("-be", "--big_energy", nargs=9, required=True, type=float, default=None,
#                     help="List of clock cycle energy for the big core frequencies")
# parser.add_argument("-g", "--gpu", nargs=6, required=True, type=int, default=None,
#                     help="List of frequencies for the GPU, from smallest to greatest")
# parser.add_argument("-ge", "--gpu_energy", nargs=6, required=True, type=float, default=None,
#                     help="List of clock cycle energy for the CPU frequencies")
#
# args = parser.parse_args()

def main():
    adbBridge = adbInterface()
    tp = TraceProcessor()
    PIDt = PIDtracer(adbBridge, "hillclimb")
    #PIDt = PIDtracer(adbBridge, "miami")

    xu3_energy = EnergyProfile()

    sys_metrics = SystemMetrics(adbBridge, xu3_energy)

    # combo_tracer = Tracer(adbBridge,
    #                      "combo",
    #                       events=["binder_transaction",
    #                      "sched_switch", "cpu_frequency",
    #                      "mali_utilization_stats"],
    #                       PID_filter=PIDt,
    #                       duration=1,
    #                       metrics=sys_metrics)
    # combo_tracer.runTracer()
    # tp.process_tracer(combo_tracer, PIDt)
    tp.process_trace_file("combo_tracer.trace", PIDt, sys_metrics)
    # tp.filterTracePID(combo_tracer, PIDt, combo_tracer.filename)


if __name__ == '__main__':
    main()
