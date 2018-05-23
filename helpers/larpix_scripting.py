import os
import json
import larpix.larpix as larpix
from helpers.script_logging import ScriptLogger
log = ScriptLogger.get_script_log()

def clear_buffer_quick(controller, run_time=0.05):
    '''Open serial comms for run_time seconds'''
    controller.run(run_time,'clear buffer (quick)')

def clear_buffer(controller, run_time=0.05, attempts=40):
    '''
    Ping serial comms until buffer is empty or until a number of attempts is reached,
    whichever is sooner.
    '''
    clear_buffer_attempts = attempts
    clear_buffer_quick(controller, run_time)
    while len(controller.reads[-1]) > 0 and clear_buffer_attempts > 0:
        clear_buffer_quick(controller, run_time)
        clear_buffer_attempts -= 1

def npackets_by_chip_channel(packets):
    '''Sort through packets, counting the number of packets from each chip id and channel.'''
    npackets = {}
    for packet in packets:
        try:
            npackets[packet.chipid][packet.channel_id] += 1
        except KeyError:
            npackets[packet.chipid] = [0]*32
            npackets[packet.chipid][packet.channel_id] += 1
    return npackets

def npackets_by_channel(packets, chip_id):
    '''
    Sort through packets, counting number of packets from each channel at matches chip_id.
    '''
    try:
        return npackets_by_chip_channel(packets)[chip_id]
    except KeyError:
        return [0]*32

def verify_chip_configuration(controller):
    '''Checks that configurations on physical chips matches those in controller.chips.'''
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

def enforce_chip_configuration(controller):
    '''
    Checks that configurations match those on physical chips.
    If not, attempt to reload configurations that do not match.
    '''
    max_attempts = 5
    attempt = 0
    clear_buffer(controller)
    config_ok, different_registers = verify_chip_configuration(controller)
    while not config_ok and attempt < max_attempts:
        attempt += 1
        log.info('enforcing chip configurations - attempt: %d' % attempt)
        for chip_id in different_registers:
            # FIX ME: this should both get chip io chain info
            # and write only to different registers
            chip = controller.get_chip(chip_id, 0)
            controller.write_configuration(chip)
        clear_buffer(controller)
        config_ok, different_registers = verify_chip_configuration(controller)
    if not config_ok:
        log.error('could not enforce configurations')
        log.info('different registers: %s' % str(different_registers))
    return config_ok, different_registers

def load_board(controller, infile):
    '''Loads the specified chipset .json file into configuration.chips'''
    chip_set = json.load(open(infile,'r'))
    for chip_info in chip_set['chip_set']:
        chip_id = chip_info[0]
        io_chain = chip_info[1]
        controller.chips.append(larpix.Chip(chip_id, io_chain))
    return chip_set['board']

def load_chip_configurations(controller, board, config_path, silence=False,
                             default_config=None):
    '''
    Disables chips, then loads specified configurations onto chips in reverse
    daisy chain order.
    `silence=True` to disable chips after loading configurations.
    `default_config` is the configuration to load if a chip specific file is not found
    and `config_path` is a directory.
    '''
    if os.path.isfile(config_path) and \
            os.path.splitext(config_path)[1] == '.json':
        controller.disable()
        for chip in reversed(controller.chips):
            chip_identifier = (board, chip.io_chain, chip.chip_id)
            chip.config.load(config_path)
            controller.write_configuration(chip)
            if silence:
                controller.disable(chip_id=chip.chip_id, io_chain=chip.io_chain)
    elif os.path.isdir(config_path):
        controller.disable()
        for chip in reversed(controller.chips):
            chip_identifier = (board, chip.io_chain, chip.chip_id)
            try:
                chip.config.load(config_path + '/%s-%d-c%d_config.json' % \
                                     chip_identifier)
                log.info('%s-%d-c%d config loaded' % chip_identifier)
            except IOError as error:
                #log.warn('%s-%d-c%d config not found' % chip_identifier)
                if not default_config is None:
                    #log.info('loading %s' % default_config)
                    try:
                        chip.config.load(default_config)
                        log.info(('%s-%d-c%d default config '+default_config+' loaded') % 
                                 chip_identifier)
                    except IOError as error:
                        log.exception(error)
                        log.error('%s-%d-c%d no default config found!' % chip_identifier)
                else:
                    log.info('disabling %s-%d-c%d' % chip_identifier)
                    controller.disable(chip_id=chip.chip_id, io_chain=chip.io_chain)
            controller.write_configuration(chip)
            if silence:
                controller.disable(chip_id=chip.chip_id, io_chain=chip.io_chain)
    else: raise IOError('specified configuration not found')
    return enforce_chip_configuration(controller)
