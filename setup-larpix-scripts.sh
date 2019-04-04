#!/bin/bash
LARPIX_SCRIPT_DIR="$(dirname "`pwd`/${BASH_SOURCE[0]}")"
BERN_DAQ_BOARD_LOGIN="ubuntu@10.0.1.6"

echo "larpix-scripts home: $LARPIX_SCRIPT_DIR"
echo "Bern DAQ board login: $BERN_DAQ_BOARD_LOGIN"

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
alias larpix-check-pedestal="python $LARPIX_SCRIPT_DIR/check_pedestal_width_low_threshold.py -p"
alias larpix-check-leakage="python $LARPIX_SCRIPT_DIR/check_leakage.py -p"
alias larpix-configure="python $LARPIX_SCRIPT_DIR/configure_chips.py"
alias larpix-check-sensitivity="python $LARPIX_SCRIPT_DIR/check_channel_sensitivity.py -p"
alias larpix-run="python $LARPIX_SCRIPT_DIR/collect_data.py"
alias larpix-run-interactive="python -i $LARPIX_SCRIPT_DIR/collect_data.py"
alias larpix-connect-to-daq="xterm -e 'while true; do ssh ${BERN_DAQ_BOARD_LOGIN}; sleep 1; done' &"
alias larpix-run-daq="xterm -e \"while true; do ssh -t ${BERN_DAQ_BOARD_LOGIN} \\\"sudo ./setup; sudo halt\\\"; sleep 1; done\" &"
alias larpix-kill-daq="ssh -t ${BERN_DAQ_BOARD_LOGIN} \"sudo pkill -f \\\"pixlar\\\"\""

echo "done"