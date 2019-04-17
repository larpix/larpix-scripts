'''
A helper library for plotting test results
There is one plot_XXXX for each standard larpix test

'''
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import (AutoMinorLocator, MultipleLocator)
import numpy as np

AXIS_FORMAT_CHIP_SIZE = 33
MAX_ADC_VALUE = 255
MAX_PULSE_AMP = 10
MAX_EFFICIENCY = 1.0
plt.ion()

def format_for_chip_idx(value, tick_number):
    '''
    value should be chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id

    '''
    chip_idx = int(value // AXIS_FORMAT_CHIP_SIZE)
    return '\nChip {}'.format(chip_idx)

def format_for_channel_ids(value, tick_number):
    '''
    value should be chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id

    '''
    channel = int(value % AXIS_FORMAT_CHIP_SIZE)
    return '{}'.format(channel)


def save_figure(fig, filename):
    '''
    Saves the figure at `filename`

    '''
    plt.figure(fig.number)
    plt.savefig(filename, bbox_inches="tight")

def plot_leakage(results, figure_title='Leakage rate'):
    '''
    Plots leakage current across chips
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel id, ...], [leakage trigger packets, ...], [leakage runtime]),
        ...
    ]
    Errors are statistical only - [sqrt(npackets)]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'trigger_packets': 4,
        'runtime': 5
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    for chip_idx in range(n_chips):
        unique_channel_id = [chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id for channel_id in results[chip_idx][chip_results_idx['channel_id']]]
        leakage_packets = results[chip_idx][chip_results_idx['trigger_packets']]
        leakage_runtime = results[chip_idx][chip_results_idx['runtime']]
        leakage_rate = [leakage_packets[i] / leakage_runtime[i] for i in range(len(leakage_packets))]
        leakage_err = [np.sqrt(max(leakage_packets[i],1)) / leakage_runtime[i] for i in range(len(leakage_packets))]
        plt.errorbar(unique_channel_id, leakage_rate, leakage_err, fmt='.', label='Chip id: {}, IO chain: {}'.format(results[chip_idx][chip_results_idx['chip_id']], results[chip_idx][chip_results_idx['io_chain']]))

    leg = ax.legend(ncol=max(int(np.sqrt(n_chips)),1))
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Channel')
    ax.set_ylabel('Rate [Hz]')
    ax.set_yscale('log')

    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_for_channel_ids))

    return fig, ax

def plot_leakage_hist(results, figure_title='Leakage rate distribution', label='_nolegend_'):
    '''
    Plots histogram of leakage current across chips
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel id, ...], [leakage trigger packets, ...], [leakage runtime]),
        ...
    ]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'trigger_packets': 4,
        'runtime': 5
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    hist_leakage = []
    for chip_idx in range(n_chips):
        leakage_packets = results[chip_idx][chip_results_idx['trigger_packets']]
        leakage_runtime = results[chip_idx][chip_results_idx['runtime']]
        hist_leakage += [leakage_packets[i] / leakage_runtime[i] for i in range(len(leakage_packets))]

    min_leakage = 1./max(leakage_runtime)
    bins = [leakage + min_leakage for leakage in set(hist_leakage)]
    bins += [leakage - min_leakage for leakage in set(hist_leakage)]
    plt.hist(hist_leakage, alpha=1.0, label=label, bins=sorted(list(set(bins))))
    leg = ax.legend(ncol=max(int(np.sqrt(n_chips)),1))
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Rate [Hz]')
    ax.set_xscale('log')
    ax.set_ylabel('Channel count')

    return fig, ax

