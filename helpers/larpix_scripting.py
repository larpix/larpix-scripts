import os
import json
import larpix.larpix as larpix
from helpers.logging import ScriptLogger
import time
import logging
log = logging.getLogger(__name__)

default_config_dir = ScriptLogger.default_datadir(time.time()) + \
    'default_config/'
default_config_filename = 'default_config.json'

def default_config():
    default_config = 'physics.json'
    if os.path.isfile(default_config_dir + default_config_filename):
        default_config = default_config_dir + default_config_filename
    return default_config

def clear_buffer_quick(controller, run_time=0.05):
    controller.run(run_time,'clear buffer (quick)')

def clear_buffer(controller, run_time=0.05, attempts=40):
    clear_buffer_attempts = attempts
    clear_buffer_quick(controller, run_time)
    while len(controller.reads[-1]) > 0 and clear_buffer_attempts > 0:
        clear_buffer_quick(controller, run_time)
        clear_buffer_attempts -= 1

def npackets_by_chip_channel(packets):
    npackets = {}
    for packet in packets:
        try:
            npackets[packet.chipid][packet.channel_id] += 1
        except KeyError:
            npackets[packet.chipid] = [0]*32
            npackets[packet.chipid][packet.channel_id] += 1
    return npackets

def npacket_by_channel(packets, chip_id):
    try:
        return npackets_by_chip_channel(packets)[chip_id]
    except KeyError:
        return [0]*32

def verify_chip_configuration(controller):
    clear_buffer(controller)
    config_ok, different_registers = controller.verify_configuration()
    if not config_ok:
        log.info('chip configurations were not verified - retrying')
        clear_buffer(controller)
        config_ok, different_registers = controller.verify_configuration()
        if not config_ok:
            log.warn('chip configurations could not be verified')
            log.warn('different registers: %s' % str(different_registers))
    return config_ok, different_registers

def load_board(controller, infile):
    chip_set = json.load(open(infile,'r'))
    for chip_info in chip_set['chip_set']:
        chip_id = chip_info[0]
        io_chain = chip_info[1]
        controller.chips.append(larpix.Chip(chip_id, io_chain))
    return chip_set['board']

def load_chip_configurations(controller, board, config_path, silence=False):
    if os.path.isfile(config_path) and \
            os.path.splitext(config_path)[1] == '.json':
        for chip in controller.chips:
            chip_identifier = (board, chip.io_chain, chip.chip_id)
            chip.config.load(config_path)
            controller.write_configuration(chip)
            if silence:
                controller.disable(chip_id=chip_id, io_chain=io_chain)
    elif os.path.isdir(config_path):
        for chip in controller.chips:
            chip_identifier = (board, chip.io_chain, chip.chip_id)
            try:
                chip.config.load(config_path + '/%s-%d-c%d_config.json' % \
                                     chip_identifier)
                log.info('%s-%d-c%d config loaded')
            except IOError as error:
                log.exception(error)
                log.warn('%s-%d-c%d config not found' % chip_identifier)
                log.info('loading %s' % default_config_filename)
                try:
                    chip.config.load(config_path + default_config_filename)
                except IOError as error:
                    log.exception(error)
                    log.error('no %s file found in %s' % 
                              (default_config_filename, config_path)
            controller.write_configuration(chip)
            if silence:
                controller.disable(chip_id=chip_id, io_chain=io_chain)
    else: raise IOError('specified configuration not found')
    return verify_chip_configuration(controller)
