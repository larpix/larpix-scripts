'''
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
from larpix.dataloader import DataLoader
from larpix.larpix import Controller
from larpix.Timestamp import Timestamp
from larpixgeometry.pixelplane import PixelPlane
import larpixgeometry.layouts as layouts
parse = Controller.parse_input

def fix_ADC(raw_adc):
    '''
    Converts the 8-bit value to the appropriate 6-bit value, formed by
    dropping the LSB (//2) and MSB (- 128).

    '''
    return (raw_adc - 128)//2

parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile', nargs='?', default=None)
parser.add_argument('-c', '--calibration', default=None)
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('--format', choices=['h5', 'root', 'ROOT'],
        required=True)
geom_choices = {'4chip': 'sensor_plane_28_simple.yaml',
        '8chip': 'sensor_plane_28_8chip.yaml',
        '28chip': 'sensor_plane_28_full.yaml'}
}
parser.add_argument('-g', '--geometry', choices=geom_choices.keys(),
        required=True, help='The sensor & chip geometry layout')
args = parser.parse_args()

infile = args.infile
outfile = args.outfile
verbose = args.verbose
loader = DataLoader(infile)
calib_data = {}

if outfile is None:
    outfile = splitext(infile)[0] + '.' + args.format.lower()
if args.verbose:
    print(infile + ' -> ' + outfile)
if not args.calibration is None:
    calib_data = json.load(open(args.calibration,'r'))
if args.format == 'h5':
    import h5py
    use_root = False
elif args.format.lower() == 'root':
    use_root = True
    import ROOT
    root_channelid = np.array([-1], dtype=int)
    root_chipid = np.array([-1], dtype=int)
    root_pixelid = np.array([-1], dtype=int)
    root_pixelx = np.array([0], dtype=float)
    root_pixely = np.array([0], dtype=float)
    root_rawADC = np.array([-1], dtype=int)
    root_rawTimestamp = np.array([0], dtype=np.uint64)
    root_ADC = np.array([-1], dtype=int)
    root_timestamp = np.array([0], dtype=np.uint64)
    root_serialblock = np.array([-1], dtype=int)
    root_v = np.array([-1], dtype=float)
    root_pdst_v = np.array([-1], dtype=float)
    fout = ROOT.TFile(outfile, 'recreate')
    ttree = ROOT.TTree('larpixdata', 'LArPixData')
    ttree.Branch('channelid', root_channelid, 'channelid/I')
    ttree.Branch('chipid', root_chipid, 'chipid/I')
    ttree.Branch('pixelid', root_pixelid, 'pixelid/I')
    ttree.Branch('pixelx', root_pixelx, 'pixelx/D')
    ttree.Branch('pixely', root_pixely, 'pixely/D')
    ttree.Branch('raw_adc', root_rawADC, 'raw_adc/I')
    ttree.Branch('raw_timestamp', root_rawTimestamp, 'raw_timestamp/l')
    ttree.Branch('adc', root_ADC, 'adc/I')
    ttree.Branch('timestamp', root_timestamp, 'timestamp/l')
    ttree.Branch('serialblock', root_serialblock, 'serialblock/I')
    ttree.Branch('v', root_v, 'v/D')
    ttree.Branch('pdst_v', root_pdst_v, 'pdst_v/D')

#geometry = PixelPlane.fromDict(layouts.load('sensor_plane_28_simple.yaml'))
geometry = PixelPlane.fromDict(layouts.load(args.geometry))

numpy_arrays = []
index_limit = 10000
serialblock = -1 # serial read index
numpy_arrays.append(np.empty((index_limit, 12), dtype=np.int64))
current_array = numpy_arrays[-1]
current_index = 0
last_timestamp = {}
while True:
    block = loader.next_block()
    serialblock += 1
    if block is None: break
    if block['block_type'] == 'data' and block['data_type'] == 'read':
        packets = parse(bytes(block['data']))
        for packet in packets:
            if packet.packet_type == packet.DATA_PACKET:
                current_array[current_index][0] = packet.channel_id
                current_array[current_index][1] = packet.chipid
                current_array[current_index][5] = packet.dataword
                current_array[current_index][6] = packet.timestamp
                current_array[current_index][7] = fix_ADC(packet.dataword)
                current_array[current_index][9] = serialblock

                chipid = packet.chipid
                channel = packet.channel_id
                pixel = geometry.chips[chipid].channel_connections[channel]
                current_array[current_index][2] = pixel.pixelid
                current_array[current_index][3] = int(10*pixel.x)
                current_array[current_index][4] = int(10*pixel.y)

                try:
                    current_array[current_index][10] = 1e3*((packet.dataword) * \
                        calib_data[str(chipid)][str(channel)]['gain_v'] + \
                        calib_data[str(chipid)][str(channel)]['gain_vcm'])
                except KeyError:
                    current_array[current_index][10] = -1
                try:
                    current_array[current_index][11] = 1e3 * calib_data[str(chipid)][str(\
                            channel)]['pedestal_v']
                except KeyError:
                    current_array[current_index][11] = -1

                cpu_time = block['time']
                ref_time = None
                if packet.chipid in last_timestamp.keys():
                    ref_time = last_timestamp[packet.chipid]
                current_timestamp = Timestamp.from_packet(packet, cpu_time,
                        ref_time)
                current_array[current_index][8] = current_timestamp.ns
                if len(last_timestamp.keys())==0:
                    for chip in range(255):
                        last_timestamp[chip] = current_timestamp
                else:
                    last_timestamp[chipid] = current_timestamp

                if use_root:
                    (root_channelid[0], root_chipid[0], root_pixelid[0],
                            root_pixelx[0], root_pixely[0],
                            root_rawADC[0], root_rawTimestamp[0],
                            root_ADC[0], root_timestamp[0],
                            root_serialblock[0], root_v[0],
                            root_pdst_v[0]
                        ) = current_array[current_index]
                    ttree.Fill()
                else:
                    current_index += 1
                    if current_index == index_limit:
                        current_index = 0
                        numpy_arrays.append(np.empty((index_limit, 12),
                            dtype=np.int64))
                        current_array = numpy_arrays[-1]

if use_root:
    ttree.Write()
    fout.Write()
    fout.Close()
else:
    numpy_arrays[-1] = numpy_arrays[-1][:current_index]
    final_array = np.vstack(numpy_arrays)
    with h5py.File(outfile, 'w') as outfile:
        dset = outfile.create_dataset('data', data=final_array,
                dtype=final_array.dtype)
        dset.attrs['descripiton'] = '''
    channel id | chip id | pixel id | int(10*pixel x) | int(10*pixel y) | raw ADC | raw
    timestamp | 6-bit ADC | full timestamp | serial index | converted voltage (mV) | calib
    pedestal voltage (mV)'''