def plot_pedestal_width(results, figure_title='ADC profile'):
    '''
    Plots adc mean and rms across channels
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[adc values] ...])
    ]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'adc_value': 4
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    for chip_idx in range(n_chips):
        unique_channel_id = [chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id for channel_id in results[chip_idx][chip_results_idx['channel_id']]]
        adc_values = results[chip_idx][chip_results_idx['adc_value']]
        adc_mean = [np.mean(adcs) for adcs in adc_values if len(adcs) > 0]
        adc_rms = [np.std(adcs) for adcs in adc_values if len(adcs) > 0]

        plot_channel_ids = [channel_id for idx, channel_id in enumerate(unique_channel_id) if len(adc_values[idx]) > 0]
        plot_adc_mean = adc_mean
        plot_adc_err = adc_rms
        plt.errorbar(plot_channel_ids, plot_adc_mean, plot_adc_err, fmt='.', label='Chip {}, IO chain {}'.format(results[chip_idx][chip_results_idx['chip_id']], results[chip_idx][chip_results_idx['io_chain']]), alpha=0.5)

    leg = ax.legend(ncol=max(int(np.sqrt(n_chips)),1), loc=8)
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Channel')
    ax.set_ylabel('ADC')

    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_for_channel_ids))

    return fig, ax

def plot_pedestal_width_hist2d(results, figure_title='ADC distribution'):
    '''
    Plots histogram of adc distributions across all channels
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[adc values] ...])
    ]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'adc_value': 4
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    hist_adc_values = []
    hist_channel_ids = []
    for chip_idx in range(n_chips):
        unique_channel_id = [chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id for channel_id in results[chip_idx][chip_results_idx['channel_id']]]
        adc_values = results[chip_idx][chip_results_idx['adc_value']]
        adc_mean = [np.mean(adcs) for adcs in adc_values if len(adcs) > 0]
        adc_rms = [np.std(adcs) for adcs in adc_values if len(adcs) > 0]

        for i in range(len(unique_channel_id)):
            if len(adc_values[i]) > 0:
                hist_adc_values += adc_values[i]
                hist_channel_ids += [unique_channel_id[i]] * len(adc_values[i])

    x_bins = np.linspace(-0.5, n_chips * AXIS_FORMAT_CHIP_SIZE - 0.5, n_chips * AXIS_FORMAT_CHIP_SIZE+1)
    y_bins = np.linspace(-0.5, MAX_ADC_VALUE + 0.5, (MAX_ADC_VALUE+2)//2)
    plt.hist2d(hist_channel_ids, hist_adc_values, bins=[x_bins, y_bins], alpha=1.0,
        label='_nolegend_', cmin=1e-6)#, norm=LogNorm())
    cb = plt.colorbar()
    #leg = ax.legend(ncol=max(int(np.sqrt(n_chips)),1), loc=8)
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Channel')
    ax.set_ylabel('ADC')

    ax.xaxis.set_major_locator(MultipleLocator(AXIS_FORMAT_CHIP_SIZE))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_for_chip_idx))
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.xaxis.set_minor_formatter(plt.FuncFormatter(format_for_channel_ids))

    return fig, ax

def plot_pedestal_width_mean_hist(results, figure_title='Pedestal mean', label='_nolegend_'):
    '''
    Plots histogram of pedestal mean across channels into a single histogram
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[adc values] ...])
    ]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'adc_value': 4
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    hist_adc_mean = []
    for chip_idx in range(n_chips):
        adc_values = results[chip_idx][chip_results_idx['adc_value']]
        adc_mean = [np.mean(adcs) for adcs in adc_values if len(adcs) > 0]
        hist_adc_mean += adc_mean

    max_adc = max(hist_adc_mean)
    min_adc = min(hist_adc_mean)
    adc_step = (max_adc - min_adc)/np.sqrt(len(hist_adc_mean))
    bins = np.linspace(min_adc-adc_step/2,  max_adc + adc_step/2, int((max_adc-min_adc)/adc_step)+2)
    plt.hist(hist_adc_mean, alpha=1.0, label=label, bins=bins)
    leg = ax.legend()
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Mean ADC')
    ax.set_ylabel('Channel count')

    return fig, ax

def plot_pedestal_width_rms_hist(results, figure_title='Pedestal width', label='_nolegend_'):
    '''
    Plots histogram of pedestal rms across channels into a single histogram
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[adc values] ...])
    ]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'adc_value': 4
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    hist_adc_rms = []
    for chip_idx in range(n_chips):
        adc_values = results[chip_idx][chip_results_idx['adc_value']]
        adc_rms = [np.std(adcs) for adcs in adc_values if len(adcs) > 0]
        hist_adc_rms += adc_rms

    max_adc = max(hist_adc_rms)
    adc_step = min(max_adc/np.sqrt(len(hist_adc_rms)), 1.)
    bins = np.linspace(-adc_step/2,  max_adc + adc_step/2, int(max_adc/adc_step)+2)
    plt.hist(hist_adc_rms, alpha=1.0, label=label, bins=bins)
    leg = ax.legend()
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('RMS ADC')
    ax.set_ylabel('Channel count')

    return fig, ax

