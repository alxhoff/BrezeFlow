import logging

class traceProcessor:

    def __init__(self):
        logging.basicConfig(filename="pytracer.log", format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Trace processor created")

    def filterTracePID(self, tracer, PID, output_filename=""):
        if output_filename == "":
            output_filename = tracer.filename + "_filtered"
        f = open(tracer.filename)
        unfiltered = f.readlines()
        filtered = []
        for x, line in enumerate(unfiltered): #make sure that PID isn't in time stamp
            split_line = line.split('[')
            if any(pid in split_line[0] for pid in PID.allPIDstrings) or x < 11:
                filtered.append(line)

        f = open(output_filename, 'w')
        f.writelines(filtered)
        self.logger.debug("Written filtered lines to: " + output_filename)
        f.close()

