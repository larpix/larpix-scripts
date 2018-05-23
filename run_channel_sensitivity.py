from os import system
import sys
from larpix.quickstart import board_info_map
import helpers.pathnames as pathnames
import time
import argparse
import json

start_time = time.localtime()

parser = argparse.ArgumentParser()
parser.add_argument('-b', '--board', type=str,
                    default=pathnames.default_board_file(start_time),
                    help='path to .json file containing chip set info (default: %(default)s)')
parser.add_argument('-c', '--chip', type=int, nargs='*',
        help='The chip ID(s) to measure', default=[])
parser.add_argument('-t', '--threshold-correction', type=int,
        help='The global threshold correction (default: %(default)s)', default=1)
parser.add_argument('-s', '--config', required=False,
                    default=pathnames.default_config_dir(start_time),
        help='The configuration to load onto the chip(s) (default: %(default)s)')
args = parser.parse_args()

global_threshold_correction = args.threshold_correction

board_info = json.load(open(args.board,'r'))

for chip in board_info['chip_set']:
    if (not args.chip) or chip[0] in args.chip:
        command = ('python check_channel_sensitivity.py '
                   '-o %s '
                   '--global_threshold_correction %d '
                   '--configuration_file %s '
                   '-v --chips %d' % (pathnames.default_script_logdir(start_time),
                                      global_threshold_correction, args.config,
                                      chip[0]))
        print(command)
        system(command)