def plot_trigger_threshold(results, figure_title='Trigger threshold'):
    '''
    Plots trigger threshold for each channel
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[injected amplitude] ...], [[n_triggers] ...], [[n pulses] ...])
    ]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'inj_ampl': 4,
        'n_triggers': 5,
        'n_inj_pulses': 6
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    for chip_idx in range(n_chips):
        unique_channel_id = [chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id for channel_id in results[chip_idx][chip_results_idx['channel_id']]]
        inj_ampls = results[chip_idx][chip_results_idx['inj_ampl']]
        n_triggers = results[chip_idx][chip_results_idx['n_triggers']]
        n_inj_pulses = results[chip_idx][chip_results_idx['n_inj_pulses']]

        plot_channel_ids = [channel_id for idx, channel_id in enumerate(unique_channel_id) if any([n_inj_pulses[idx][j] <= n_triggers[idx][j] for j in range(len(inj_ampls[idx]))])]
        plot_min_ampl = [inj_ampls[i][j] for i in range(len(inj_ampls)) for j in range(len(inj_ampls[i])) if n_inj_pulses[i][j] <= n_triggers[i][j]]
        plt.plot(plot_channel_ids, plot_min_ampl, marker='d', linestyle='', label='Chip {}, IO chain {}'.format(results[chip_idx][chip_results_idx['chip_id']], results[chip_idx][chip_results_idx['io_chain']]), alpha=0.5)

    leg = ax.legend(ncol=max(int(np.sqrt(n_chips)),1), loc=8)
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Channel')
    ax.set_ylabel('Injected pulse amplitude [DAC]')

    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_for_channel_ids))

    return fig, ax

def plot_trigger_threshold_hist2d(results, figure_title='Trigger threshold and efficiency'):
    '''
    Plots trigger efficiency for each channel in a 2d histogram
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[injected amplitude] ...], [[n_triggers] ...], [[n pulses] ...])
    ]

    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'inj_ampl': 4,
        'n_triggers': 5,
        'n_inj_pulses': 6
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    hist_ampl_values = []
    hist_ampl_weights = []
    hist_channel_ids = []
    for chip_idx in range(n_chips):
        unique_channel_id = [chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id for channel_id in results[chip_idx][chip_results_idx['channel_id']]]
        inj_ampls = results[chip_idx][chip_results_idx['inj_ampl']]
        n_triggers = results[chip_idx][chip_results_idx['n_triggers']]
        n_inj_pulses = results[chip_idx][chip_results_idx['n_inj_pulses']]

        for i in range(len(unique_channel_id)):
            for j in range(len(inj_ampls[i])):
                hist_ampl_weights += [n_triggers[i][j] / n_inj_pulses[i][j]]
                hist_ampl_values += [inj_ampls[i][j]]
                hist_channel_ids += [unique_channel_id[i]]

    x_bins = np.linspace(-0.5, n_chips * AXIS_FORMAT_CHIP_SIZE - 0.5, n_chips * AXIS_FORMAT_CHIP_SIZE+1)
    y_bins = np.linspace(-0.5, MAX_PULSE_AMP + 0.5, (MAX_PULSE_AMP+2))
    hist = plt.hist2d(hist_channel_ids, hist_ampl_values, weights=hist_ampl_weights, bins=[x_bins, y_bins], alpha=1.0, label='_nolegend_', cmin=1e-6, vmax=MAX_EFFICIENCY)
    cb = plt.colorbar()
    cb.set_label("Trigger efficiency")
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Channel')
    ax.set_ylabel('Injected pulse amplitude [DAC]')

    ax.xaxis.set_major_locator(MultipleLocator(AXIS_FORMAT_CHIP_SIZE))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_for_chip_idx))
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.xaxis.set_minor_formatter(plt.FuncFormatter(format_for_channel_ids))

    return fig, ax

