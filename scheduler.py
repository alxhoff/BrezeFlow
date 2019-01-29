from pytracer import tracer
from adb_interface import adbInterface

def main():
    adbBridge = adbInterface()
    adbBridge.createPIDtool("hillclimb")


if __name__ == '__main__':
    main()
