import logging

class traceProcessor:

    def __init__(self):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Trace processor created")

    def filterTracePID(self, tracer, PIDtracer, output_filename=""):
        if output_filename == "":
            output_filename = tracer.filename + "_filtered"
        f = open(tracer.filename)
        unfiltered = f.readlines()
        filtered = []
        pids = PIDtracer.getPIDStrings()
        for x, line in enumerate(unfiltered): #make sure that PID isn't in time stamp
            if any(("=" + pid) in line for pid in pids) or x < 11:
                filtered.append(line)

        f = open(output_filename, 'w')
        f.writelines(filtered)
        self.logger.debug("Written filtered lines to: " + output_filename)
        f.close()



