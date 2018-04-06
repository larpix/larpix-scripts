import time
import sys
from larpix.quickstart import *
from larpix.larpix import enable_logger, flush_logger, SerialPort, disable_logger()

enable_logger()
print 'saving to %s' % SerialPort._logger.filename
c=qc('pcb-10')
c.disable()
load_configurations(c, sys.argv[1])

if not sys.argv[2] is None:
    for chip in c.chips:
        chip.config.global_threshold += int(sys.argv[2])
        c.write_configuration(chip,32)

for _ in range(30):
    specifier = time.strftime('%Y_%m_%d_%H_%M_%S')
    print 'begin collect_data_%s' % specifier
    c.run(60,'collect_data_%s' % specifier)
    print 'end collect_data_%s' % specifier
    print 'storing...'
    flush_logger()
    print 'done'
    c.reads = []

print 'end of run %s' % SerialPort._logger.filename
disable_logger()
