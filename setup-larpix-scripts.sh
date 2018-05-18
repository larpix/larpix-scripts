#!/bin/bash
LARPIX_SCRIPT_DIR="$(dirname "`pwd`/${BASH_SOURCE[0]}")"
echo "larpix-scripts home: $LARPIX_SCRIPT_DIR"
# add larpix-scripts to python path
export PYTHONPATH="${PYTHONPATH}:${LARPIX_SCRIPT_DIR}"

if [ ! -z "$1" ]
# generate a default board layout file (if passed one)
    then
    echo "generating default board config: "
    python_command="
from helpers.pathnames import make_default_board;
from time import localtime;
print(make_default_board(localtime(), '$1', force=True))"
    echo $python_command | python
fi

echo "creating aliases..."
alias larpix-check-pedestal="python $LARPIX_SCRIPT_DIR/run_pedestal_scan.py"
alias larpix-check-leakage="python $LARPIX_SCRIPT_DIR/run_leakage.py"
alias larpix-configure="python $LARPIX_SCRIPT_DIR/run_configure_chips.py"
alias larpix-check-sensitivity="python $LARPIX_SCRIPT_DIR/run_channel_sensitivity.py"
alias larpix-run="python $LARPIX_SCRIPT_DIR/collect_data.py"

echo "done"