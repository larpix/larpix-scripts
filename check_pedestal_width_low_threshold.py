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
from helpers.script_logging import ScriptLogger
import helpers.pathnames as pathnames
import helpers.larpix_scripting as larpix_scripting
import helpers.script_plotting as script_plotting
import time
import larpix.larpix as larpix
import larpix.serialport as serialport
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
parser.add_argument('--global_threshold', default=0, type=int,
                    help='(optional, default: %(default)s)')
parser.add_argument('-t','--run_time', default=0.05, type=float,
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
run_time = args.run_time
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
    #io = serialport.SerialPort()
    io = ZMQ_IO('tcp://10.0.1.6')
    controller.io = io
    # Initial configuration of chips
    board_info = larpix_scripting.load_board(controller, infile)
    log.info('begin initial configuration of chips for board %s' % board_info)
    config_ok, different_registers = larpix_scripting.load_chip_configurations(
        controller, board_info, config_file, silence=True, default_config=default_config)
    if config_ok:
        log.info('initial configuration of chips complete')

    # Run low pedestal test on each chip
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

            larpix_scripting.clear_buffer(controller)
            chip_results = noise_tests.noise_test_low_threshold(controller=controller,
                                                                chip_idx=chip_idx,
                                                                global_threshold=\
                                                                    global_threshold,
                                                                run_time=run_time)
            board_results += [chip_results]
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

    # Print pedestal scan results
    plot_data = []
    for chip_idx,chip in enumerate(controller.chips):
        chip_id = chip.chip_id
        io_chain = chip.io_chain
        if board_results[chip_idx] is None:
            log.info('%s-%d-c%d skipped' % (board_info, io_chain, chip_id))
            continue
        chip_ped_mean = sum(board_results[chip_idx][1].values()) /\
            len(board_results[chip_idx][1].values())
        chip_ped_rms = sum(abs(ped - chip_ped_mean)
                           for ped in board_results[chip_idx][1].values()) /\
                           len(board_results[chip_idx][1])
        log.info('%s-%d-c%d mean pedestal: %.2f adc, rms: %.2f adc' % \
                     (board_info, io_chain, chip_id, chip_ped_mean, chip_ped_rms))

        chip_width_mean = sum(board_results[chip_idx][2].values()) /\
            len(board_results[chip_idx][2].values())
        chip_width_rms = sum(abs(width - chip_width_mean)
                             for width in board_results[chip_idx][2].values())/\
                             len(board_results[chip_idx][2])
        log.info('%s-%d-c%d mean width: %.2f adc, rms: %.2f adc' % \
                     (board_info, io_chain, chip_id, chip_width_mean, chip_width_rms))
        for channel in board_results[chip_idx][1].keys():
            log.info('%s-%d-c%d-ch%d pedestal: %.2f adc, width: %.2f adc' % \
                         (board_info, io_chain, chip_id, channel,
                          board_results[chip_idx][1][channel],
                          board_results[chip_idx][2][channel]))
        if make_plots:
            plot_data += [(chip_idx, chip_id, io_chain, [channel for channel in board_results[chip_idx][0].keys()], [board_results[chip_idx][0][channel] for channel in board_results[chip_idx][0].keys()])]

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
