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
import time
import larpix.larpix as larpix
from sys import (exit, stdout)
import json
import os

def npackets_by_channel(packets, chip_id):
    npackets = [0]*32
    for packet in packets:
        if packet.chipid == chip_id:
            npackets[packet.channel_id] += 1
    return npackets

def npackets_by_chip_channel(packets):
    npackets = [[0]*32]*256
    for packet in packets:
        npackets[packet.chipid][packet.channel_id] += 1
    return npackets

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
                    help='output directory for log and config files '
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
parser.add_argument('--configuration_file', default='physics.json',
                    help='initial chip configuration file to load '
                    '(optional, default: %(default)s)')
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
parser.add_argument('--chips', default=None, type=str,
                    help='chips to include in scan, string of chip_ids separated by commas'
                    '(optional, default: None=all chips in chipset file)')
args = parser.parse_args()

infile = args.infile
outdir = args.outdir
verbose = args.verbose
global_threshold_max = args.global_threshold_max
global_threshold_min = args.global_threshold_min
global_threshold_step = args.global_threshold_step
pixel_trim_max = args.pixel_trim_max
pixel_trim_min = args.pixel_trim_min
pixel_trim_step = args.pixel_trim_step
config_file = args.configuration_file
threshold_rate = args.threshold_rate
max_rate = args.max_rate
run_time = args.run_time
quick_run_time = args.quick_run_time
if not args.chips is None:
    chips_to_scan = [int(chip_id) for chip_id in args.chips.split(',')]
else:
    chips_to_scan = None

return_code = 0

if not os.path.exists(outdir):
    os.makedirs(outdir)
