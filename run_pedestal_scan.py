from os import system
import sys
from larpix.quickstart import board_info_map
import time

specifier = time.strftime('%Y_%m_%d_%H_%M')

for chip_idx,chip in enumerate(board_info_map['pcb-10']['chip_list']):
    command = ('python check_pedestal_width_low_threshold.py pcb-10_chip_info.json '
               'datalog/pedestal_%s -v --chips %d' % (specifier, chip[0]))
    print(command)
    system(command)
               
