import time
import sys
from larpix.quickstart import *
from larpix.larpix import enable_logger, flush_logger, SerialPort, disable_logger()
from helpers.logging import ScriptLogger

parser = argparse.ArgumentParser()
parser.add_argument('--config', required=True,
                    help='The configuration to load on the chips (with %d '
                    'placeholder for chip_id')
parser.add_argument('--subruns', default=1, required=False, type=int
                    help='The number of data collection times (default: '
                    '%(default)s)')
parser.add_argument('-t','--run_time', default=60, required=False, type=float,
                    help='The run time for each subrun in sec (default: '
                    '%(default)s)')
parser.add_argument('--global_threshold_correction', default=0, required=False,
                    type=int,
                    help='Adjustment on global threshold from values in config'
                    ' files (default: %(default)s)')
args = parser.parse_args()

sl = ScriptLogger('data_run')
log = sl.script_log
if outdir is None:
    outdir = sl.script_logdir

try:
    c=qc('pcb-10')
    c.disable()
    load_configurations(c, args.config)

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
