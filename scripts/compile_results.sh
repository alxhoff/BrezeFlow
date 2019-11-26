#!/bin/bash

#script to iterate through each application and each governor,
#compiling the results as it goes

RESULTS_DIR=$1
for D in $RESULTS_DIR*/; do
    if [ -d "${D}" ]; then
        APP=$(basename $D)
        for dir in $D*/; do
            if [ -d "${dir}" ]; then
                GOVERNOR=$(basename $dir)
                COMMAND="python compile_optimizations.py -f $dir -a $APP -g $GOVERNOR"
                echo $COMMAND
                eval $COMMAND
            fi
        done
    fi
done
