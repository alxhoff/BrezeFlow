#! /bin/bash

for entry in "$(dirname $0)"/*.ui; do
    pushd $(dirname $0)
    filename=$(basename -- $entry)
    outputfilename="${filename%.*}"
    outputfilename="../$outputfilename.py"
    pyuic5 $filename -o $outputfilename
done
