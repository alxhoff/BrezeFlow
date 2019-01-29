from pytracer import tracer

def main():
    test = tracer("CPU_scheduler")
    test.getTraceResults()

if __name__ == '__main__':
    main()
