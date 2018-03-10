'''
This script generates a series of chip configuration .json files for a larpix board.
Requires a .json file containing chip-ids and daisy chain data formatted like
{
    'board': <board-name>,
    'chip_set': [
        (<chip-id>, <io-chain>),
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
    npackets = {}
    for packet in packets:
        try:
            npackets[packet.chipid][packet.channel_id] += 1
        except KeyError:
            npackets[packet.chipid] = [0]*32
            npackets[packet.chipid][packet.channel_id] += 1
    return npackets

def clear_buffer(controller):
    controller.run(0.1,'clear buffer (quick)')
    if len(controller.reads[-1]) > 0:
        controller.run(2,'clear buffer (slow)')

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

if not os.path.exists(outdir):
    os.makedirs(outdir)
logfile =  outdir + '/configure_chips_%s.log' % \
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

try:
    controller = larpix.Controller()
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

    clear_buffer(controller)

    config_ok, different_registers = controller.verify_configuration()
    if not config_ok:
        log.warn('chip configurations were not verified')
        log.warn('different registers: %s' % str(different_registers))

    chip_configurations = []
    for chip in controller.chips:
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        chip_info = (chip_id, io_chain)
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
            log.info('check rate on c%d-%d' % chip_info)
            controller.run(run_time,'rate check c%d-%d' % chip_info)
            npackets = npackets_by_channel(controller.reads[-1], chip_id)
            for channel,npacket in enumerate(npackets):
                if npacket >= max_rate * run_time:
                    log.info('c%d-%d-ch%d has a rate of %.2f Hz' % \
                                 (chip_id, io_chain, channel, npacket/run_time))
                    high_threshold_channels.add(channel)
                    break_flag = False
            log.info('disable c%d-%d channels %s' % (chip_id, io_chain,
                                                     str(high_threshold_channels)))
            controller.disable(chip_id=chip_id, channel_list=list(high_threshold_channels),
                               io_chain=io_chain)
            clear_buffer(controller)
        if len(high_threshold_channels):
            log.info('c%d-%d channels with threshold above %d: %s' % \
                         (chip_id, io_chain, global_threshold, str(high_threshold_channels)))
        # Perform quick global threshold scan to determine highest channel threshold
        log.info('begin quick global threshold scan for c%d-%d' % chip_info)
        while global_threshold >= global_threshold_min:
            clear_buffer(controller)
            chip.config.global_threshold = global_threshold
            modified_registers = 32
            controller.write_configuration(chip, modified_registers)
            controller.run(quick_run_time,'quick global threshold scan')
            packets = controller.reads[-1]
            log.info('threshold %d - chip rate %.2f Hz' % \
                         (global_threshold, len(packets)/quick_run_time))
            npackets = npackets_by_channel(packets, chip_id)
            for channel in range(32):
                if npackets[channel] >= threshold_rate * quick_run_time:
                    log.info('c%d-%d-ch%d rate is %.2f Hz' % \
                                 (chip_id, io_chain, channel,
                                  npackets[channel]/quick_run_time))
                    break
            global_threshold -= global_threshold_step
        log.info('quick global threshold scan for c%d-%d complete: %d' % \
                     (chip_id, io_chain, global_threshold))
        # Perform slow global threshold scan to closely determine global threshold
        log.info('begin fine global threshold scan for c%d-%d' % chip_info)
        break_flag = False
        while global_threshold <= global_threshold_max and not break_flag:
            break_flag = True
            clear_buffer(controller)
            chip.config.global_threshold = global_threshold
            modified_registers = 32
            controller.write_configuration(chip, modified_registers)
            controller.run(run_time,'global threshold scan')
            packets = controller.reads[-1]
            log.info('threshold %d - chip rate %.2f Hz' % \
                         (global_threshold, len(packets)/run_time))
            npackets = npackets_by_channel(packets, chip_id)
            for channel in range(32):
                if npackets[channel] > threshold_rate * run_time:
                    log.info('c%d-%d-ch%d rate is %.2f Hz' % \
                                 (chip_id, io_chain, channel, npackets[channel]/run_time))
                    break_flag = False
            if not break_flag:
                global_threshold += global_threshold_step
        log.info('fine global threshold scan for c%d-%d complete: %d' % \
                     (chip_id, io_chain, global_threshold))
        # Run quick pixel trim scan
        log.info('begin quick pixel trim scan for c%d-%d' % chip_info)
        pixel_trim = pixel_trim_max
        while pixel_trim >= pixel_trim_min:
            clear_buffer(controller)
            chip.config.pixel_trim_thresholds = pixel_trims
            modified_registers = range(32)
            controller.write_configuration(chip, modified_registers)
            controller.run(quick_run_time,'quick pixel trim scan')
            packets = controller.reads[-1]
            log.info('trim %d - chip rate %.2f Hz' % \
                         (pixel_trim, len(packets)/quick_run_time))
            npackets = npackets_by_channel(packets, chip_id)
            for channel in range(32):
                if npackets[channel] < threshold_rate * quick_run_time:
                    if pixel_trims[channel] <= pixel_trim_min:
                        pixel_trims[channel] = pixel_trim_min
                    else:
                        pixel_trims[channel] -= pixel_trim_step
                else:
                    log.info('c%d-%d-ch%d rate is %.2f Hz' % \
                                 (chip_id, io_chain, channel,
                                  npackets[channel]/quick_run_time))
            if all([n >= threshold_rate * quick_run_time for n in npackets]):
                break
            pixel_trim -= pixel_trim_step
        log.info('quick pixel trim scan for c%d-%d complete: %s' % \
                     (chip_id, io_chain, str(pixel_trims)))
        # Perform slow pixel scan to closely determine pixel trims
        log.info('begin fine pixel trim scan for c%d-%d' % chip_info)
        while pixel_trim <= pixel_trim_max:
            break_flag = True
            clear_buffer(controller)
            chip.config.pixel_trim_thresholds = pixel_trims
            modified_registers = range(32)
            controller.write_configuration(chip, modified_registers)
            controller.run(run_time,'pixel trim scan')
            packets = controller.reads[-1]
            log.info('trim %d - chip rate %.2f Hz' % \
                         (pixel_trim, len(packets)/run_time))
            npackets = npackets_by_channel(packets, chip_id)
            for channel in range(32):
                if npackets[channel] > threshold_rate * run_time:
                    log.info('c%d-%d-ch%d rate is %.2f Hz' % \
                                 (chip_id, io_chain, channel, npackets[channel]/run_time))
                    if pixel_trims[channel] >= pixel_trim_max:
                        pixel_trims[channel] = pixel_trim_max
                    else:
                        pixel_trims[channel] += pixel_trim_step
            if all([n <= threshold_rate * run_time for n in npackets]):
                break
            pixel_trim += pixel_trim_step
        log.info('fine pixel trim scan for c%d-%d complete: %s' % \
                     (chip_id, io_chain, pixel_trims))
        # Check one last time for high rate channels
        log.info('checking rate with configuration')
        clear_buffer(controller)
        controller.run(run_time,'rate check')
        npackets = npackets_by_channel(controller.reads[-1], chip_id)
        log.info('c%d-%d rate is %.2f Hz' % \
                         (chip_id, io_chain, channel, sum(npackets)/run_time))
        high_rate_channels = []
        for channel in range(32):
            log.info('c%d-%d-ch%d rate is %.2f Hz' % \
                         (chip_id, io_chain, channel, npackets[channel]/run_time))
            if npackets[channel] > max_rate * run_time:
                high_rate_channels += [channel]
        if len(high_rate_channels) > 0:
            log.warn('rates too high on channel %s, disabling' % \
                        (high_rate_channels))
        controller.disable(chip_id=chip_id, channel_list=high_rate_channels,
                           io_chain=io_chain)
        # Save chip configuration
        config = Configuration()
        chip_configurations += [config.from_dict(chip.config.to_dict())]
        configuration_file = outdir + '/%s_c%d-%d_config.json' % \
            (board_info, chip_id, io_chain)
        config.write(configuration_file)
        log.info('configuration saved to %s' % configuration_file)
        # Disable chip for rest of loop
        controller.disable(chip_id=chip_id, io_chain=io_chain)
        log.info('c%d-%d configuration complete' % chip_info)

    log.info('all chips configuration complete')

    # Load configuration onto chips and check final rate
    log.info('board rate check')
    for chip in controller.chips:
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        configuration_file = outdir + '/%s_c%d-%d_config.json' % \
            (board_info, chip_id, io_chain)
        chip.config.load(configuration_file)
        controller.write_configuration(chip)
    clear_buffer(controller)
    controller.run(run_time,'check rate')
    packets = controller.reads[-1]
    log.info('%s rate: %.2f Hz' % (board_info, len(packets)/run_time))
    npackets = npackets_by_chip_channel(controller.reads[-1])
    for chip in controller.chips:
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        if chip_id in npackets.keys():
            log.info('%s-c%d-%d rate: %.2f Hz' % \
                         (board_info, chip_id, io_chain, sum(npackets[chip_id])/run_time))
            for channel in range(32):
                log.info('%s-c%d-%d-ch%d rate: %.2f Hz' % \
                             (board_info, chip_id, io_chain, channel,
                              npackets[chip_id][channel]/run_time))
        else:
            log.warn('%s-c%d-%d no packets received' % \
                         (board_info, chip_id, io_chain))
    exit(0)
except Exception as error:
    log.exception(error)
    exit(1)
