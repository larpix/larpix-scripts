'''
This script generates a calibration .json file from the specified calibration data and
type. The output calibration data has the following structure:
``
{
    chipid :
    {
        channelid :
        {
        'pedestal_vref' : value,
        'pedestal_vcm' : value,
        'pedestal_adc' : value,
        'pedestal_adc_sigma' : value,
        'pedestal_v' : value,
        'pedestal_v_sigma' : value,
        'gain_v' : value,
        'gain_e' : value,
        ...
        },
        ...
    },
    ...
}
``
Thus to extract a particular chip/channel's pedestal value use
``calibration_data[chipid][channelid]['pedestal_v']``.
'''

from __future__ import print_function
import argparse
from os.path import splitext
from larpix.dataloader import DataLoader
from larpix.larpix import Controller
from sys import exit
import os
import json
import calibration
parse = Controller.parse_input

default_cal_data = {
    'pedestal_vref' : 1.5,
    'pedestal_vcm' : 0.2,
    'pedestal_adc' : 29.5,
    'pedestal_adc_sigma' : 0.,
    'pedestal_v' : 0.350,
    'pedestal_v_sigma' : 0.,
    'gain_v' : 0.005,
    'gain_e' : 4e-6
}

def fill_missing_with_default(cal_data, default_cal_data=default_cal_data):
    for chipid in cal_data.keys():
        for channelid in cal_data[chipid].keys():
            for cal_field in default_cal_data.keys():
                if not cal_field in cal_data[chipid][channelid].keys():
                    cal_data[chipid][channelid][cal_field] = default_cal_data[cal_field]

parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile', nargs='?', default=None)
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('-f', '--force', action='store_true')
parser.add_argument('-c', '--calibration', choices=['pedestal'],
        required=True)
parser.add_argument('--vref', type=float, required=True)
parser.add_argument('--vcm', type=float, required=True)
args = parser.parse_args()

infile = args.infile
outfile = args.outfile
verbose = args.verbose
calibration = args.calibration
force_overwrite = args.force
vref = args.vref
vcm = args.vcm
loader = DataLoader(infile)

if outfile is None:
    outfile = splitext(infile)[0] + '_cal.json'
if os.path.isfile(outfile) and not force_overwrite:
    print('Calibration file already exists! Use -f to update.')
    exit(1)
if args.verbose:
    print(infile + ' -> ' + outfile)

cal_data = {}
if calibration == 'pedestal':
    if verbose:
        print('Performing pedestal calibration...')
    cal_data = calibration.do_pedestal_calibration(infile, vref=vref, vcm=vcm,
                                                   verbose=verbose)
if os.path.isfile(outfile):
    # File exists - load calibration data and update
    try:
        prev_cal_data = json.load(open(outfile, 'r'))
    except ValueError:
        prev_cal_data = {}
    for chipid in cal_data.keys():
        for channelid in cal_data[chipid].keys():
            if chipid in prev_cal_data.keys() and channelid in prev_cal_data[chipid].keys():
                # Previous data exists - update
                for cal_field in cal_data[chipid][channelid].keys():
                    prev_cal_data[chipid][channelid][cal_field] = cal_data[chipid][channelid]\
                        [cal_field]
            else:
                # Previous data does not exist
                try:
                    prev_cal_data[chipid][channelid] = cal_data[chipid][channelid]
                except KeyError:
                    prev_cal_data[chipid] = {channelid : cal_data[chipid][channelid]}
    fill_missing_with_default(prev_cal_data)
    with open(outfile, 'w') as fo:
        json.dump(prev_cal_data, fo, sort_keys=True, indent=4, separators=(',',': '))
else:
    # File does not exist - write calibration data
    fill_missing_with_default(cal_data)
    with open(outfile, 'w') as fo:
        # File exisits
        json.dump(cal_data, fo, sort_keys=True, indent=4, separators=(',',': '))

exit(0)
