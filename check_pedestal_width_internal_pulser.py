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
import math
from helpers.script_logging import ScriptLogger
import helpers.pathnames as pathnames
import helpers.larpix_scripting as larpix_scripting
import helpers.script_plotting as script_plotting
import time
import larpix.larpix as larpix
from larpix.serialport import SerialPort
from larpix.zmq_io import ZMQ_IO
import helpers.noise_tests as noise_tests
from sys import (exit, stdout)
import json
import os

start_time = time.localtime()
default_config = 'physics.json'

parser = argparse.ArgumentParser()
parser.add_argument('-b','--board', default=pathnames.default_board_file(start_time),
                    help='input file containing chipset info (optional, default: '
                    '%(default)s)')
parser.add_argument('-o','--outdir', default=pathnames.default_script_logdir(start_time),
                    help='output directory for log file and data files '
                    '(optional, default: %(default)s)')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('--global_threshold', default=40, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--pulse_channel_trim', default=0, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--pulse_dac', default=6, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--testpulse_dac_max', default=255, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--testpulse_dac_min', default=128, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--n_pulses', default=500, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--pulse_channel_0', default=0, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--pulse_channel_1', default=31, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('--max_rate', default=0.1, type=float,
                    help='max rate before disabling channels (and excluding from test) '
                    '(optional, units: Hz, default=%(default)s)')
parser.add_argument('--csa_recovery_time', default=0.05, type=float,
                    help='(optional, units: sec,  default: %(default)s)')
parser.add_argument('--reset_dac_time', default=0.05, type=float,
                    help='(optional, units: sec,  default: %(default)s)')
parser.add_argument('-s','--configuration_file', default=None,
                    help='initial chip configuration file to load '
                    'by default will look in %s for individual chip configurations, '
                    'if chip config not found, will load %s, '
                    'if this file does not exist, will load %s and generate new default '
                    '(optional)' % (pathnames.default_config_dir(start_time),
                                    pathnames.default_config_file(start_time),
                                    default_config))
parser.add_argument('-c','--chips', default=None, nargs='+', type=int,
                    help='chips to include in scan '
                    '(optional, default: all chips in chipset file)')
parser.add_argument('-p','--plot', action='store_true',
                    help='generate and save plots (optional)')
args = parser.parse_args()

infile = args.board
outdir = args.outdir
verbose = args.verbose
global_threshold = args.global_threshold
pulse_channel_trim = args.pulse_channel_trim
testpulse_dac_max = args.testpulse_dac_max
testpulse_dac_min = args.testpulse_dac_min
csa_recovery_time = args.csa_recovery_time
reset_dac_time = args.reset_dac_time
pulse_dac = args.pulse_dac
n_pulses = args.n_pulses
max_rate = args.max_rate
pulse_channel_0 = args.pulse_channel_0
pulse_channel_1 = args.pulse_channel_1
pulse_channels = [pulse_channel_0, pulse_channel_1]
config_file = args.configuration_file
if config_file is None:
    config_file = pathnames.default_config_dir(start_time)
    default_config = pathnames.make_default_config(start_time, default_config)
chips_to_scan = args.chips
make_plots = args.plot

return_code = 0

script_logfile = outdir + '/' + \
    os.path.basename(pathnames.default_script_logfile(start_time))
data_logfile = outdir + '/' + os.path.basename(pathnames.default_data_logfile(start_time))
sl = ScriptLogger(start_time, script_logfile=script_logfile, data_logfile=data_logfile)
log = sl.script_log
log.info('arguments: %s' % str(args))

