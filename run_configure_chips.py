from os import system
import sys
from larpix.quickstart import board_info_map
import time

specifier = time.strftime('%Y_%m_%d_%H_%M')

for chip in board_info_map['pcb-10']['chip_list']:
    command = ('python configure_chips.py pcb-10_chip_info.json '
               'datalog/configure_chips_%s -v --chips "%d"' % (specifier, chip[0]))
    print command
    system(command)
               
