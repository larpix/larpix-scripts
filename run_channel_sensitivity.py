from os import system
import sys
from larpix.quickstart import board_info_map
import time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--chip', type=int, nargs='*',
        help='The chip ID(s) to measure', default=[])
parser.add_argument('-t', '--threshold-correction', type=int,
        help='The global threshold correction', default=1)
parser.add_argument('-s', '--config', required=True,
        help='The configuration to load onto the chip(s)')
args = parser.parse_args()

specifier = time.strftime('%Y_%m_%d_%H_%M')

global_threshold_correction = args.threshold_correction


for chip in board_info_map['pcb-10']['chip_list']:
    if (not args.chip) or chip[0] in args.chip:
        command = ('python check_channel_sensitivity.py pcb-10_chip_info.json '
                   'datalog/channel_sensitivty_%s '
                   '--global_threshold_correction %d '
                   '--configuration_file %s '
                   '-v --chips "%d"' % (specifier, global_threshold_correction, args.config,
                                        chip[0]))
        print command
        system(command)
