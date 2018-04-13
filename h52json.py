import h5py
import numpy as np
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('infile', help='The file to dump to JSON')
parser.add_argument('outfile', help='The destination JSON file')
args = parser.parse_args()

infile = h5py.File(args.infile, 'r')
with open(args.outfile, 'w') as outfile:
    data = np.array(infile['data']).tolist()
    json.dump(data, outfile)
