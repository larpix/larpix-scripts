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
from helpers.script_logging import ScriptLogger
import helpers.pathnames as pathnames
import helpers.larpix_scripting as larpix_scripting
import time
import larpix.larpix as larpix
import helpers.noise_tests as noise_tests
from sys import (exit, stdout)
import json
import os

start_time = time.localtime()
default_config = 'physics.json'

parser = argparse.ArgumentParser()
parser.add_argument('--board', default=pathnames.default_board_file(start_time),
                    help='input file containing chipset info (optional, default: '
                    '%(default)s)')
parser.add_argument('-o','--outdir', default=pathnames.default_script_logdir(start_time),
                    help='output directory for log file '
                    '(optional, default: %(default)s)')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('--global_threshold_correction', default=0, type=int,
                    help='Amount to increase the global threshold on each chip'
                    ' for sensitivity test'
                    '(optional, default: %(default)s)')
parser.add_argument('--pixel_trim_correction', default=0, type=int,
                    help='Amount to increase the pixel trim on each channel'
                    ' for sensitivity test '
                    '(optional, default: %(default)s)')
parser.add_argument('--max_dac_amp', default=10, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--min_dac_amp', default=0, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--n_pulses', default=10, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--configuration_file', default=None,
                    help='initial chip configuration file to load '
                    'by default will look in %s for individual chip configurations, '
                    'if chip config not found, will load %s, '
                    'if this file does not exist, will load %s and generate new default '
                    '(optional)' % (pathnames.default_config_dir(start_time),
                                    pathnames.default_config_file(start_time),
                                    default_config))
parser.add_argument('--chips', default=None, type=str,
                    help='chips to include in scan, string of chip_ids separated by commas '
                    '(optional, default: None=all chips in chipset file)')
args = parser.parse_args()

infile = args.board
outdir = args.outdir
verbose = args.verbose
global_threshold_correction = args.global_threshold_correction
pixel_trim_correction = args.pixel_trim_correction
max_dac_amp = args.max_dac_amp
min_dac_amp = args.min_dac_amp
n_pulses = args.n_pulses
config_file = args.configuration_file
if config_file is None:
    config_file = pathnames.default_config_dir(start_time)
    default_config = pathnames.make_default_config_file(start_time, default_config)
if not args.chips is None:
    chips_to_scan = [int(chip_id) for chip_id in args.chips.split(',')]
else:
    chips_to_scan = None

return_code = 0

sl = ScriptLogger(start_time)
log = sl.get_script_log()

try:
    controller = larpix.Controller(timeout=0.01)
    # Initial configuration of chips
    board_info = larpix_scripting.load_board(controller, infile)
    log.info('begin initial configuration of chips for board %s' % board_info)
    config_ok, different_registers = larpix_scripting.load_chip_configurations(
        controller, board_info, config_file, silence=True, default_config=default_config)
    if config_ok:
        log.info('initial configuration of chips complete')

    # Run sensitivity test on each chip
    board_results = []
    for chip_idx,chip in enumerate(controller.chips):
        try:
            start_time = time.time()
            chip_id = chip.chip_id
            io_chain = chip.io_chain
            chip_info = (io_chain, chip_id)
            if chips_to_scan is None:
                pass
            else:
                if not chip_id in chips_to_scan:
                    log.info('skipping %d-c%d' % chip_info)
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
                log.debug('%d-c%d sensitivity test took %.2f s' % \
                              (io_chain, chip_id, finish_time - start_time))
        except Exception as error:
            log.exception(error)
            log.error('%d-c%d sensitivity test failed!' % chip_info)
            controller.disable(chip_id=chip_id, io_chain=io_chain)
            return_code = 2
            continue

    log.info('all chips sensitivity check complete')

    # Print sensitivity test results
    for chip_idx,chip in enumerate(controller.chips):
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        if board_results[chip_idx] is None:
            log.info('%s-%d-c%d skipped' % (board_info, io_chain, chip_id))
            continue
        for channel in sorted(board_results[chip_idx].keys()):
            log.info('%s-%d-c%d-ch%d min dac: %d dac, efficiency: %.2f' % \
                         (board_info, io_chain, chip_id, channel,
                          board_results[chip_idx][channel]['min_pulse_dac'],
                          board_results[chip_idx][channel]['eff']))

except Exception as error:
    log.exception(error)
    return_code = 1

exit(return_code)
