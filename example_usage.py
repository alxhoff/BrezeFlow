from adbinterface import adbInterface
from metrics import SystemMetrics
from pidtrace import PIDtracer
from pytracer import Tracer
from traceprocessor import TraceProcessor


def main():
    adbBridge = adbInterface()
    tp = TraceProcessor()
    PIDt = PIDtracer(adbBridge, "hillclimb")
    # PIDt = PIDtracer(adbBridge, "miami")

    sys_metrics = SystemMetrics(adbBridge)

    combo_tracer = Tracer(adbBridge,
                          "combo",
                          events=["binder_transaction", "cpu_idle",
                                  "sched_switch", "cpu_frequency", "update_cpu_metric",
                                  "mali_utilization_stats"],
                          PID_filter=PIDt,
                          duration=1,
                          metrics=sys_metrics)
    combo_tracer.runTracer()
    tp.process_tracer(combo_tracer, PIDt)
    # tp.process_trace_file("combo_tracer.trace", PIDt, sys_metrics)
    # tp.filterTracePID(combo_tracer, PIDt, combo_tracer.filename)


if __name__ == '__main__':
    main()
