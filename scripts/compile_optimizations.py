#!/usr/bin/env python

import argparse
import csv
import os

#  This script compiles a folder of automated tests into a single average results file

parser = argparse.ArgumentParser()

parser.add_argument("-f", "--folder", required=True, type=str, help="Specify folder where results can be found")
parser.add_argument("-a", "--application", required=True, type=str, help="Spcifies the applications name")
parser.add_argument("-g", "--governor", required=True, type=str, help="Specifies the governor used in the test")

args = parser.parse_args()

folder = args.folder
application = args.application
governor = args.governor
script_dir = os.path.dirname(os.path.realpath(__file__))
input_dir = os.path.join(script_dir, folder)


def writerEmptyRow(writer):
    writer.writerow([])


def writeResultsHeader(writer, governor, application):
    writer.writerow(["Governor: {}".format(governor), "Application: {}".format(application)])
    writerEmptyRow(writer)
    writer.writerow(["B2L Reallocations", "DVFS", "Realloc in cluster", "DVFS after realloc"])


def findOptimizationsRow(filepath):
    with open(filepath, mode='r') as f:

        f_wr = csv.reader(f, delimiter=",")

        found = False

        for row in f_wr:
            if found:
                optimizations = row[1:5]
                return optimizations
            try:
                if row[0] == "Optimizations":
                    found = True
            except Exception:
                pass


def getResults():
    results = [0, 0, 0, 0]
    for directory, subdirectory, files in os.walk(input_dir):
        for sd in subdirectory:
            for d, s, f in os.walk(os.path.join(directory, sd)):
                for r_file in f:
                    if "results" in r_file:
                        test = os.path.join(d, r_file)
                        res = findOptimizationsRow(test)
                        if (len(res) != 4):
                            raise Exception("File {} failed to process".format(test))
                        else:
                            for i in range(len(res)):
                                results[i] += int(res[i])

    return results


try:
    results = getResults()
except Exception as e:
    print(e)

output_file = os.path.join(folder, "compiled.csv")

with open(output_file, mode="w+") as f:
    fw = csv.writer(f, delimiter=',', quoting=csv.QUOTE_MINIMAL)

    writeResultsHeader(fw, governor, application)
    fw.writerow(results)
