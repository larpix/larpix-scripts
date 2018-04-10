'''
This script runs noise_tests.test_min_signal_amplitude on a specified chip set
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
from helpers.logging import ScriptLogger
import time
import larpix.larpix as larpix
import helpers.noise_tests as noise_tests
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
parser.add_argument('--global_threshold_correction', default=0, type=int,
                    help='Amount to increase the global threshold on each chip'
                    ' for sensitivity test'
                    '(optional, default: %(default)s)')
parser.add_argument('--pixel_trim_correction', default=0, type=int,
                    help='Amount to increase the pixel trim on each channel'
                    ' for sensitivity test'
                    '(optional, default: %(default)s)')
parser.add_argument('--max_dac_amp', default=10, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--min_dac_amp', default=0, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--n_pulses', default=10, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--configuration_file', default='physics.json',
                    help='initial chip configuration file to load '
                    'will attempt to load with chip_id replacement first'
                    '(optional, default: %(default)s)')
parser.add_argument('--chips', default=None, type=str,
                    help='chips to include in scan, string of chip_ids separated by commas'
                    '(optional, default: None=all chips in chipset file)')
args = parser.parse_args()

infile = args.infile
outdir = args.outdir
verbose = args.verbose
global_threshold_correction = args.global_threshold_correction
pixel_trim_correction = args.pixel_trim_correction
max_dac_amp = args.max_dac_amp
min_dac_amp = args.min_dac_amp
n_pulses = args.n_pulses
config_file = args.configuration_file
if not args.chips is None:
    chips_to_scan = [int(chip_id) for chip_id in args.chips.split(',')]
else:
    chips_to_scan = None

return_code = 0

sl = ScriptLogger('check_channel_sensitivity')
log = sl.script_log
if outdir is None:
    outdir = sl.script_logdir

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
        chip_info = (chip_id, io_chain)
        controller.chips.append(larpix.Chip(chip_id, io_chain))
        chip = controller.chips[-1]
        try:
            chip.config.load(config_file % chip_id)
        except:
            try:
                chip.config.load(config_file)
            except:
                log.warning('no configuration found for c%d-%d' % chip_info)
                controller.disable(chip_id=chip_id, io_chain=io_chain)
                continue
        controller.write_configuration(chip)
        controller.disable(chip_id=chip_id, io_chain=io_chain)
    log.info('initial configuration of chips complete')

    verify_chip_configuration(controller)

    # Run sensitivity test on each chip
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
            chip_results = noise_tests.test_min_signal_amplitude(\
                controller=controller,chip_idx=chip_idx,
                threshold=chip.config.global_threshold + global_threshold_correction,
                trim=[trim + pixel_trim_correction
                      for trim in chip.config.pixel_trim_thresholds],
                n_pulses=n_pulses,
                min_dac_amp=min_dac_amp,
                max_dac_amp=max_dac_amp,
                reset_cycles=chip.config.reset_cycles)
                                                                     
            board_results += [chip_results]
            finish_time = time.time()
            if verbose:
                log.debug('c%d-%d sensitivity test took %.2f s' % \
                              (chip_id, io_chain, finish_time - start_time))
        except Exception as error:
            log.exception(error)
            log.error('c%d-%d sensitivity test failed!' % chip_info)
            controller.disable(chip_id=chip_id, io_chain=io_chain)
            return_code = 2
            continue

    log.info('all chips sensitivity check complete')

    # Print sensitivity test results
    for chip_idx,chip in enumerate(controller.chips):
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        if board_results[chip_idx] is None:
            log.info('%s-c%d-%d skipped' % (board_info, chip_id, io_chain))
            continue
        for channel in sorted(board_results[chip_idx].keys()):
            log.info('%s-c%d-%d-ch%d min dac: %d dac, efficiency: %.2f' % \
                         (board_info, chip_id, io_chain, channel,
                          board_results[chip_idx][channel]['min_pulse_dac'],
                          board_results[chip_idx][channel]['eff']))

except Exception as error:
    log.exception(error)
    return_code = 1

exit(return_code)
