#!/bin/bash/env python

import argparse
import os
import math
import csv
import array
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

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
                                            apps[current_app][current_governor] = row[0:5]

        for name in app_names:
            writer.writerow([name])
            for gov in governors:
                res = apps[name][gov]
                writer.writerow([gov, res[0], res[1], res[2], res[3], res[4]])
            writer.writerow([])

# Bar graph
app_count = len(app_names)
xlabels = []
for app in app_names:
    xlabels.append(app.replace("_", " "))
gov_count = len(governors)

n_groups = app_count

#indicies
index = np.arange(n_groups)
bar_width = 0.15
opacity = 0.8

titles = ['Big To Little Reallocations', 'DVFS Misdecisions', 'Intra-Cluster Reallocations', 'DVFS After Reallocations']

y_top_margin = 0.2
colors = ['0', '0.2', '0.4', '0.6', '0.8']

matplotlib.rcParams['font.serif'] = 'Times New Roman'

fig, ax = plt.subplots(4, 1)
fig.set_size_inches(8, 11)
fig.subplots_adjust(hspace=0.2)
#figure axes
#TODO
count = 0
#  for i in range(1):
for j in range(4):
    x_coords = []
    y_max = 0

    for x, gov in enumerate(governors):
        bars = []
        if x:
            x_coords.append([x + bar_width for x in x_coords[x - 1]])
        else:
            x_coords.append(index)

        for app in app_names:
            dvfs_val = int(apps[app][gov][count])
            if dvfs_val > y_max:
                y_max = dvfs_val
            bars.append(dvfs_val)

        try:
            ax[j].bar(x_coords[x], bars, bar_width, alpha=opacity, color=colors[x], label=gov)
        except Exception as e:
            print("wait here")
        if j == 3:
            ax[j].set_ylabel('Misdecisions (count/15ms)')
        ax[j].set(
            title=titles[count],
            xticks=index + 1.5 * bar_width,
        )
        #  xticklabels=app_names,
        ax[j].tick_params('x', labelrotation=30)
        ax[j].set_xticklabels(labels=xlabels, horizontalalignment='right', wrap=True)
        ax[j].label_outer()

        #  if j == 1:
        #      ax[i,j].

    count += 1

gov_legend = ["Powersave+CFS", "Performance+CFS", "Interactive+CFS", "OnDemand+CFS", "GameGovernor"]
fig.legend(labels=gov_legend, ncol=3, loc="upper center", frameon=False)
#  fig.tight_layout(pad=4.5)
fig.savefig('result_fig.png', dpi=300, format='png')

fig2, ax2 = plt.subplots()
fig2.set_size_inches(8, 4)

x_coords = []
ymax = 0

for x, gov in enumerate(governors):
    bars = []

    if x:
        x_coords.append([x + bar_width for x in x_coords[x - 1]])
    else:
        x_coords.append(index)

    for app in app_names:
        dvfs_val = int(apps[app][gov][4])
        if dvfs_val > y_max:
            y_max = dvfs_val
        bars.append(dvfs_val)

    ax2.bar(x_coords[x], bars, bar_width, alpha=opacity, color=colors[x], label=gov)
    ax2.set(title='Total Misdecisions', xticks=index + 1.5 * bar_width, xticklabels=app_names)
    ax2.tick_params('x', labelrotation=30)
    ax2.set_xticklabels(labels=xlabels, horizontalalignment='right', wrap=True)

fig2.legend(frameon=False, ncol=len(governors), loc='upper center')
fig2.tight_layout(pad=2.5)
fig2.savefig('totals_fig.png', dpi=300, format='png')

#  plt.show()
