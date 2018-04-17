from os import system
import sys
from larpix.quickstart import board_info_map
import helpers.pathnames as pathnames
import time

start_time = time.localtime()

for chip_idx,chip in enumerate(board_info_map['pcb-1']['chip_list']):
    command = ('python check_pedestal_width_low_threshold.py '
               '-o %s -v --chips %d' % (pathnames.default_script_logdir(start_time), chip[0]))
    print(command)
    system(command)
               
