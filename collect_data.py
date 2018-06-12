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
parser.add_argument('-b','--board', default=pathnames.default_board_file(start_time),
                    help='path to chip set info file (default: %(default)s)')
parser.add_argument('-s','--config', default=pathnames.default_config_dir(start_time),
                    help='initial chip configuration file to load '
                    '(default: %(default)s)')
parser.add_argument('-n','--subruns', default=1, required=False, type=int,
                    help='The number of data collection periods (default: '
                    '%(default)s)')
parser.add_argument('-t','--run_time', default=60, required=False, type=float,
                    help='The run time for each subrun in sec (default: '
                    '%(default)s)')
parser.add_argument('--global_threshold_correction', default=0, required=False,
                    type=int,
                    help='Adjustment on global threshold from values in config'
                    ' files (default: %(default)s)')
parser.add_argument('--trim_correction', default=0, required=False, type=int,
                    help='Global adjustment to pixel trims (default: %(default)s)')
parser.add_argument('-i','--interactive', action='store_true', help='Run in interactive mode allowing access to '
                    'controller and chip configurations')
parser.add_argument('-v','--verbose',  action='store_true')
args = parser.parse_args()
if args.interactive:
    from helpers.pixel_report import *
    from larpix_scripting import store_chip_configurations

sl = ScriptLogger(start_time)
log = sl.script_log
log.info('arguments: %s' % str(args))

last_read = []
controller = None # keep handle to some variables in case you want to enter an interactive session
board_info = None
try:
    controller = larpix.Controller(timeout=0.01)
    board_info = larpix_scripting.load_board(controller, args.board)
    controller.disable()
    config_ok, different_registers = larpix_scripting.load_chip_configurations(
        controller, board_info, args.config,
        threshold_correction=args.global_threshold_correction,
        trim_correction=args.trim_correction)

    for chip in controller.chips:
        chip.config.external_trigger_mask[7] = 0
        controller.write_configuration(chip,range(56,60))
    
    for _ in range(args.subruns):
        specifier = time.strftime('%Y_%m_%d_%H_%M_%S')
        log.info('begin collect_data_%s' % specifier)
        controller.run(args.run_time,'collect_data_%s' % specifier)
        last_read = controller.reads[-1]
        log.info('end collect_data_%s' % specifier)
        log.info('storing...')
        sl.flush_datalog()
        log.info('done')
        log.info('rate: %.2f Hz' % (len(controller.reads[-1])/args.run_time))
        if args.verbose:
            npackets = larpix_scripting.npackets_by_chip_channel(last_read)
            for chip_id in npackets.keys():
                for channel,npacket in enumerate(npackets[chip_id]):
                    log.info('c%d-ch%d rate: %.2f Hz' % (chip_id, channel,
                                                         float(npacket) / args.run_time))
        larpix_scripting.clear_stored_packets(controller)
        controller.reads = []

    log.info('end of run %s' % sl.data_logfile)
    if args.interactive:
        pixel_report(last_read)
        log.info('entering interactive session')
    else:
        sys.exit(0)
except Exception as error:
    log.exception(error)
    log.error('run encountered an error')
    log.info('flushing serial log...')
    sl.flush_datalog()
    log.info('done')

    log.info('run closed abnormally: %s' % sl.data_logfile)
    sys.exit(1)
