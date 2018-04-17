from os import system
import sys
from larpix.quickstart import board_info_map
import helpers.pathnames as pathnames
import time

start_time = time.localtime()

for chip in board_info_map['pcb-1']['chip_list']:
    command = ('python configure_chips.py '
               '-o %s -v --chips %d' % (pathnames.default_script_logdir(start_time), chip[0]))
    print command
    system(command)
               
