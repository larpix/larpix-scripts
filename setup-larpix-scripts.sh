#!/bin/bash
echo "larpix-scripts home: $(dirname "`pwd`/${BASH_SOURCE[0]}")"
LARPIX_SCRIPT_DIR="$(dirname "`pwd`/${BASH_SOURCE[0]}")"

echo "creating aliases..."
alias larpix-check-pedestal="python $LARPIX_SCRIPT_DIR/check_pedestal_width_low_threshold.py"
alias larpix-check-leakage="python $LARPIX_SCRIPT_DIR/check_leakage.py"
alias larpix-configure="python $LARPIX_SCRIPT_DIR/configure_chips.py"
alias larpix-check-sensitivity="python $LARPIX_SCRIPT_DIR/check_channel_sensitivity.py"
alias larpix-run="python $LARPIX_SCRIPT_DIR/collect_data.py"

echo "done"