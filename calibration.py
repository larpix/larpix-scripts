from larpix.analyzers import LogAnalyzer
from larpix.larpix import Packet
import numpy as np
import argparse
import json
import ROOT
import sys

def adc_to_v(adc, vref, vcm):
    return adc * (vref - vcm) / 256 + vcm

def is_good_data(trans):
    if trans['block_type'] != 'data': return False
    if trans['data_type'] != 'read': return False
    if len(trans['packets']) <= 0: return False
    return True

def is_good_packet(packet):
    if packet.packet_type != Packet.DATA_PACKET: return False
    if packet.has_valid_parity() is False: return False
    return True

def good_bins(values, step=1, min_v=None, max_v=None):
    if min_v is None:
        min_v = min(values)
    if max_v is None:
        max_v = max(values)
    nsteps = int((max_v - min_v) / float(step)+1)
    bins = np.linspace(min_v, max_v, nsteps)
    return bins

def find_fwhm(hist, max_bin):
    half_max_bin_high = max_bin
    half_max_bin_low = max_bin
    max = hist.GetBinContent(max_bin)
    while( half_max_bin_high < hist.GetNbinsX() and 
           hist.GetBinContent(half_max_bin_high) > max/2 ):
        half_max_bin_high += 1
    while( half_max_bin_low < hist.GetNbinsX() and 
           hist.GetBinContent(half_max_bin_low) > max/2 ):
        half_max_bin_low -= 1
    return hist.GetBinLowEdge(half_max_bin_high) - hist.GetBinLowEdge(half_max_bin_low)

def fit_dist_gaus(hist, max, min):
    f_gaus = ROOT.TF1('f_gaus','[0]*exp(-(x-[1])^2/2/[2]^2)', min, max)
    f_gaus.SetParameter(0, hist.GetMaximum())
    f_gaus.SetParameter(1, hist.GetBinLowEdge(hist.GetMaximumBin()))
    fwhm = find_fwhm(hist, hist.GetMaximumBin())
    if fwhm != 0:
        f_gaus.SetParameter(2, fwhm)
    else:
        f_gaus.SetParameter(2, hist.GetRMS())
    result = hist.Fit('f_gaus','NLS')
    return_dict = {
        'status': int(result),
        'peak': result.Parameter(0),
        'mean': result.Parameter(1),
        'sigma': result.Parameter(2),
        }
    return return_dict

def extract_adc_dist(filename, adc_max=255, adc_min=0, adc_step=2, max_trans=None,
                     verbose=False):
    la = LogAnalyzer(filename)
    adc_dist = {}
    loop_data = {
        'n_trans': 0,
        'n_trans_cut': 0,
        'n_packets': 0,
        'n_packets_cut': 0
        }

    chips_silenced = False # cuts out all data before first write command
    while True:
        curr_trans = la.next_transmission()
        if curr_trans is None: break
        if loop_data['n_trans'] == max_trans: break
        loop_data['n_trans'] += 1
        if verbose and loop_data['n_trans'] % 100 == 0:
            print('trans: %d, trans_cut: %d, packets: %d, packets_cut: %d\r' % 
                  (loop_data['n_trans'], loop_data['n_trans_cut'], loop_data['n_packets'],
                   loop_data['n_packets_cut'])),
            sys.stdout.flush()
        if curr_trans['block_type'] is 'data' and curr_trans['data_type'] is 'write':
            chips_silenced = True # assumes first write is a silence command
        if not is_good_data(curr_trans):
            loop_data['n_trans_cut'] += 1
            continue
        if not chips_silenced:
            loop_data['n_trans_cut'] += 1
            continue
        loop_data['n_packets'] += len(curr_trans['packets'])
        for packet in curr_trans['packets']:
            if not is_good_packet(packet): 
                loop_data['n_packets_cut'] += 1
                continue
            chip_id = packet.chipid
            channel_id = packet.channel_id
            adc = packet.dataword
            try:
                hist = adc_dist[chip_id][channel_id]
                hist.Fill(adc)
            except KeyError:
                try:
                    bins = good_bins([], step=adc_step, min_v=adc_min, max_v=adc_max)
                    adc_dist[chip_id][channel_id] = ROOT.TH1F('c%d_ch%d_adc' % (chip_id,
                                                                                channel_id),
                                                              ';adc;count;', len(bins)-1,
                                                              bins)
                except KeyError:
                    # Entry for chip has not been created
                    bins = good_bins([], step=adc_step, min_v=adc_min, max_v=adc_max)
                    adc_dist[chip_id] = { 
                        channel_id : ROOT.TH1F('c%d_ch%d_adc' % (chip_id, channel_id),
                                               ';adc;count', len(bins)-1, bins)
                        }
    print(' N_transmissions: %4d, N_transmissions removed: %4d' % (
            loop_data['n_trans'], loop_data['n_trans_cut']))
    print(' N_packets: %4d, N_packets removed: %4d' % (
            loop_data['n_packets'], loop_data['n_packets_cut']))
    return adc_dist

def do_pedestal_calibration(infile, vref=None, vcm=None, verbose=False):
    adc_max = 256
    adc_min = -1
    adc_step = 2

    pedestal_data = {}

    # Get distributions of adc values
    if verbose:
        print('Begin pedestal calibration')
        print('Extracting data from %s' % infile)
    adc_dist = extract_adc_dist(infile, adc_max, adc_min, adc_step, verbose=verbose)

    for chipid in adc_dist:
        for channelid in adc_dist[chipid]:
            # Fit adc distributions
            if verbose:
                print('Fit c%d-ch%d adc dist' % (chipid, channelid))
            adc_fit = fit_dist_gaus(adc_dist[chipid][channelid], max=255, min=0)
            if adc_fit['status'] == 0:
                try:
                    pedestal_data[chipid][channelid] = { 
                        'pedestal_adc': adc_fit['mean'],
                        'pedestal_adc_sigma': adc_fit['sigma']
                        }
                except KeyError:
                    pedestal_data[chipid] = { channelid: {
                            'pedestal_adc': adc_fit['mean'],
                            'pedestal_adc_sigma': adc_fit['sigma']
                            }}
            
            # Calculate voltage distributions
            if not vref is None and not vcm is None:
                try:
                    pedestal_data[chipid][channelid]['pedestal_vref'] = vref
                    pedestal_data[chipid][channelid]['pedestal_vcm'] = vcm
                except KeyError:
                    pedestal_data[chipid] = { channelid: {
                            'pedestal_vref': vref,
                            'pedestal_vcm': vcm
                            }}
                if verbose:
                    print('Fit c%d-ch%d v dist' % (chipid, channelid))
                adc_hist = adc_dist[chipid][channelid]
                v_bins = np.array([adc_to_v(adc_hist.GetBinLowEdge(bin), vref, vcm) 
                                   for bin in range(adc_hist.GetNbinsX())], dtype=float)
                v_dist = ROOT.TH1F('c%d_ch%d_v' % (chipid, channelid),
                                   ';v;count', len(v_bins)-1, v_bins)
                v_dist.Sumw2()
                for bin in range(v_dist.GetNbinsX()):
                    v_dist.Fill(v_dist.GetBinLowEdge(bin), adc_hist.GetBinContent(bin))
                v_fit = fit_dist_gaus(v_dist, max=adc_to_v(adc_max, vref, vcm), 
                                      min=adc_to_v(adc_min, vref, vcm))
                if v_fit['status'] == 0:
                    pedestal_data[chipid][channelid]['pedestal_v'] = v_fit['mean']
                    pedestal_data[chipid][channelid]['pedestal_v_sigma'] = v_fit['sigma']

    return pedestal_data
