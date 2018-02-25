from larpix.analyzers import LogAnalyzer
from larpix.larpix import Packet
import numpy as np
import argparse
import json
import ROOT
import sys

def adc_to_v(adc, vref, vcm):
    '''
    Function to convert an 8-bit adc value to a voltage based on two reference voltages
    '''
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
    '''
    Returns a list of values ranging from min-step to max+step of data (or specified min and
    max) with the specified step size
    '''
    if min_v is None:
        min_v = min(values)
    if max_v is None:
        max_v = max(values)
    nsteps = int((max_v - min_v) / float(step)+3)
    bins = np.linspace(min_v-step, max_v+step, nsteps)
    return bins

def inverse_interpolate(hist, y, bins):
    '''
    Linear interpolation to find the point at which the histogram value crosses y
    '''
    bins = sorted(bins)
    x0 = hist.GetBinCenter(bins[0])
    x1 = hist.GetBinCenter(bins[1])
    y0 = hist.GetBinContent(bins[0])
    y1 = hist.GetBinContent(bins[1])
    if y1 == y0:
        return x0
    return (y - y0) * (x1 - x0) / (y1 - y0) + x0

def integral_within_range(hist, x_low, x_high, moment=0):
    '''
    Calculates the integral ``x^m * f(x) dx`` of the distribution within a range
    Assumes a uniform distribution within bins
    '''
    sum = 0.
    low_bin = hist.FindBin(x_low)
    high_bin = hist.FindBin(x_high)
    if not high_bin == low_bin:
        sum += hist.GetBinContent(low_bin) * (get_bin_high_edge(hist, low_bin) - x_low) / \
            hist.GetBinWidth(low_bin) * ((get_bin_high_edge(hist, low_bin) + x_low)/2)**moment
        sum += hist.GetBinContent(high_bin) * (x_high - hist.GetBinLowEdge(high_bin)) / \
            hist.GetBinWidth(high_bin) * ((hist.GetBinLowEdge(high_bin) + x_high)/2)**moment
    else:
        sum += hist.GetBinContent(low_bin) * (x_high - x_low) / \
            hist.GetBinWidth(low_bin) * ((x_high + x_low)/2)**moment
    for bin in range(low_bin+1,high_bin):
        sum += hist.GetBinContent(bin) * hist.GetBinCenter(bin)**moment
    return sum

def get_bin_high_edge(hist, bin):
    return hist.GetBinLowEdge(bin) + hist.GetBinWidth(bin)

def find_fwhm(hist, max_bin):
    '''
    Returns the linear interpolated half max values above and below the specified bin
    '''
    half_max_bin_high = max_bin
    half_max_bin_low = max_bin
    max = hist.GetBinContent(max_bin)
    hm = max/2.
    while( half_max_bin_high < hist.GetNbinsX() and
           hist.GetBinContent(half_max_bin_high) > max/2 ):
        half_max_bin_high += 1
    hm_high = inverse_interpolate(hist, hm, [half_max_bin_high, half_max_bin_high-1])
    while( half_max_bin_low > 0 and
           hist.GetBinContent(half_max_bin_low) > max/2 ):
        half_max_bin_low -= 1
    hm_low = inverse_interpolate(hist, hm, [half_max_bin_low, half_max_bin_low+1])
    return (hm_low, hm_high)

def get_peak_values(hist):
    '''
    Returns the peak value, the mean value within the fwhm of peak, and the sigma of the
    peak (calculated from fwhm)
    '''
    max_bin = hist.GetMaximumBin()
    max_x = hist.GetBinCenter(max_bin)
    max_y = hist.GetBinContent(max_bin)
    hm_low, hm_high = find_fwhm(hist, max_bin)
    fwhm = hm_high - hm_low
    mean_x = integral_within_range(hist, hm_low, hm_high, moment=1)/\
        integral_within_range(hist, hm_low, hm_high)
    return_dict = {
        'peak' : max_y,
        'mean' : mean_x,
        'sigma' : fwhm / (2 * np.sqrt(2 * np.log(2)))
        }
    return return_dict