logfile = outdir + '/.configure_chips_%s.log' % \
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
    chip0 = controller.all_chips[0]
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
    controller.disable()
    clear_buffer(controller)

    verify_chip_configuration(controller)

    chip_configurations = []
    try:
        start_time = time.time()
        global_threshold = {}
        pixel_trims = {}
        modified_registers = range(32) + [32]
        for chip in controller.chips:
            chip_id = chip.chip_id
            global_threshold[chip_id] = global_threshold_max
            pixel_trims[chip_id] = [pixel_trim_max]*32
            chip.config.global_threshold = global_threshold[chip_id]
            chip.config.pixel_trim_thresholds = pixel_trims[chip_id]
            controller.write_configuration(chip, modified_registers)
        # Check for high rate channels
        high_threshold_channels = {}
        for chip in controller.chips:
            chip_id = chip.chip_id
            high_threshold_channels[chip_id] = set()
            if chips_to_scan is None:
                controller.enable()
            elif chip_id in chips_to_scan:
                controller.enable(chip_id=chip_id)

        break_flag = False
        while not break_flag:
            break_flag = True
            clear_buffer(controller)
            log.info('check rate on chips')
            controller.write_configuration(chip0, range(10), write_read=run_time,
                                           message='rate check')
            npackets = npackets_by_chip_channel(controller.reads[-1])
            for chip in chips:
                chip_id = chip.chip_id
                if sum(npackets[chip_id]) <= 0:
                    continue
                log.info('c%d-%d has a rate of %.2f Hz' % \
                             (chip_id, io_chain, sum(npackets[chip_id])/run_time))
                for channel,npacket in enumerate(npackets[chip_id]):
                    if npacket >= max_rate * run_time:
                        if verbose:
                            log.info('c%d-%d-ch%d has a rate of %.2f Hz' % \
                                         (chip_id, io_chain, channel, npacket/run_time))
                        high_threshold_channels[chip_id].add(channel)
                        break_flag = False
                log.info('disable c%d-%d channels %s' % \
                             (chip_id, io_chain, str(high_threshold_channels[chip_id])))
                controller.disable(chip_id=chip_id,
                                   channel_list=list(high_threshold_channels[chip_id]),
                                   io_chain=io_chain)
        for chip in controller.chips:
            chip_id = chip.chip_id
            if len(high_threshold_channels[chip_id]):
                log.info('c%d-%d channels with threshold above %d: %s' % \
                             (chip_id, io_chain, global_threshold,
                              str(high_threshold_channels[chip_id])))

        # Perform quick global threshold scan to determine highest channel threshold
        log.info('begin quick global threshold scan' % chip_info)
        repeat_flag = False
        break_flag = False
        scan_complete = {}
        for chip in controller.chips: scan_complete[chip.chip_id] = False
        test_threshold = global_threshold_max
        while test_threshold >= global_threshold_min and not break_flag:
            clear_buffer(controller)
            modified_registers = [32]
            for chip in controller.chips:
                chip_id = chip.chip_id
                if not scan_complete[chip_id]:
                    global_threshold[chip_id] = test_threshold
                    chip.config.global_threshold = global_threshold[chip_id]
                    modified_registers = 32
                    controller.write_configuration(chip, modified_registers)
                    clear_buffer_quick(controller)
            controller.write_configuration(chip0, range(10), write_read=quick_run_time,
                                           message='quick global threshold scan')
            packets = controller.reads[-1]
            npackets = npackets_by_chip_channel(packets)
            for chip in controller.chips:
                chip_id = chip.chip_id
                if sum(npackets[chip_id]) <= 0:
                    continue
                log.info('threshold %d - chip rate %.2f Hz' % \
                             (global_threshold, sum(npackets[chip_id])/quick_run_time))
                for channel in range(32):
                    if npackets[chip_id][channel] >= threshold_rate * quick_run_time:
                        if verbose:
                            log.info('c%d-ch%d rate is %.2f Hz' % \
                                         (chip_id, channel,
                                          npackets[chip_id][channel]/quick_run_time))
                        scan_complete[chip_id] = True
                        repeat_flag = True
                        controller.disable(chip_id=chip_d)
            break_flag = all(scan_complete.values())
            if not break_flag:
                if not repeat_flag:
                    test_threshold -= global_threshold_step
                if test_threshold < global_threshold_min:
                    test_threshold = global_threshold_min
        log.info('quick global threshold scan for complete')
        if verbose:
            for chip in controller.chips:
                chip_id = chip.chip_id
                log.info('c%d threshold: %d' % (chip_id, chip.config.global_threshold))
        log.info('reenabling chips at new thresholds')
        for chip in reversed(controller.chips):
            chip_id = chip.chip_id
            io_chain = chip.io_chain
            controller.enable(chip_id=chip_id, io_chain=io_chain)
            controller.disable(chip_id=chip_id,
                               channel_list=list(high_threshold_channels[chip_id]),
                               io_chain=io_chain)

        # Perform slow global threshold scan to closely determine global threshold
        log.info('begin fine global threshold scan')
        break_flag = False
        while not break_flag:
            break_flag = True
            clear_buffer(controller)
            modified_registers = 32
            for chip in controller.chips:
                chip_id = chip.chip_id
                chip.config.global_threshold = global_threshold[chip_id]
                controller.write_configuration(chip, modified_registers)
                clear_buffer_quick(controller)
            controller.write_configuration(chip0, range(10), write_read=run_time,
                                           message='global threshold scan')
            packets = controller.reads[-1]
            npackets = npackets_by_chip_channel(packets)
            for chip in controller.chips:
                chip_id = chip.chip_id
                if any([npacket > threshold_rate * run_time
                        for npacket in npackets[chip_id]]):
                    global_threshold[chip_id] += global_threshold_step
                    log.info('threshold %d - chip rate %.2f Hz' % \
                                 (global_threshold[chip_id], sum(npackets[chip_id])/run_time))
                    if verbose:
                        for channel in range(32):
                            log.info('c%d-ch%d rate is %.2f Hz' % \
                                         (chip_id, channel,
                                          npackets[chip_id][channel]/run_time))
                    break_flag = False
        log.info('fine global threshold scan complete')
        if verbose:
            for chip in controller.chips:
                chip_id = chip.chip_id
                log.info('c%d threshold: %d' % (chip_id, chip.config.global_threshold))

        # Run quick pixel trim scan
        log.info('begin quick pixel trim scan')
        break_flag = False
        repeat_flag = False
        test_trim = pixel_trim_max
        disabled_channels = {}
        scan_complete = {}
        for chip in controller.chips:
            chip_id = chip.chip_id
            disabled_channels[chip_id] = set()
            # channels that are disabled during quick pixel trim scan
            scan_complete[chip_id] = [False]*32
            for channel in range(32):
                if channel in high_threshold_channels[chip_id]:
                    scan_complete[chip_id][channel] = True

        while test_trim >= pixel_trim_min and not break_flag:
            repeat_flag = False
            clear_buffer(controller)
            modified_registers = range(32)
            for chip in controller.chips:
                chip_id = chip.chip_id
                chip.config.pixel_trim_thresholds = pixel_trims[chip_id]
                controller.write_configuration(chip, modified_registers)
                clear_buffer_quick(controller)
            controller.write_configuration(chip0, range(10), write_read=quick_run_time,
                                           message='quick pixel trim scan')
            packets = controller.reads[-1]
            npackets = npackets_by_chip_channel(packets)
            for chip in controller.chips:
                chip_id = chip.chip_id
                for channel in range(32):
                    if npackets[chip_id][channel] < threshold_rate * quick_run_time and \
                            not scan_complete[chip_id][channel]:
                        pixel_trims[chip_id][channel] = test_trim
                    elif npackets[chip_id][channel] >= threshold_rate * quick_run_time:
                        scan_complete[chip_id][channel] = True
                        disabled_channels[chip_id].add(channel)
                        repeat_flag = True
                        if verbose:
                            log.info('c%d-ch%d rate is %.2f Hz' % \
                                         (chip_id, channel,
                                          npackets[chip_id][channel]/quick_run_time))
                        controller.disable(chip_id=chip_id,
                                           channel_list=list(disabled_channels[chip_id]))
            if all([complete for chip_complete in scan_complete
                    for complete in chip_complete]):
                break_flag = True
            if not repeat_flag:
                test_trim -= pixel_trim_step
        log.info('quick pixel trim scan complete')
        for chip in controller.chips:
            chip_id = chip.chip_id
            if verbose:
                log.info('c%d trims: %s' % (chip_id,
                                            str(chip.config.pixel_trim_thresholds)))
            controller.enable(chip_id=chip_id,
                              channel_list=list(disabled_channels[chip_id]))

        # Perform slow pixel scan to closely determine pixel trims
        log.info('begin fine pixel trim scan')
        while True:
            clear_buffer(controller)
            modified_registers = range(32)
            for chip in controller.chips:
                chip_id = chip.chip_id
                chip.config.pixel_trim_thresholds = pixel_trims[chip_id]
                controller.write_configuration(chip, modified_registers)
                clear_buffer_quick(controller)
            controller.write_configuration(chip0, range(10), write_read=run_time,
                                           message='pixel trim scan')
            packets = controller.reads[-1]
            npackets = npackets_by_chip_channel(packets)
            for chip in controller.chips:
                if any([npacket > threshold_rate * run_time
                        for npacket in npackets[chip_id]]):
                    for channel, npacket in enumerate(npackets[chip_id]):
                        if npacket > threshold_rate * run_time:
                            if verbose:
                                log.info('c%d-ch%d rate is %.2f Hz' % \
                                             (chip_id, channel,
                                              npacket/run_time))
                            if pixel_trims[channel] >= pixel_trim_max:
                                log.warn('c%d-ch%d trim at max, disabling' % \
                                             (chip_id, channel))
                                controller.disable(chip_id=chip_id, channel_list=[channel])
                            else:
                                pixel_trims[channel] += pixel_trim_step
                                if pixel_trims[channel] > pixel_trim_max:
                                    pixel_trims[channel] = pixel_trim_max
            if all([npacket <= threshold_rate * run_time
                    for chip_npackets in npackets[chip_id] for npacket in chip_npackets]):
                break
        log.info('fine trim scan complete')
        if verbose:
            for chip in controller.chips:
                chip_id = chip.chip_id
                log.info('c%d trims: %s' % (chip_id,
                                            str(chip.config.pixel_trim_thresholds)))

        # Check one last time for high rate channels
        high_rate_channels = {}
        for chip in controller.chips: high_rate_channels[chip.chip_id] = set()
        while True:
            log.info('checking rate with configuration')
            clear_buffer(controller)
            controller.write_configuration(chip0, range(10), write_read=run_time,
                                           message='rate check')
            npackets = npackets_by_chip_channel(controller.reads[-1])
            for chip in controller.chips:
                chip_id = chip.chip_id
                log.info('c%d-%d rate is %.2f Hz' % \
                             (chip_id, sum(npackets[chip_id])/run_time))
                if any([npacket > max_rate * run_time for npacket in npackets[chip_id]]):
                    for channel in range(32):
                        if npackets[chip_id][channel] > max_rate * run_time:
                            high_rate_channels[chip_id].add(channel)
                    if len(high_rate_channels[chip_id]) > 0:
                        log.warn('rates too high on c%d channels %s, disabling' % \
                                     (chip_id, str(high_rate_channels)))
                        controller.disable(chip_id=chip_id, channel_list=list(high_rate_channels))
            if all([npacket <= max_rate * run_time for chip_npackets in npackets
                    for npacket in chip_npackets]):
                break

        # Save chip configuration
        for chip in controller.chips:
            chip_id = chip.chip_id
            io_chain = chip.io_chain
            config = larpix.Configuration()
            config.from_dict(chip.config.to_dict())
            if verbose:
                log.debug('configuration for c%d' % chip_id)
                log.debug(str(config))
            chip_configurations += [config]
            configuration_file = outdir + '/%s-%d-c%d_config.json' % \
                (board_info, io_chain, chip_id)
            config.write(configuration_file, force=True)
            log.info('configuration saved to %s' % configuration_file)
        finish_time = time.time()
        if verbose:
            log.debug('configuration took %.2f s' % \
                              (chip_id, io_chain, finish_time - start_time))
    except Exception as error:
        log.exception(error)
        log.error('configuration failed!' % chip_info)
        controller.disable(chip_id=chip_id, io_chain=io_chain)
        return_code = 2
        continue

    log.info('all chips configuration complete')

    # Load configuration onto chips and check final rate
    log.info('board rate check')
    for chip in controller.chips:
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        configuration_file = outdir + '/%s-%d-c%d_config.json' % \
            (board_info, io_chain, chip_id)
        if not os.path.isfile(configuration_file):
            continue
        chip.config.load(configuration_file)
        controller.write_configuration(chip)
    clear_buffer(controller)
    controller.run(run_time,'check rate')
    packets = controller.reads[-1]
    log.info('%s rate: %.2f Hz' % (board_info, len(packets)/run_time))
    npackets = npackets_by_chip_channel(controller.reads[-1])
    for chip in controller.chips:
        chip_id = chip.chip_id
        if chip_id in npackets.keys():
            log.info('%s-c%d rate: %.2f Hz' % \
                         (board_info, chip_id, sum(npackets[chip_id])/run_time))
            for channel in range(32):
                log.info('%s-c%d-ch%d rate: %.2f Hz' % \
                             (board_info, chip_id, channel,
                              npackets[chip_id][channel]/run_time))
        else:
            log.warn('%s-c%d no packets received' % \
                         (board_info, chip_id))
except Exception as error:
    log.exception(error)
    return_code = 1

exit(return_code)
