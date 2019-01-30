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
                            functions="schedule",
                            trace_type="function",
                            duration=5)
    schedule_tracer.run()
    tp.filterTracePID(schedule_tracer, PIDt)




if __name__ == '__main__':
    main()