def extract_chip_channel_ids(filename, max_trans=None, verbose=False):
    la = LogAnalyzer(filename)
    chip_channel_ids = {}
    loop_data = {
        'n_trans': 0,
        'n_trans_cut': 0,
        'n_packets': 0,
        'n_packets_cut': 0
        }

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
        if not is_good_data(curr_trans):
            loop_data['n_trans_cut'] += 1
            continue
        loop_data['n_packets'] += len(curr_trans['packets'])
        for packet in curr_trans['packets']:
            if not is_good_packet(packet):
                loop_data['n_packets_cut'] += 1
                continue
            chip_id = str(packet.chipid)
            channel_id = str(packet.channel_id)
            try:
                chip_channel_ids[chip_id] += [channel_id]
            except KeyError:
                chip_channel_ids[chip_id] = [channel_id]
    print('')
    print(' N_transmissions: %4d, N_transmissions removed: %4d' % (
            loop_data['n_trans'], loop_data['n_trans_cut']))
    print(' N_packets: %4d, N_packets removed: %4d' % (
            loop_data['n_packets'], loop_data['n_packets_cut']))
    return chip_channel_ids
        

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
            chip_id = str(packet.chipid)
            channel_id = str(packet.channel_id)
            adc = packet.dataword
            try:
                hist = adc_dist[chip_id][channel_id]
                hist.Fill(adc)
            except KeyError:
                try:
                    bins = good_bins([], step=adc_step, min_v=adc_min, max_v=adc_max)
                    adc_dist[chip_id][channel_id] = ROOT.TH1F('c%s_ch%s_adc' % (chip_id,
                                                                                channel_id),
                                                              ';adc;count;', len(bins)-1,
                                                              bins)
                    adc_dist[chip_id][channel_id].Fill(adc)
                except KeyError:
                    # Entry for chip has not been created
                    bins = good_bins([], step=adc_step, min_v=adc_min, max_v=adc_max)
                    adc_dist[chip_id] = {
                        channel_id : ROOT.TH1F('c%s_ch%s_adc' % (chip_id, channel_id),
                                               ';adc;count', len(bins)-1, bins)
                        }
                    adc_dist[chip_id][channel_id].Fill(adc)
    print('')
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
                print('Calculating from c%s-ch%s adc dist' % (chipid, channelid))
            adc_peak_values = get_peak_values(adc_dist[chipid][channelid])
            try:
                pedestal_data[chipid][channelid] = {
                    'pedestal_adc': adc_peak_values['mean'],
                    'pedestal_adc_sigma': adc_peak_values['sigma']
                    }
            except KeyError:
                pedestal_data[chipid] = { channelid: {
                        'pedestal_adc': adc_peak_values['mean'],
                        'pedestal_adc_sigma': adc_peak_values['sigma']
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
                adc_hist = adc_dist[chipid][channelid]
                v_bins = np.array([adc_to_v(adc_hist.GetBinLowEdge(bin), vref, vcm)
                                   for bin in range(0, adc_hist.GetNbinsX()+2)], dtype=float)
                v_dist = ROOT.TH1F('c%s_ch%s_v' % (chipid, channelid),
                                   ';v;count', len(v_bins)-1, v_bins)
                for bin in range(0, adc_hist.GetNbinsX()+2):
                    v_dist.Fill(adc_to_v(adc_hist.GetBinCenter(bin), vref, vcm),
                                adc_hist.GetBinContent(bin))
                v_peak_values = get_peak_values(v_dist)
                pedestal_data[chipid][channelid]['pedestal_v'] = v_peak_values['mean']
                pedestal_data[chipid][channelid]['pedestal_v_sigma'] = v_peak_values['sigma']

    return pedestal_data

def do_gain_calibration(infile, vref=None, vcm=None, verbose=False):
    if vref is None or vcm is None:
        return {}
    gain_data = {}
    id_data = extract_chip_channel_ids(infile, verbose=verbose)
    for chip_id in id_data:
        for channel_id in id_data[chip_id]:
            gain_e = 1./250
            gain_v = adc_to_v(1, vref, vcm) - adc_to_v(0, vref, vcm)
            gain_vcm = adc_to_v(0, vref, vcm)
            try:
                gain_data[chip_id][channel_id] = {
                    'gain_v' : gain_v,
                    'gain_e' : gain_e,
                    'gain_vcm' : gain_vcm
                    }
            except KeyError:
                gain_data[chip_id] = { channel_id : {
                        'gain_v' : gain_v,
                        'gain_e' : gain_e,
                        'gain_vcm' : gain_vcm
                        }}
    return gain_data

