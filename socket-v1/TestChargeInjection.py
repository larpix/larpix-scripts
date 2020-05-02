from configure_to_rate import _configure_to_rate
from larpix.larpix import *
from larpix.io.zmq_io import ZMQ_IO
from larpix.logger.h5_logger import HDF5Logger

c = Controller()
c.io = ZMQ_IO('../configs/io/daq-srv1.json', miso_map={2:1})
c.load('../configs/controller/pcb-3_chip_info.json')
c.io.ping()
for key,chip in c.chips.items():
	chip.config.load('../configs/chip/quiet.json')
	c.write_configuration(key)

if not c.verify_configuration():
        print("verify configuration failed!")
        exit();

c.disable()
chip_key = '1-1-10'

c.chips[chip_key].config.global_threshold = 24
c.write_configuration(chip_key)
if not c.verify_configuration():
        print("verify configuration failed!")
        exit()

c.enable(chip_key,[5])
c.chips[chip_key].config.sample_cycles = 255
#c.enable_analog_monitor(chip_key, 26)
c.enable_testpulse(chip_key, [5], start_dac=200)
c.write_configuration(chip_key)

if not c.verify_configuration():
        print("verify configuration failed!")
        exit();


#logger declared and switched enabled
c.logger = HDF5Logger(None, True)
c.logger.enable()
c.logger.is_enabled()

c.verify_configuration(chip_key)
print(c.chips[chip_key].config)

min_dac = 110
max_count = 1000
count = 0

while(count < max_count):
        while(c.chips[chip_key].config.csa_testpulse_dac_amplitude > min_dac and count < max_count):
                c.issue_testpulse(chip_key, 5, min_dac=100) 
                #print(c.reads[-1])
                count+=1
                #print(count)
        c.enable_testpulse(chip_key, [5], start_dac=200)

print("the end")

c.logger.disable()
c.logger.close()