try:
    controller = larpix.Controller()
    #controller.io = SerialPort()
    controller.io = ZMQ_IO('tcp://10.0.1.6')
    # Initial configuration of chips
    board_info = larpix_scripting.load_board(controller, infile)
    log.info('begin initial configuration of chips for board %s' % board_info)
    config_ok, different_registers = larpix_scripting.load_chip_configurations(
        controller, board_info, config_file, silence=True, default_config=default_config)
    if config_ok:
        log.info('initial configuration of chips complete')

    # Testpulse one channel on each chip while cross-triggering others
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

            controller.enable(chip_id=chip_id, io_chain=io_chain)
            # Disable any noisy channels (will not have pedestal info from these channels)
            log.info('checking for high rate channels (rate > %.2fHz)' % max_rate)
            high_threshold_channels = set()
            break_flag = False
            run_time = 1.0
            while not break_flag:
                break_flag = True
                larpix_scripting.clear_buffer(controller)
                log.info('check rate')
                controller.run(run_time,'rate check')
                npackets = larpix_scripting.npackets_by_channel(controller.reads[-1],
                                                                chip_id=chip_id)
                for channel,npacket in enumerate(npackets):
                    rate = float(npacket) / run_time
                    if rate > max_rate:
                        log.warning('high rate on c%d-ch%d (%.2f Hz)' % (\
                                chip_id, channel, rate))
                        break_flag = False
                        high_threshold_channels.add(channel)
                log.info('disable c%d channels %s' % (\
                        chip_id, high_threshold_channels))
                controller.disable(chip_id=chip_id,
                                   channel_list=list(high_threshold_channels))

            chip_data = []
            for pulse_channel in pulse_channels:
                larpix_scripting.clear_buffer(controller)
                chip_data += [noise_tests.noise_test_internal_pulser(\
                    controller=controller, chip_idx=chip_idx, threshold=global_threshold,
                    reset_dac_time=reset_dac_time, csa_recovery_time=csa_recovery_time,
                    pulse_dac=pulse_dac, n_pulses=int(n_pulses/2),
                    pulse_channel=pulse_channel,
                    reset_cycles=chip.config.reset_cycles,
                    testpulse_dac_max=testpulse_dac_max,
                    testpulse_dac_min=testpulse_dac_min, trim=pulse_channel_trim)]
            chip_results = {
                'adc_rms' : {},
                'adc_mean': {},
                'channel_results': {},
                }
            for pulse_channel_idx, pulse_channel_packets in enumerate(chip_data):
                for testpulse_packets in pulse_channel_packets:
                    for packet in testpulse_packets:
                        if packet.channel_id in chip_results['channel_results'].keys() and packet.channel_id != pulse_channels[pulse_channel_idx]:
                            chip_results['channel_results'][packet.channel_id]['n'] += 1
                            chip_results['channel_results'][packet.channel_id]['adc_sum'] += packet.dataword
                            chip_results['channel_results'][packet.channel_id]['adc_sqsum'] += packet.dataword**2
                            chip_results['channel_results'][packet.channel_id]['adc'] += [packet.dataword]
                        elif packet.channel_id != pulse_channels[pulse_channel_idx]:
                            chip_results['channel_results'][packet.channel_id] = {
                                'n' : 1,
                                'adc_sum' : packet.dataword,
                                'adc_sqsum' : packet.dataword**2,
                                'adc' : [packet.dataword]
                                }
            for channel in sorted(chip_results['channel_results'].keys()):
                chip_results['adc_mean'][channel] = float(\
                    chip_results['channel_results'][channel]['adc_sum']) / chip_results['channel_results'][channel]['n']
                chip_results['adc_rms'][channel] = math.sqrt(\
                    float(chip_results['channel_results'][channel]['adc_sqsum'])\
                        / chip_results['channel_results'][channel]['n'] \
                        - chip_results['adc_mean'][channel]**2)
                log.info('%d-c%d-ch%d adc mean: %.2f, adc rms: %.2f' % (\
                        chip.io_chain, chip.chip_id, channel, \
                            chip_results['adc_mean'][channel], \
                            chip_results['adc_rms'][channel]))

            board_results += [chip_results]
            controller.disable(chip_id=chip_id, io_chain=io_chain)
            larpix_scripting.clear_stored_packets(controller)
            finish_time = time.time()
            if verbose:
                log.debug('%d-c%d pedestal scan took %.2f s' % \
                              (io_chain, chip_id, finish_time - start_time))
        except Exception as error:
            log.exception(error)
            log.error('%d-c%d pedestal scan failed!' % chip_info)
            controller.disable(chip_id=chip_id, io_chain=io_chain)
            return_code = 2
            board_results += [None]
            continue

    log.info('all chips pedestal complete')

    plot_data = []
    for chip_idx,chip in enumerate(controller.chips):
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        if board_results[chip_idx] is None:
            log.info('%s-%d-c%d skipped' % (board_info, io_chain, chip_id))
            continue

        if make_plots:
            plot_data += [(chip_idx, chip_id, io_chain, [channel for channel in board_results[chip_idx]['channel_results'].keys()], [board_results[chip_idx]['channel_results'][channel]['adc'] for channel in board_results[chip_idx]['channel_results'].keys()])]

    if make_plots:
        # Save profile
        figure_title = os.path.basename(script_logfile.replace('.log','.pdf'))
        fig, ax = script_plotting.plot_pedestal_width(plot_data, figure_title=figure_title)
        log.info('Saving plot to {}...'.format(outdir + '/' + figure_title))
        script_plotting.save_figure(fig, outdir + '/' + figure_title)

        # Save 2d histogram
        figure_title = os.path.basename(script_logfile.replace('.log','_hist2d.pdf'))
        fig, ax = script_plotting.plot_pedestal_width_hist2d(plot_data, figure_title=figure_title)
        log.info('Saving plot to {}...'.format(outdir + '/' + figure_title))
        script_plotting.save_figure(fig, outdir + '/' + figure_title)

        # Save 1D histograms of ADC mean
        figure_title = os.path.basename(script_logfile.replace('.log','_mean_hist.pdf'))
        fig, ax = script_plotting.plot_pedestal_width_mean_hist(plot_data, figure_title=figure_title, label='All chips')
        log.info('Saving plot to {}...'.format(outdir + '/' + figure_title))
        script_plotting.save_figure(fig, outdir + '/' + figure_title)

        for chip_idx in range(len(plot_data)):
            chip = controller.chips[chip_idx]
            chip_id = chip.chip_id
            io_chain = chip.io_chain
            figure_title = os.path.basename(script_logfile.replace('.log','_mean_hist_{}-{}-c{}.pdf'.format(board_info, io_chain, chip_id)))
            fig, ax = script_plotting.plot_pedestal_width_mean_hist([plot_data[chip_idx]], figure_title=figure_title, label='Chip {}, IO chain {}'.format(chip_id, io_chain))
            log.info('Saving plot to {}...'.format(outdir + '/' + figure_title))
            script_plotting.save_figure(fig, outdir + '/' + figure_title)

        # Save 1D histograms of ADC rms
        figure_title = os.path.basename(script_logfile.replace('.log','_rms_hist.pdf'))
        fig, ax = script_plotting.plot_pedestal_width_rms_hist(plot_data, figure_title=figure_title, label='All chips')
        log.info('Saving plot to {}...'.format(outdir + '/' + figure_title))
        script_plotting.save_figure(fig, outdir + '/' + figure_title)

        for chip_idx in range(len(plot_data)):
            chip = controller.chips[chip_idx]
            chip_id = chip.chip_id
            io_chain = chip.io_chain
            figure_title = os.path.basename(script_logfile.replace('.log','_rms_hist_{}-{}-c{}.pdf'.format(board_info, io_chain, chip_id)))
            fig, ax = script_plotting.plot_pedestal_width_rms_hist([plot_data[chip_idx]], figure_title=figure_title, label='Chip {}, IO chain {}'.format(chip_id, io_chain))
            log.info('Saving plot to {}...'.format(outdir + '/' + figure_title))
            script_plotting.save_figure(fig, outdir + '/' + figure_title)

except Exception as error:
    log.exception(error)
    return_code = 1

exit(return_code)
