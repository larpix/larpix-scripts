''''
A script to convert a .dat data file into the specified format with the
following data:

    channel id | chip id | pixel id | pixel x | pixel y | raw ADC | raw
    timestamp | 6-bit ADC | full timestamp

Note: for the h5 output, the array type is 64-bit signed integer. This
works to hold all of the data with no problem except for the pixel x and
y. These are stored as int(10*value) as a way to save some precision.
(For ROOT output, those fields are saved as floats so no problem.)

'''

from __future__ import print_function
import argparse
import numpy as np
from os.path import splitext
import json
import h5py
# from larpix.dataloader import DataLoader
from larpix.larpix import (Controller, Configuration, Packet)
from larpix.timestamp import Timestamp
from larpixgeometry.pixelplane import PixelPlane
import larpixgeometry.layouts as layouts
# parse = Controller.parse_input

def fix_ADC(raw_adc):
    '''
    Converts the 8-bit value to the appropriate 6-bit value, formed by
    dropping the LSB (//2) and MSB (- 128).

    '''
    return (raw_adc - 128)//2

parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile', nargs='?', default=None)
# parser.add_argument('-c', '--calibration', default=None)
parser.add_argument('-v', '--verbose', action='store_true')
# parser.add_argument('--format', choices=['h5', 'root', 'ROOT'],
        # required=True)
geom_choices = {'4chip': 'sensor_plane_28_simple.yaml',
        '8chip': 'sensor_plane_28_8chip.yaml',
        '28chip': 'sensor_plane_28_full.yaml',
        'v1.5anode': 'sensor_plane_pcb-5.yaml'}
parser.add_argument('-g', '--geometry', choices=geom_choices.keys(),
        required=True, help='The sensor & chip geometry layout')
args = parser.parse_args()

infile = args.infile
outfile = args.outfile
verbose = args.verbose
datafile = h5py.File(infile,'r')
if args.verbose:
    print(datafile.keys())
dataset = 'raw_packet'
# calib_data = {}

if outfile is None:
    outfile = splitext(infile)[0] + '.' + args.format.lower()
if args.verbose:
    print(infile + ' -> ' + outfile)

geometry = PixelPlane.fromDict(layouts.load(geom_choices[args.geometry]))

numpy_arrays = []
index_limit = 10000
serialblock = -1 # serial read index
numpy_arrays.append(np.empty((index_limit, 10), dtype=np.int64))
current_array = numpy_arrays[-1]
current_index = 0
last_timestamp = {}
print()
for idx in range(datafile[dataset].shape[0]):
    data_array = datafile[dataset][idx]
    serialblock += 1
    if args.verbose and serialblock % 100 == 0:
        print('\rprocessing block {}...'.format(serialblock),end='')
    if data_array['type'] == 0: # data packet
        current_array[current_index][0] = data_array['channel'] #packet.channel_id
        current_array[current_index][1] = data_array['chipid'] #packet.chipid
        current_array[current_index][5] = data_array['adc_counts'] #packet.dataword
        current_array[current_index][6] = data_array['timestamp'] #packet.timestamp
        current_array[current_index][7] = fix_ADC(data_array['adc_counts'])
        current_array[current_index][9] = serialblock

        chipid = data_array['chipid'] #packet.chipid
        channel = data_array['channel'] #packet.channel_id
        try:
            pixel = geometry.chips[chipid].channel_connections[channel]
        except KeyError:
            pixel = geometry.unconnected_pixel
        except IndexError:
            pixel = geometry.unconnected_pixel
        if pixel.pixelid is None:
            current_array[current_index][2] = -1
            current_array[current_index][3] = -1
            current_array[current_index][4] = -1
        else:
            current_array[current_index][2] = pixel.pixelid
            current_array[current_index][3] = int(10*pixel.x)
            current_array[current_index][4] = int(10*pixel.y)

        cpu_time = data_array['timestamp']
        ref_time = None
        if chipid in last_timestamp.keys():
            ref_time = last_timestamp[chipid]
        current_timestamp = Timestamp.serialized_timestamp(adc_time=cpu_time, cpu_time=data_array['record_timestamp'],
            ref_time=ref_time)#Timestamp.from_packet(packet, cpu_time,
                # ref_time)
        current_array[current_index][8] = current_timestamp.ns
        if len(last_timestamp.keys())==0:
            for chip in range(255):
                last_timestamp[chip] = current_timestamp
        else:
            last_timestamp[chipid] = current_timestamp

        current_index += 1
        if current_index == index_limit:
            current_index = 0
            numpy_arrays.append(np.empty((index_limit, 10),
                dtype=np.int64))
            current_array = numpy_arrays[-1]

numpy_arrays[-1] = numpy_arrays[-1][:current_index]
final_array = np.vstack(numpy_arrays)
with h5py.File(outfile, 'w') as outfile:
    dset = outfile.create_dataset('data', data=final_array,
            dtype=final_array.dtype)
    dset.attrs['descripiton'] = '''
channel id | chip id | pixel id | int(10*pixel x) | int(10*pixel y) | raw ADC | raw
timestamp | 6-bit ADC | full timestamp | serial index '''
print('Done!')

