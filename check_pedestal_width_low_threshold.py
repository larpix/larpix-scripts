'''
This script runs noise_tests.noise_test_low_threshold on a specified chip set
Requires noise_tests library
Requires a .json file containing chip-ids and daisy chain data formatted like
{
    'board': <board-name>,
    'chip_set': [
        [<chip-id>, <io-chain>],
        ...
        ]
}
'''

from __future__ import print_function
import argparse
import logging
import time
import larpix.larpix as larpix
import noise_tests
from sys import (exit, stdout)
import json
import os

def clear_buffer_quick(controller):
    controller.run(0.05,'clear buffer (quick)')

def clear_buffer(controller):
    buffer_clear_attempts = 5
    clear_buffer_quick(controller)
    while len(controller.reads[-1]) > 0 and buffer_clear_attempts > 0:
        clear_buffer_quick(controller)
        buffer_clear_attempts -= 1

def verify_chip_configuration(controller):
    clear_buffer(controller)
    config_ok, different_registers = controller.verify_configuration()
    if not config_ok:
        log.warn('chip configurations were not verified - retrying')
        clear_buffer(controller)
        config_ok, different_registers = controller.verify_configuration()
        if not config_ok:
            log.warn('chip configurations could not be verified')
            log.warn('different registers: %s' % str(different_registers))

parser = argparse.ArgumentParser()
parser.add_argument('infile',
                    help='input file containing chipset info (required)')
parser.add_argument('outdir', nargs='?', default='.',
                    help='output directory for log file'
                    '(optional, default: %(default)s)')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('--global_threshold', default=0, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--run_time', default=0.05, type=int,
                    help='(optional, units: sec,  default: %(default)s)')
parser.add_argument('--configuration_file', default='physics.json',
                    help='initial chip configuration file to load '
                    '(optional, default: %(default)s)')
parser.add_argument('--chips', default=None, type=str,
                    help='chips to include in scan, string of chip_ids separated by commas'
                    '(optional, default: None=all chips in chipset file)')
args = parser.parse_args()

infile = args.infile
outdir = args.outdir
verbose = args.verbose
global_threshold = args.global_threshold
run_time = args.run_time
config_file = args.configuration_file
if not args.chips is None:
    chips_to_scan = [int(chip_id) for chip_id in args.chips.split(',')]
else:
    chips_to_scan = None

return_code = 0

if not os.path.exists(outdir):
    os.makedirs(outdir)
logfile = outdir + '/.check_pedestal_width_low_threshold_%s.log' % \
    str(time.strftime('%Y_%m_%d_%H_%M_%S',time.localtime()))
log = logging.getLogger(__name__)
fhandler = logging.FileHandler(logfile)
shandler = logging.StreamHandler(stdout)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
fhandler.setFormatter(formatter)
shandler.setFormatter(formatter)
log.addHandler(fhandler)
log.addHandler(shandler)
log.setLevel(logging.DEBUG)
log.info('start of new run')
log.info('logging to %s' % logfile)

try:
    larpix.enable_logger()
    controller = larpix.Controller(timeout=0.01)
    # Initial configuration of chips
    chip_set = json.load(open(infile,'r'))
    board_info = chip_set['board']
    log.info('begin initial configuration of chips for board %s' % board_info)
    for chip_tuple in chip_set['chip_set']:
        chip_id = chip_tuple[0]
        io_chain = chip_tuple[1]
        controller.chips.append(larpix.Chip(chip_id, io_chain))
        chip = controller.chips[-1]
        chip.config.load(config_file)
        controller.write_configuration(chip)
        controller.disable(chip_id=chip_id, io_chain=io_chain)
    log.info('initial configuration of chips complete')

    verify_chip_configuration(controller)

    # Run low pedestal test on each chip
    board_results = []
    for chip_idx,chip in enumerate(controller.chips):
        try:
            start_time = time.time()
            chip_id = chip.chip_id
            io_chain = chip.io_chain
            chip_info = (chip_id, io_chain)
            if chips_to_scan is None:
                pass
            else:
                if not chip_id in chips_to_scan:
                    log.info('skipping c%d-%d' % chip_info)
                    board_results += [None]
                    continue

            clear_buffer(controller)
            chip_results = noise_tests.noise_test_low_threshold(controller=controller,
                                                                chip_idx=chip_idx,
                                                                global_threshold=\
                                                                    global_threshold,
                                                                run_time=run_time)
            board_results += [chip_results[1:]]
            finish_time = time.time()
            if verbose:
                log.debug('c%d-%d pedestal scan took %.2f s' % \
                              (chip_id, io_chain, finish_time - start_time))
        except Exception as error:
            log.exception(error)
            log.error('c%d-%d pedestal scan failed!' % chip_info)
            controller.disable(chip_id=chip_id, io_chain=io_chain)
            return_code = 2
            continue

    log.info('all chips pedestal complete')

    # Print pedestal scan results
    for chip_idx,chip in enumerate(controller.chips):
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        if board_results[chip_idx] is None:
            log.info('%s-c%d-%d skipped' % (board_info, chip_id, io_chain))
            continue
        chip_ped_mean = sum(board_results[chip_idx][0].values()) /\
            len(board_results[chip_idx][0].values())
        chip_ped_rms = sum(abs(ped - chip_ped_mean)
                           for ped in board_results[chip_idx][0].values()) /\
                           len(board_results[chip_idx][0])
        log.info('%s-c%d-%d mean pedestal: %.2f adc, rms: %.2f adc' % \
                     (board_info, chip_id, io_chain, chip_ped_mean, chip_ped_rms))

        chip_width_mean = sum(board_results[chip_idx][1].values()) /\
            len(board_results[chip_idx][1].values())
        chip_width_rms = sum(abs(width - chip_width_mean)
                             for width in board_results[chip_idx][1].values())/\
                             len(board_results[chip_idx][1])
        log.info('%s-c%d-%d mean width: %.2f adc, rms: %.2f adc' % \
                     (board_info, chip_id, io_chain, chip_width_mean, chip_width_rms))
        for channel in board_results[chip_idx][0].keys():
            log.info('%s-c%d-%d-ch%d pedestal: %.2f adc, width: %.2f adc' % \
                         (board_info, chip_id, io_chain, channel,
                          board_results[chip_idx][0][channel],
                          board_results[chip_idx][1][channel]))
except Exception as error:
    log.exception(error)
    return_code = 1

exit(return_code)
