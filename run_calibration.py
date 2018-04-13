'''
This script generates a calibration .json file from the specified calibration data and
type. The output calibration data has the following structure:
``
{
    '<chipid>' :
    {
        '<channelid>' :
        {
        'pedestal_vref' : value,
        'pedestal_vcm' : value,
        'pedestal_adc' : value,
        'pedestal_adc_sigma' : value,
        'pedestal_v' : value,
        'pedestal_v_sigma' : value,
        'gain_v' : value,
        'gain_vcm' : value,
        'gain_e' : value,
        ...
        },
        ...
    },
    ...
}
``
Thus to extract a particular chip/channel's pedestal value use
``calibration_data[str(chipid)][str(channelid)]['pedestal_v']``.
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
    'gain_vcm' : 0.2,
    'gain_e' : 4e-6
}

def fill_missing_with_default(cal_data, default_cal_data=default_cal_data):
    for chipid in cal_data:
        for channelid in cal_data[chipid]:
            for cal_field in default_cal_data:
                if not cal_field in cal_data[chipid][channelid]:
                    cal_data[chipid][channelid][cal_field] = default_cal_data[cal_field]

def update_cal_data(cal_data, new_cal_data):
    if new_cal_data is None:
        return
    for chipid in new_cal_data:
        for channelid in new_cal_data[chipid]:
            for cal_field in new_cal_data[chipid][channelid]:
                try:
                    cal_data[chipid][channelid][cal_field] = \
                        new_cal_data[chipid][channelid][cal_field]
                except KeyError:
                    try:
                        cal_data[chipid][channelid] = \
                            { cal_field: new_cal_data[chipid][channelid][cal_field] }
                    except KeyError:
                        cal_data[chipid] = \
                            { channelid:
                                  { cal_field: new_cal_data[chipid][channelid][cal_field] }}

parser = argparse.ArgumentParser()
parser.add_argument('-i','--infile', nargs='+', required=True,
                    help='list of files to process')
parser.add_argument('-o','--outfile', nargs='?', default=None,
                    help='output file (if none specified saves to <infile>_calib.json for '
                    'each infile)')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('-f', '--force', action='store_true')
parser.add_argument('-c', '--calibration', nargs='+', choices=['pedestal','gain','timing'],
        required=True)
parser.add_argument('-p', '--prev_calibration', default=None)
parser.add_argument('--vref', type=float, required=False)
parser.add_argument('--vcm', type=float, required=False)
args = parser.parse_args()

infiles = args.infile
outfile = args.outfile
prev_calib = args.prev_calibration
verbose = args.verbose
calibration_type = args.calibration
force_overwrite = args.force
vref = args.vref
vcm = args.vcm

if not args.outfile is None and os.path.isfile(outfile) and not force_overwrite:
    print('Calibration file already exists! Use -f to update.')
    exit(1)
if not args.outfile is None and args.verbose:
    print(str(infiles) + ' -> ' + outfile)

for infile in infiles:
    loader = DataLoader(infile)

    cal_data = {}
    if not prev_calib is None:
        cal_data = json.load(open(prev_calib, 'r'))
        if verbose:
            print('Using previous calibration %s' % prev_calib)

    if args.outfile is None:
        outfile = splitext(infile)[0] + '_calib.json'
        if verbose:
            print(infile + ' -> ' + outfile)

    if 'pedestal' in calibration_type:
        if verbose:
            print('Performing pedestal calibration...')
        new_cal_data = calibration.do_pedestal_calibration(infile, vref=vref, vcm=vcm,
                                                           verbose=verbose)
        update_cal_data(cal_data, new_cal_data)
    if 'gain' in calibration_type:
        if verbose:
            print('Performing gain calibration...')
        new_cal_data = calibration.do_gain_calibration(infile, vref=vref, vcm=vcm,
                                                       verbose=verbose)
        update_cal_data(cal_data, new_cal_data)
    if 'timing' in calibration_type:
        if verbose:
            print('Performing timing calibration...')
        new_cal_data = calibration.do_timing_calibration(infile, verbose=verbose)
        update_cal_data(cal_data, new_cal_data)

    if os.path.isfile(outfile):
        # File exists - load calibration data and update
        prev_cal_data = {}
        try:
            prev_cal_data = json.load(open(outfile, 'r'))
        except ValueError as e:
            print('Error: %s' % e)
            pass
        for chipid in cal_data:
            for channelid in cal_data[chipid]:
                if chipid in prev_cal_data and channelid in prev_cal_data[chipid]:
                    # Previous data exists - update
                    for cal_field in cal_data[chipid][channelid]:
                        prev_cal_data[chipid][channelid][cal_field] = \
                            cal_data[chipid][channelid][cal_field]
                else:
                    # Previous data does not exist
                    try:
                        prev_cal_data[chipid][channelid] = cal_data[chipid][channelid]
                    except KeyError:
                        prev_cal_data[chipid] = {channelid : cal_data[chipid][channelid]}
        #fill_missing_with_default(prev_cal_data)
        with open(outfile, 'w') as fo:
            json.dump(prev_cal_data, fo, sort_keys=True, indent=4, separators=(',',': '))
    else:
        # File does not exist - write calibration data
        #fill_missing_with_default(cal_data)
        with open(outfile, 'w') as fo:
            # File exisits
            json.dump(cal_data, fo, sort_keys=True, indent=4, separators=(',',': '))

exit(0)
