from larpix.serial_helpers.analyzers import LogAnalyzer
from helpers.lpx_convert import LpxAnalyzer
import larpix.larpix as larpix
from larpix.timestamp import Timestamp
import numpy as np
import argparse
import json
import sys
from os.path import splitext
from bitarray import bitarray

def get_analyzer(filename):
    '''
    Returns proper analyzer for file type
    '''
    ext = splitext(filename)[1]
    if ext == '.lpx':
        return LpxAnalyzer(filename)
    else:
        return LogAnalyzer(filename)

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
    if packet.packet_type != larpix.Packet.DATA_PACKET: return False
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
    nsteps = int((max_v - min_v) / float(step)) + 3
    bins = np.linspace(min_v-step, max_v+step, nsteps)
    return bins

def integral_within_range(hist, x_low, x_high, moment=0):
    '''
    Calculates the integral ``x^m * f(x) dx`` of the distribution within a range
    Assumes a uniform distribution within bins
    '''
    dist, bin_edges = hist
    sum = 0.
    low_bin = np.digitize(x_low, bin_edges)-1
    high_bin = np.digitize(x_high, bin_edges)-1
    if not high_bin == low_bin:
        dx = bin_edges[low_bin+1] - bin_edges[low_bin]
        sum += dist[low_bin] * (bin_edges[low_bin+1] - x_low) / dx * \
            ((bin_edges[low_bin+1] + x_low)/2)**moment
        dx = bin_edges[high_bin+1] - bin_edges[high_bin]
        sum += dist[high_bin] * (x_high - bin_edges[high_bin]) / dx * \
            ((bin_edges[high_bin] + x_high)/2)**moment
    else:
        dx = bin_edges[low_bin+1] - bin_edges[low_bin]
        sum += dist[low_bin] * (x_high - x_low) / dx * \
            ((x_high + x_low)/2)**moment
    for bin in range(low_bin+1,high_bin):
        sum += dist[bin] * ((bin_edges[bin+1] + bin_edges[bin])/2)**moment
    return sum

def find_fwhm(hist, max_bin):
    '''
    Returns the linear interpolated half max values above and below the specified bin
    '''
    dist, bin_edges = hist
    hm_bin_high = max_bin
    hm_bin_low = max_bin
    max = dist[max_bin]
    hm = max/2.
    while( hm_bin_high < len(bin_edges) and dist[hm_bin_high] > hm ):
        hm_bin_high += 1
    yp = [dist[hm_bin_high-1], dist[hm_bin_high]]
    xp = [(bin_edges[hm_bin_high-1] + bin_edges[hm_bin_high])/2,
          (bin_edges[hm_bin_high] + bin_edges[hm_bin_high+1])/2] # bin center
    hm_high = np.interp(hm, yp, xp)
    while( hm_bin_low > 0 and dist[hm_bin_low] > hm ):
        hm_bin_low -= 1
    yp = [dist[hm_bin_low], dist[hm_bin_low+1]]
    xp = [(bin_edges[hm_bin_low] + bin_edges[hm_bin_low+1])/2,
          (bin_edges[hm_bin_low+1] + bin_edges[hm_bin_low+2])/2] # bin center
    hm_low = np.interp(hm, yp, xp)
    return (hm_low, hm_high)

def get_peak_values(hist):
    '''
    Returns the peak value, the mean value within the fwhm of peak, and the sigma of the
    peak (calculated from fwhm)
    '''
    dist, bin_edges = hist
    max_bin = np.argmax(dist)
    max_x = bin_edges[max_bin]
    max_y = dist[max_bin]
    hm_low, hm_high = find_fwhm((dist, bin_edges), max_bin)
    fwhm = hm_high - hm_low
    mean_x = integral_within_range((dist, bin_edges), hm_low, hm_high, moment=1)/\
        integral_within_range((dist, bin_edges), hm_low, hm_high)
    return_dict = {
        'peak' : max_y,
        'mean' : mean_x,
        'sigma' : fwhm / (2 * np.sqrt(2 * np.log(2)))
        }
    return return_dict

def extract_chip_channel_ids(filename, max_trans=None, verbose=False):
    la = get_analyzer(filename)
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
                   loop_data['n_packets_cut']), end='')
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

def extract_chip_rel_timing(filename, verbose=False, max_trans=None):
    la = get_analyzer(filename)
    last_timestamp = {}
    rel_offset = {}
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
                   loop_data['n_packets_cut']), end='')
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
        prev_ns = None
        prev_chip_id = None
        for packet in curr_trans['packets']:
            if not is_good_packet(packet):
                loop_data['n_packets_cut'] += 1
                continue
            chip_id = str(packet.chipid)
            cpu_time = curr_trans['time']
            ref_time = None
            if chip_id in last_timestamp.keys():
                ref_time = last_timestamp[str(packet.chipid)]
            current_timestamp = Timestamp.from_packet(packet, cpu_time, ref_time)
            if len(last_timestamp.keys()) == 0:
                for chip in range(255):
                    last_timestamp[str(chip)] = current_timestamp
            else:
                last_timestamp[chip_id] = current_timestamp
            if prev_chip_id is None:
                prev_ns = current_timestamp.ns
                prev_chip_id = chip_id
                continue
            if chip_id != prev_chip_id:
                # two different chips in serial read almost simultaneous
                #   -> store time difference
                dt = prev_ns - current_timestamp.ns
                try:
                    rel_offset[chip_id][prev_chip_id] += [dt]
                except KeyError:
                    rel_offset[chip_id] = { prev_chip_id: [dt] }
            prev_chip_id = chip_id
            prev_ns = current_timestamp.ns
    print('')
    print(' N_transmissions: %4d, N_transmissions removed: %4d' % (
            loop_data['n_trans'], loop_data['n_trans_cut']))
    print(' N_packets: %4d, N_packets removed: %4d' % (
            loop_data['n_packets'], loop_data['n_packets_cut']))
    return rel_offset

