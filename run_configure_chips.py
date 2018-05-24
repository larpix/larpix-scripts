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
        help='The chip ID(s) to configure', default=[])
parser.add_argument('-t', '--threshold_rate', type=float, default=0.9,
                    help='Threshold rate for configuring chips (optional, units: Hz, default:'
                    ' %(default)s)')
args = parser.parse_args()

board_info = json.load(open(args.board,'r'))

for chip in board_info['chip_set']:
    if (not args.chip) or chip[0] in args.chip:
        command = ('python configure_chips.py '
                   '-o %s -v --chips %d --threshold_rate %f' % (\
                pathnames.default_script_logdir(start_time), chip[0], args.threshold_rate))
        print(command)
        system(command)
               
