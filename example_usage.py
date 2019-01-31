from pytracer import tracer
from adb_interface import adbInterface
from traceprocessor import traceProcessor
from pid_trace import PIDtracer

def main():
    adbBridge = adbInterface()
    tp = traceProcessor()
    PIDt  = PIDtracer(adbBridge, "hillclimb")

    #trace schedule
    schedule_tracer = tracer(adbBridge,
                            "schedule",
                            events=["sched_switch", "sched_wakeup"],
                            PID_filter=PIDt,
                            duration=1)
    schedule_tracer.runTracer()

    tp.filterTracePID(schedule_tracer, PIDt)




if __name__ == '__main__':
    main()