def extract_pulsed_adc_dist(filename, adc_max=256, adc_min=0, adc_step=2, max_trans=None,
                            verbose=False):
    '''
    Extracts adc distributions for each chip and channel excluding hits from channels that
    were issued test pulses
    '''
    la = get_analyzer(filename)
    adc_dist = {}
    loop_data = {
        'n_trans': 0,
        'n_trans_cut': 0,
        'n_packets': 0,
        'n_packets_cut': 0
        }
    chips_silenced = True # cuts out all data before first write command (False removes data)
    chip_conf = {} # keep track of chip configuration commands sent
    pulsed_chip_channels = {} # keeps track of channels with test pulser enabled
    while True:
        curr_trans = la.next_transmission()
        if curr_trans is None: break
        if loop_data['n_trans'] == max_trans: break
        loop_data['n_trans'] += 1
        if verbose and loop_data['n_trans'] % 100 == 0:
            print('trans: %d, trans_cut: %d, packets: %d, packets_cut: %d\r' %
                  (loop_data['n_trans'], loop_data['n_trans_cut'], loop_data['n_packets'],
                   loop_data['n_packets_cut']), end='')
            sys.stdout.flush()
        if curr_trans['block_type'] is 'data' and curr_trans['data_type'] is 'write':
            chips_silenced = True # assumes first write is a silence command

            testpulse_conf_flag = False # marks if testpulse enable configuration has changed
            for packet_idx, packet in enumerate(curr_trans['packets']):
                if packet.packet_type == larpix.Packet.CONFIG_READ_PACKET:
                    continue
                # update configuration with new packets
                packet_dict = {packet.register_address: packet.register_data}
                try:
                    chip_conf[packet.chipid].from_dict_registers(packet_dict)
                except KeyError:
                    chip_conf[packet.chipid] = larpix.Configuration()
                    chip_conf[packet.chipid].from_dict_registers(packet_dict)

                if packet.register_address in larpix.Configuration.csa_testpulse_enable_addresses:
                    # change test pulse configuration
                    testpulse_conf_flag = True
                    pulsed_chip_channels = {} # reset pulsed channels
            if testpulse_conf_flag:
                for chipid, conf in chip_conf.items():
                    if any([value == 0 for value in conf.csa_testpulse_enable]):
                        pulsed_chip_channels[chipid] = [channel
                                                        for channel, value in enumerate(conf.csa_testpulse_enable)
                                                        if value == 0]
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
            if (packet.chipid in pulsed_chip_channels.keys() and
                packet.channel_id in pulsed_chip_channels[packet.chipid]):
                loop_data['n_packets_cut'] += 1
                continue
            chip_id = str(packet.chipid)
            channel_id = str(packet.channel_id)
            adc = packet.dataword
            try:
                hist, bins = adc_dist[chip_id][channel_id]
                try:
                    hist[np.digitize(adc, bins)-1] += 1
                except IndexError:
                    print('adc value %d from c%s-ch%s invalid' % (adc, chip_id, channel_id))
            except KeyError:
                try:
                    bins = good_bins([], step=adc_step, min_v=adc_min, max_v=adc_max)
                    adc_dist[chip_id][channel_id] = np.histogram([adc], bins)
                except KeyError:
                    # Entry for chip has not been created
                    bins = good_bins([], step=adc_step, min_v=adc_min, max_v=adc_max)
                    adc_dist[chip_id] = {
                        channel_id : np.histogram([adc], bins)
                        }
    print('')
    print(' N_transmissions: %4d, N_transmissions removed: %4d' % (
            loop_data['n_trans'], loop_data['n_trans_cut']))
    print(' N_packets: %4d, N_packets removed: %4d' % (
            loop_data['n_packets'], loop_data['n_packets_cut']))
    return adc_dist

def do_pedestal_calibration(infile, vref=None, vcm=None, verbose=False):
    adc_max = 257
    adc_min = -1
    adc_step = 2

    pedestal_data = {}

    # Get distributions of adc values
    if verbose:
        print('Begin pedestal calibration')
        print('Extracting data from %s' % infile)
    adc_dist = extract_pulsed_adc_dist(infile, adc_max, adc_min, adc_step, verbose=verbose)

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
                adc_hist, adc_bins = adc_dist[chipid][channelid]
                v_bins = np.array([adc_to_v(bin, vref, vcm) for bin in adc_bins],
                                  dtype=float)
                v_dist, v_bins = np.histogram([], v_bins)
                for bin_idx, bin in enumerate(adc_bins[:-1]):
                    v = adc_to_v(bin, vref, vcm)
                    v_dist[np.digitize(v, v_bins)-1] += adc_hist[bin_idx]
                v_peak_values = get_peak_values((v_dist, v_bins))
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
            gain_e = 250. # e/mv
            gain_v = adc_to_v(1, vref, vcm) - adc_to_v(0, vref, vcm) # v/adc
            gain_vcm = adc_to_v(0, vref, vcm) # v offset
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

def do_timing_calibration(infile, verbose=False):
    pass