def plot_cumulative_response(results, figure_title='Trigger threshold', label='_nolegend_'):
    '''
    Plots the number of responding channels weighted by their trigger efficiency at each pulse amplitude
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[injected amplitude] ...], [[n_triggers] ...], [[n pulses] ...])
    ]
    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'inj_ampl': 4,
        'n_triggers': 5,
        'n_inj_pulses': 6
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    hist_ampl_values = []
    hist_ampl_weights = []
    all_inj_ampl = sorted(list(set([inj_pulse for chip_result in results
        for inj_pulse_list in chip_result[chip_results_idx['inj_ampl']]
        for inj_pulse in inj_pulse_list])))
    for chip_idx in range(n_chips):
        unique_channel_id = [chip_idx * AXIS_FORMAT_CHIP_SIZE + channel_id for channel_id in results[chip_idx][chip_results_idx['channel_id']]]
        inj_ampls = results[chip_idx][chip_results_idx['inj_ampl']]
        n_triggers = results[chip_idx][chip_results_idx['n_triggers']]
        n_inj_pulses = results[chip_idx][chip_results_idx['n_inj_pulses']]

        for i in range(len(unique_channel_id)):
            for j,ampl in enumerate(range(len(all_inj_ampl))):
                try:
                    hist_ampl_weights += [min(n_triggers[i][j] / n_inj_pulses[i][j], 1.)/len(unique_channel_id)/n_chips]
                    hist_ampl_values += [inj_ampls[i][j]]
                except IndexError:
                    hist_ampl_weights += [1./len(unique_channel_id)/n_chips]
                    hist_ampl_values += [all_inj_ampl[j]]

    bins = np.linspace(-0.5, MAX_PULSE_AMP + 0.5, (MAX_PULSE_AMP+2))
    plt.hist(hist_ampl_values, weights=hist_ampl_weights, bins=bins, alpha=1.0,
        label=label)
    leg = ax.legend()
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Injected pulse amp. [DAC]')
    ax.set_ylabel('Effective efficiency')

    return fig, ax


def plot_trigger_threshold_hist(results, figure_title='Trigger threshold', label='_nolegend_'):
    '''
    Plots trigger threshold for each channel in a histogram
    Expects results to be formatted as
    [
        (chip_idx, chip_id, io_chain, [channel_id], [[injected amplitude] ...], [[n_triggers] ...], [[n pulses] ...])
    ]
    '''
    chip_results_idx = {
        'chip_idx': 0,
        'chip_id': 1,
        'io_chain': 2,
        'channel_id': 3,
        'inj_ampl': 4,
        'n_triggers': 5,
        'n_inj_pulses': 6
    }
    n_chips = len(results)
    fig = plt.figure(figure_title)
    ax = fig.add_subplot(111)
    hist_min_ampl = []
    for chip_idx in range(n_chips):
        inj_ampls = results[chip_idx][chip_results_idx['inj_ampl']]
        n_triggers = results[chip_idx][chip_results_idx['n_triggers']]
        n_inj_pulses = results[chip_idx][chip_results_idx['n_inj_pulses']]

        hist_min_ampl += [inj_ampls[i][j] for i in range(len(inj_ampls)) for j in range(len(inj_ampls[i])) if n_inj_pulses[i][j] <= n_triggers[i][j]]

    bins = np.linspace(-0.5, MAX_PULSE_AMP + 0.5, (MAX_PULSE_AMP+2))
    plt.hist(hist_min_ampl, bins=bins, alpha=1.0, label=label)
    leg = ax.legend()
    ax.grid(True, linestyle='--', linewidth=1)
    ax.axis(option='auto')
    ax.set_frame_on(True)
    ax.set_xlabel('Minimum injected pulse amplitude [DAC]')
    ax.set_ylabel('Channel count')

    return fig, ax












