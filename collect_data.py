import argparse
import time
import sys
import larpix.larpix as larpix
import helpers.pathnames as pathnames
import helpers.larpix_scripting as larpix_scripting
from larpix.quickstart import *
from helpers.script_logging import ScriptLogger

start_time = time.localtime()

parser = argparse.ArgumentParser()
parser.add_argument('--board', default=pathnames.default_board_file(start_time),
                    help='path to chip set info file (default: %(default)s)')
parser.add_argument('--config', default=pathnames.default_config_dir(start_time),
                    help='initial chip configuration file to load '
                    '(default: %(default)s)')
parser.add_argument('--subruns', default=1, required=False, type=int,
                    help='The number of data collection periods (default: '
                    '%(default)s)')
parser.add_argument('-t','--run_time', default=60, required=False, type=float,
                    help='The run time for each subrun in sec (default: '
                    '%(default)s)')
parser.add_argument('--global_threshold_correction', default=0, required=False,
                    type=int,
                    help='Adjustment on global threshold from values in config'
                    ' files (default: %(default)s)')
args = parser.parse_args()

sl = ScriptLogger(start_time)
log = sl.script_log

try:
    controller = larpix.Controller(timeout=0.01)
    board_info = larpix_scripting.load_board(controller, args.board)
    controller.disable()
    config_ok, different_registers = larpix_scripting.load_chip_configurations(
        controller, board_info, args.config)

    if not args.global_threshold_correction == 0:
        for chip in c.chips:
            chip.config.global_threshold += args.global_threshold_correction
            c.write_configuration(chip,32)

    for _ in range(args.subruns):
        specifier = time.strftime('%Y_%m_%d_%H_%M_%S')
        log.info('begin collect_data_%s' % specifier)
        c.run(args.run_time,'collect_data_%s' % specifier)
        log.info('end collect_data_%s' % specifier)
        log.info('storing...')
        sl.flush_datalog()
        log.info('done')
        c.reads = []

    log.info('end of run %s' % sl.data_logfile)
except Exception as error:
    log.exception(error)
    log.error('run encountered an error')
    log.info('flushing serial log...')
    sl.flush_datalog()
    log.info('done')

    log.info('run closed abnormally: %s' % sl.data_logfile)
