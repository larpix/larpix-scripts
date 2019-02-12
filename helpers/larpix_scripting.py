import os
import json
import time
import larpix.larpix as larpix
from helpers.script_logging import ScriptLogger
log = ScriptLogger.get_script_log()

def clear_stored_packets(controller):
    for chip in controller.chips:
        chip.reads = []
    controller.reads = []

def clear_buffer_quick(controller, run_time=0.05):
    '''Open serial comms for run_time seconds'''
    controller.run(run_time,'clear buffer (quick)')

# def clear_buffer(controller, run_time=0.05, attempts=40):
    # '''
    # Ping serial comms until buffer is empty or until a number of attempts is reached,
    # whichever is sooner.
    # '''
    # clear_buffer_attempts = attempts
    # clear_buffer_quick(controller, run_time)
    # while len(controller.reads[-1]) > 0 and clear_buffer_attempts > 0:
        # clear_buffer_quick(controller, run_time)
        # clear_buffer_attempts -= 1

def clear_buffer(controller, delay=0.05):
    '''
    Empty the queue after a given delay.

    '''
    controller.start_listening()
    controller.read()
    time.sleep(delay)
    controller.read()
    controller.stop_listening()


def temp_store_config(chip):
    ''' Save chip configuration to a hidden configuration file '''
    temp_filename = '.config_%s.json' % time.strftime('%Y_%m_%d_%H_%M_%S',time.localtime())
    log.info('storing chip {} configuration in temp file {}'.format(chip.chip_id,
                                                                    temp_filename))
    chip.config.write(temp_filename, force=True)
    return temp_filename

def load_temp_file(controller, chip, filename):
    '''
    Load chip conf from a hidden configuration file and write to chip. Deletes hidden file
    when complete
    '''
    log.info('loading chip {} configuration from temp file {}'.format(chip.chip_id,
                                                                      filename))
    controller.disable(chip_id=chip.chip_id)
    chip.config.load(filename)
    controller.write_configuration(chip)
    config_ok, different_registers = verify_chip_configuration(controller,
                                                               chip_id=chip.chip_id)
    if config_ok:
        os.remove(filename)
    else:
        log.warn('chip configuration failed - prior state stored in {}'.format(filename))
    return config_ok, different_registers

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

def verify_chip_configuration(controller, chip_id=None):
    '''Checks that configurations on physical chips matches those in controller.chips.'''
    clear_buffer(controller)
    config_ok, different_registers = controller.verify_configuration(chip_id=chip_id)
    if not config_ok:
        log.info('chip configurations were not verified - retrying')
        clear_buffer(controller)
        config_ok, different_registers = controller.verify_configuration(chip_id=chip_id)
        if not config_ok:
            log.warn('chip configurations could not be verified')
            log.warn('different registers: %s' % str(different_registers))
    return config_ok, different_registers

def enforce_chip_configuration(controller):
    '''
    Checks that configurations match those on physical chips.
    If not, attempt to reload configurations that do not match.
    '''
    error_flag = False
    max_attempts = 5
    clear_buffer(controller)
    config_ok, different_registers = verify_chip_configuration(controller)
    if not config_ok:
        for chip_id in different_registers:
            config_ok = False
            attempt = 0
            while not config_ok and attempt < max_attempts:
                attempt += 1
                log.info('enforcing chip %d configuration - attempt: %d' % (chip_id, attempt))
                # FIX ME: this should both get chip io chain info
                # and write only to different registers
                chip = controller.get_chip(chip_id, 0)
                controller.write_configuration(chip)
                clear_buffer(controller)
                config_ok = verify_chip_configuration(controller,
                                                      chip_id=chip_id)[0]
            if not config_ok:
                log.error('could not enforce configuration on chip %d' % chip_id)
                error_flag = True
    if error_flag:
        log.error('Not all chip configurations were successful')
        config_ok, different_registers = verify_chip_configuration(controller)
        log.error('Different registers: %s' % str(different_registers))
    return config_ok, different_registers

def load_board(controller, infile):
    '''Loads the specified chipset .json file into configuration.chips'''
    chip_set = json.load(open(infile,'r'))
    for chip_info in chip_set['chip_set']:
        chip_id = chip_info[0]
        io_chain = chip_info[1]
        controller.chips.append(larpix.Chip(chip_id, io_chain))
    return chip_set['board']

def store_chip_configurations(controller, board_info, outdir, force=False):
    '''
    Stores chip configurations in specified directory
    '''
    config = larpix.Configuration()
    for chip in controller.chips:
        config.from_dict(chip.config.to_dict())
        configuration_file = outdir + '/%s-%d-c%d_config.json' % (board_info, chip.io_chain, chip.chip_id)
        config.write(configuration_file, force=force)
        log.info('configuration saved to ' + configuration_file)

def load_chip_configurations(controller, board, config_path, silence=False,
                             default_config=None, threshold_correction=0,
                             trim_correction=0):
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
            chip.config.global_threshold += threshold_correction
            for channel in range(32):
                if (chip.config.pixel_trim_thresholds[channel] + trim_correction
                    <= 31):
                    chip.config.pixel_trim_thresholds[channel] += trim_correction
                else:
                    chip.config.pixel_trim_thresholds[channel] = 31
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
            chip.config.global_threshold += threshold_correction
            for channel in range(32):
                if (chip.config.pixel_trim_thresholds[channel] + trim_correction
                    <= 31):
                    chip.config.pixel_trim_thresholds[channel] += trim_correction
                else:
                    chip.config.pixel_trim_thresholds[channel] = 31
            controller.write_configuration(chip)
            if silence:
                controller.disable(chip_id=chip.chip_id, io_chain=chip.io_chain)
    else: raise IOError('specified configuration not found')
    return verify_chip_configuration(controller)
    #return enforce_chip_configuration(controller)
