#! /bin/bash

for entry in "$(dirname $0)"/*.ui; do
    filename=$(basename -- $entry)
    outputfilename="${filename%.*}"
    outputfilename="../$outputfilename.py"
    echo "$filename"
    echo "$outputfilename"
    pyuic5 $filename -o $outputfilename
done
