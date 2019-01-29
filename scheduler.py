from pytracer import tracer
from adb_interface import adbInterface

def main():
    adbBridge = adbInterface()
    adbBridge.createPIDtool("hillclimb")
    adbBridge.createTracer("schedule",
                            functions="schedule",
                            trace_type="function",
                            duration=5)
    adbBridge.runTracers()


if __name__ == '__main__':
    main()
