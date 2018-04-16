'''
This script generates a series of chip configuration .json files for a larpix board.
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
from sys import (exit, stdout)
import json
import os

start_time = time.localtime()
default_config = 'physics.json'

parser = argparse.ArgumentParser()
parser.add_argument('--board', default=pathnames.default_board_file(start_time),
                    help='input file containing chipset info (optional, '
                    'default: %(default)s)')
parser.add_argument('-o','--outdir', default=pathnames.default_script_logdir(start_time),
                    help='output directory for log, config, and data files '
                    '(optional, default: %(default)s)')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('--global_threshold_max', default=40, type=int,
                    help='maximum global threshold for coarse scan '
                    '(optional, default: %(default)s)')
parser.add_argument('--global_threshold_min', default=0, type=int,
                    help='minimum global threshold for coarse scan '
                    '(optional, default: %(default)s)')
parser.add_argument('--global_threshold_step', default=1, type=int,
                    help='global threshold step size for coarse scan '
                    '(optional, default: %(default)s)')
parser.add_argument('--pixel_trim_max', default=31, type=int,
                    help='maximum pixel trim for fine scan '
                    '(optional, default: %(default)s)')
parser.add_argument('--pixel_trim_min', default=0, type=int,
                    help='minimum pixel trim for fine scan '
                    '(optional, default: %(default)s)')
parser.add_argument('--pixel_trim_step', default=1, type=int,
                    help='pixel trim step size for fine scan '
                    '(optional, default: %(default)s)')
parser.add_argument('--configuration_file', default=None,
                    help='initial chip configuration file to load '
                    'by default will look in %s for individual chip configurations, '
                    'if chip config not found, will load %s, '
                    'if this file does not exist, will load %s and generate new default '
                    '(optional)' % (pathnames.default_config_dir(start_time),
                                    pathnames.default_config_file(start_time),
                                    default_config))
parser.add_argument('--threshold_rate', default=5, type=float,
                    help='target per channel trigger rate - configuration guarantees '
                    '< threshold_rate Hz/channel of triggers '
                    '(optional, units: Hz, default: %(default)s)')
parser.add_argument('--max_rate', default=20, type=float,
                    help='maximum per channel trigger rate - configuration will disable '
                    'channels with >= max_rate Hz of triggers at start and end of scan '
                    '(optional, units: Hz, default: %(default)s)')
parser.add_argument('--run_time', default=1, type=float,
                    help='read time for calculating trigger rate - recommended that run_time '
                    '> 1/threshold_rate '
                    '(optional, units: sec, default: %(default)s)')
parser.add_argument('--quick_run_time', default=0.1, type=float,
                    help='read time for calculating trigger rate on initial quick threshold '
                    'scan - recommended ~run_time/10 '
                    '(optional, units: sec, default: %(default)s)')
parser.add_argument('--chips', default=None, type=int, nargs='+',
                    help='chips to include in scan '
                    '(optional, default: all chips in chipset file)')
args = parser.parse_args()

infile = args.board
outdir = args.outdir
verbose = args.verbose
global_threshold_max = args.global_threshold_max
global_threshold_min = args.global_threshold_min
global_threshold_step = args.global_threshold_step
pixel_trim_max = args.pixel_trim_max
pixel_trim_min = args.pixel_trim_min
pixel_trim_step = args.pixel_trim_step
config_file = args.configuration_file
if config_file is None:
    config_file = pathnames.default_config_dir(start_time)
    default_config = pathnames.make_default_config(start_time, default_config)
threshold_rate = args.threshold_rate
max_rate = args.max_rate
run_time = args.run_time
quick_run_time = args.quick_run_time
chips_to_scan = args.chips

return_code = 0

script_logfile = outdir + '/' + \
    os.path.basename(pathnames.default_script_logfile(start_time))
data_logfile = outdir + '/' + os.path.basename(pathnames.default_data_logfile(start_time))
sl = ScriptLogger(start_time, script_logfile=script_logfile, data_logfile=data_logfile)
log = sl.script_log

try:
    controller = larpix.Controller(timeout=0.01)
    chip0 = controller.all_chips[0]
    # Initial configuration of chips
    board_info = larpix_scripting.load_board(controller, infile)
    log.info('begin initial configuration of chips for board %s' % board_info)
    config_ok, different_registers = larpix_scripting.load_chip_configurations(
        controller, board_info, config_file, silence=True, default_config=default_config)
    if config_ok:
        log.info('initial configuration of chips successful')

    chip_configurations = []
    for chip in controller.chips:
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
                    continue
            global_threshold = global_threshold_max
            chip.config.global_threshold = global_threshold
            pixel_trims = [pixel_trim_max]*32
            chip.config.pixel_trim_thresholds = pixel_trims
            modified_registers = range(32) + [32]
            controller.write_configuration(chip, modified_registers)
            # Check for high rate channels
            controller.enable(chip_id=chip_id, io_chain=io_chain)
            high_threshold_channels = set()
            break_flag = False
            while not break_flag:
                break_flag = True
                clear_buffer(controller)
                log.info('check rate on %d-c%d' % chip_info)
                controller.write_configuration(chip0, range(10), write_read=run_time,
                                               message='rate check %d-c%d' % chip_info)
                npackets = npackets_by_channel(controller.reads[-1], chip_id)
                log.info('%d-c%d has a rate of %.2f Hz' % \
                             (io_chain, chip_id, sum(npackets)/run_time))
                for channel,npacket in enumerate(npackets):
                    if npacket >= max_rate * run_time:
                        if verbose:
                            log.info('%d-c%d-ch%d has a rate of %.2f Hz' % \
                                         (io_chain, chip_id, channel, npacket/run_time))
                        high_threshold_channels.add(channel)
                        break_flag = False
                log.info('disable %d-c%d channels %s' % (io_chain, chip_id,
                                                         str(high_threshold_channels)))
                controller.disable(chip_id=chip_id,
                                   channel_list=list(high_threshold_channels),
                                   io_chain=io_chain)
                clear_buffer(controller)
            if len(high_threshold_channels):
                log.info('%d-c%d channels with threshold above %d: %s' % \
                             (io_chain, chip_id, global_threshold,
                              str(high_threshold_channels)))
            # Perform quick global threshold scan to determine highest channel threshold
            log.info('begin quick global threshold scan for %d-c%d' % chip_info)
            break_flag = False
            while global_threshold >= global_threshold_min and not break_flag:
                clear_buffer(controller)
                chip.config.global_threshold = global_threshold
                modified_registers = 32
                controller.write_configuration(chip, modified_registers)
                clear_buffer_quick(controller)
                controller.write_configuration(chip0, range(10), write_read=quick_run_time,
                                               message='quick global threshold scan')
                packets = controller.reads[-1]
                npackets = npackets_by_channel(packets, chip_id)
                log.info('threshold %d - chip rate %.2f Hz' % \
                             (global_threshold, sum(npackets)/quick_run_time))
                for channel in range(32):
                    if npackets[channel] >= threshold_rate * quick_run_time:
                        if verbose:
                            log.info('%d-c%d-ch%d rate is %.2f Hz' % \
                                         (io_chain, chip_id, channel,
                                          npackets[channel]/quick_run_time))
                        break_flag = True
                if not break_flag:
                    global_threshold -= global_threshold_step
            if global_threshold < global_threshold_min: global_threshold = global_threshold_min
            log.info('quick global threshold scan for %d-c%d complete: %d' % \
                         (io_chain, chip_id, global_threshold))
            # Perform slow global threshold scan to closely determine global threshold
            log.info('begin fine global threshold scan for %d-c%d' % chip_info)
            break_flag = False
            while global_threshold <= global_threshold_max and not break_flag:
                break_flag = True
                clear_buffer(controller)
                chip.config.global_threshold = global_threshold
                modified_registers = 32
                controller.write_configuration(chip, modified_registers)
                clear_buffer_quick(controller)
                controller.write_configuration(chip0, range(10), write_read=run_time,
                                               message='global threshold scan')
                packets = controller.reads[-1]
                npackets = npackets_by_channel(packets, chip_id)
                log.info('threshold %d - chip rate %.2f Hz' % \
                             (global_threshold, sum(npackets)/run_time))
                for channel in range(32):
                    if npackets[channel] > threshold_rate * run_time:
                        if verbose:
                            log.info('%d-c%d-ch%d rate is %.2f Hz' % \
                                         (io_chain, chip_id, channel, npackets[channel]/run_time))
                        break_flag = False
                if not break_flag:
                    global_threshold += global_threshold_step
            log.info('fine global threshold scan for %d-c%d complete: %d' % \
                         (io_chain, chip_id, global_threshold))
            # Run quick pixel trim scan
            log.info('begin quick pixel trim scan for %d-c%d' % chip_info)
            pixel_trim = pixel_trim_max
            disabled_channels = [] # channels that are disabled during quick pixel trim scan
            channel_at_threshold = [channel in high_threshold_channels for channel in range(32)]
            while pixel_trim >= pixel_trim_min:
                clear_buffer(controller)
                chip.config.pixel_trim_thresholds = pixel_trims
                modified_registers = range(32)
                controller.write_configuration(chip, modified_registers)
                clear_buffer_quick(controller)
                controller.write_configuration(chip0, range(10), write_read=quick_run_time,
                                               message='quick pixel trim scan')
                packets = controller.reads[-1]
                npackets = npackets_by_channel(packets, chip_id)
                log.info('trim %d - chip rate %.2f Hz' % \
                             (pixel_trim, sum(npackets)/quick_run_time))
                for channel in range(32):
                    if npackets[channel] < threshold_rate * quick_run_time and \
                            not channel_at_threshold[channel]:
                        if pixel_trims[channel] <= pixel_trim_min:
                            pixel_trims[channel] = pixel_trim_min
                        else:
                            pixel_trims[channel] -= pixel_trim_step
                    elif npackets[channel] >= threshold_rate * quick_run_time:
                        channel_at_threshold[channel] = True
                        disabled_channels += [channel]
                        if verbose:
                            log.info('%d-c%d-ch%d rate is %.2f Hz' % \
                                         (io_chain, chip_id, channel,
                                          npackets[channel]/quick_run_time))
                controller.disable(chip_id=chip_id, channel_list=disabled_channels,
                                   io_chain=io_chain)
                # disable channels to reduce data rate
                if all(channel_at_threshold):
                    break
                pixel_trim -= pixel_trim_step
            if pixel_trim < pixel_trim_min: pixel_trim = pixel_trim_min
            log.info('quick pixel trim scan for %d-c%d complete: %s' % \
                         (io_chain, chip_id, str(pixel_trims)))
            controller.enable(chip_id=chip_id, channel_list=disabled_channels)
            # re-enable channels
            # Perform slow pixel scan to closely determine pixel trims
            log.info('begin fine pixel trim scan for %d-c%d' % chip_info)
            while pixel_trim <= pixel_trim_max:
                break_flag = True
                clear_buffer(controller)
                chip.config.pixel_trim_thresholds = pixel_trims
                modified_registers = range(32)
                controller.write_configuration(chip, modified_registers)
                clear_buffer_quick(controller)
                controller.write_configuration(chip0, range(10), write_read=run_time,
                                               message='pixel trim scan')
                packets = controller.reads[-1]
                npackets = npackets_by_channel(packets, chip_id)
                log.info('trim %d - chip rate %.2f Hz' % \
                             (pixel_trim, sum(npackets)/run_time))
                for channel in range(32):
                    if npackets[channel] > threshold_rate * run_time:
                        if verbose:
                            log.info('%d-c%d-ch%d rate is %.2f Hz' % \
                                         (io_chain, chip_id, channel, npackets[channel]/run_time))
                        if pixel_trims[channel] >= pixel_trim_max:
                            pixel_trims[channel] = pixel_trim_max
                        else:
                            pixel_trims[channel] += pixel_trim_step
                if all([n <= threshold_rate * run_time for n in npackets]):
                    break
                pixel_trim += pixel_trim_step
            log.info('fine pixel trim scan for %d-c%d complete: %s' % \
                         (io_chain, chip_id, pixel_trims))
            # Check one last time for high rate channels
            log.info('checking rate with configuration')
            clear_buffer(controller)
            controller.write_configuration(chip0, range(10), write_read=run_time,
                                           message='rate check')
            npackets = npackets_by_channel(controller.reads[-1], chip_id)
            log.info('%d-c%d rate is %.2f Hz' % \
                             (io_chain, chip_id, sum(npackets)/run_time))
            high_rate_channels = []
            for channel in range(32):
                if verbose:
                    log.info('%d-c%d-ch%d rate is %.2f Hz' % \
                                 (io_chain, chip_id, channel, npackets[channel]/run_time))
                if npackets[channel] > max_rate * run_time:
                    high_rate_channels += [channel]
            if len(high_rate_channels) > 0:
                log.warn('rates too high on channel %s, disabling' % \
                            (high_rate_channels))
            controller.disable(chip_id=chip_id, channel_list=high_rate_channels,
                               io_chain=io_chain)
            # Save chip configuration
            config = larpix.Configuration()
            config.from_dict(chip.config.to_dict())
            if verbose:
                log.debug(str(config))
                num_31s = 0
                num_0s = 0
                for thresh in config.pixel_trim_thresholds:
                    if thresh == 0:
                        num_0s += 1
                    elif thresh == 31:
                        num_31s += 1
                log.debug('num 0s: %d, num 31s: %d, FoM: %.2f', num_0s,
                        num_31s, num_31s + 0.5*num_0s)
            chip_configurations += [config]
            configuration_file = outdir + '/%s-%d-c%d_config.json' % \
                (board_info, io_chain, chip_id)
            config.write(configuration_file, force=True)
            log.info('configuration saved to %s' % configuration_file)
            # Disable chip for rest of loop
            controller.disable(chip_id=chip_id, io_chain=io_chain)
            log.info('%d-c%d configuration complete' % chip_info)
            finish_time = time.time()
            if verbose:
                log.debug('%d-c%d configuration took %.2f s' % \
                              (io_chain, chip_id, finish_time - start_time))
        except Exception as error:
            log.exception(error)
            log.error('%d-c%d configuration failed!' % chip_info)
            controller.disable(chip_id=chip_id, io_chain=io_chain)
            return_code = 2
            continue

    log.info('all chips configuration complete')

    # Load configuration onto chips and check final rate
    log.info('board rate check')
    larpix_scripting.load_chip_configurations(controller, board_info, outdir)
    clear_buffer(controller)
    controller.run(run_time,'check rate')
    packets = controller.reads[-1]
    log.info('%s rate: %.2f Hz' % (board_info, len(packets)/run_time))
    npackets = npackets_by_chip_channel(controller.reads[-1])
    for chip in controller.chips:
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        if chip_id in npackets.keys():
            log.info('%s-%d-c%d rate: %.2f Hz' % \
                         (board_info, io_chain, chip_id, sum(npackets[chip_id])/run_time))
            for channel in range(32):
                log.info('%s-%d-c%d-ch%d rate: %.2f Hz' % \
                             (board_info, io_chain, chip_id, channel,
                              npackets[chip_id][channel]/run_time))
        else:
            log.warn('%s-%d-c%d no packets received' % \
                         (board_info, io_chain, chip_id))
except Exception as error:
    log.exception(error)
    return_code = 1

exit(return_code)
