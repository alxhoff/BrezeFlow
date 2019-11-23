#!/bin/bash/env python

import argparse
import os
import csv
import array
import numpy as np
import matplotlib.pyplot as plt

# Compiles results from a folder containing the results from various apps into
# a single file with the results all desplayed in a single table

parser = argparse.ArgumentParser()

parser.add_argument("-f", "--folder", required=True, type=str, help="Relative location to the folder where results can be found")

args = parser.parse_args()

folder = args.folder

if os.path.isabs(folder):
    input_dir = folder
else:
    script_dir = os.path.dirname(os.path.realpath(__file__))
    input_dir = os.path.join(script_dir, folder)

# Get apps
apps = dict()

app_names = []
governors = []

# Populate dict with empty results arrays
for directory, subdirectory, files in os.walk(input_dir):
    with open(os.path.join(folder, "resuls.csv"), mode="w+") as f:
        writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        # for each app
        for sd in subdirectory:
            if app_names == []:
                app_names = subdirectory
            current_app = sd
            apps[current_app] = dict()
            # for each governor subdir - sdx
            for dx, gov_dirs, fx in os.walk(os.path.join(directory, sd)):
                if governors == []:
                    governors = gov_dirs
                for gov_dir in gov_dirs:
                    current_governor = gov_dir
                    apps[current_app][current_governor] = []
                    # find compiled file
                    for dxx, sdxx, fx in os.walk(os.path.join(dx, current_governor)):
                        for f in fx:
                            if "compiled" in f:
                                with open(os.path.join(dxx, f)) as fl:
                                    reader = csv.reader(fl, delimiter=",")
                                    for i, row in enumerate(reader):
                                        if i == 3:
                                            apps[current_app][current_governor] = row[0:4]

        for name in app_names:
            writer.writerow([name])
            for gov in governors:
                res = apps[name][gov]
                writer.writerow([gov, res[0], res[1], res[2], res[3]])
            writer.writerow([])

# Bar graph
app_count = len(app_names)
gov_count = len(governors)

n_groups = app_count

fig, ax = plt.subplots()

#indicies
index = np.arange(n_groups)
bar_width = 0.15
opacity = 0.8

B2L_realloc = 0
DVFS = 1
Realloc_in_cluster = 2
DVFS_after_realloc = 3

#dvfs graph
x_coords = []

colors = ['b', 'g', 'r', 'y']

y_max = 0
y_top_margin = 0.2

for x, gov in enumerate(governors):
    bars = []
    if x:
        x_coords.append([x + bar_width for x in x_coords[x - 1]])
    else:
        x_coords.append(index)

    for app in app_names:
        dvfs_val = int(apps[app][gov][DVFS])
        if dvfs_val > y_max:
            y_max = dvfs_val
        bars.append(dvfs_val)

    plt.bar(x_coords[x], bars, bar_width, alpha=opacity, color=colors[x], label=gov)

plt.xlabel('Applications')
plt.ylabel('Missdecision Count')

plt.title('DVFS Missdevisions')

y_max *= (1 + y_top_margin)
plt.yticks(np.arange(0, int(round(y_max)), step=20000))
plt.xticks(index + bar_width, app_names)
plt.legend()

plt.tight_layout()
plt.show()
