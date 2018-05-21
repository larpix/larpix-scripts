'''
Helper functions for keeping the default pathnames for larpix-scripts straight
'''

import time
import os
import larpix.larpix as larpix
import sys
import shutil

script_name = os.path.basename(os.path.splitext(sys.argv[0])[0])

def default_datadir(start_time):
    datadir = 'data/' + time.strftime('%Y_%m_%d', start_time) + '/'
    return datadir

def default_config_dir(start_time):
    config_dir = default_datadir(start_time) + 'default_config/'
    return config_dir

def default_config_file(start_time):
    config_file = default_config_dir(start_time) + 'default_config.json'
    return config_file

def make_default_config(start_time, config, force=False):
    mkdir_p(os.path.dirname(default_config_file(start_time)))
    if not force and os.path.isfile(default_config_file(start_time)):
        return default_config_file(start_time)
    c = larpix.Configuration()
    c.load(config)
    c.write(default_config_file(start_time), force=True)
    return default_config_file(start_time)

def default_board_file(start_time):
    board_file = default_config_dir(start_time) + 'default_chip_info.json'
    return board_file

def make_default_board(start_time, board_info_file, force=False):
    mkdir_p(os.path.dirname(default_board_file(start_time)))
    if not force and os.path.isfile(default_board_file(start_time)):
        return default_board_file(start_time)
    shutil.copy(board_info_file, default_board_file(start_time))
    return default_board_file(start_time)

def default_script_logdir(start_time):
    logdir = default_datadir(start_time) + script_name + '_' + \
        time.strftime('%Y_%m_%d_%H_%M_%S_%Z', start_time) + '/'
    return logdir

def default_script_logfile(start_time):
    logfile = default_script_logdir(start_time) + script_name + '_' + \
        time.strftime('%Y_%m_%d_%H_%M_%S_%Z', start_time) + '.log'
    return logfile

def default_data_logdir(start_time):
    logdir = default_datadir(start_time) + 'datalog/'
    return logdir

def default_data_logfile(start_time):
    logfile = default_data_logdir(start_time) + 'datalog_' + \
        time.strftime('%Y_%m_%d_%H_%M_%S_%Z') + '.dat'
    return logfile

def mkdir_p(path):
    '''shamelessly copied from http://stackoverflow.com/a/600612/190597 (tzot)'''
    try:
        os.makedirs(path, exist_ok=True)  # Python>3.2
    except TypeError:
        try:
            os.makedirs(path)
        except OSError as exc: # Python >2.5
            if os.path.isdir(path):
                pass
            else: raise
