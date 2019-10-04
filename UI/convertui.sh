#! /bin/bash

pushd $(dirname $0)
for entry in "$(dirname $0)"/*.ui; do
    filename=$(basename -- $entry)
    outputfilename="${filename%.*}"
    outputfilename="../$outputfilename.py"
    echo "pyuic5 $filename -o $outputfilename"
    pyuic5 $filename -o $outputfilename
done
