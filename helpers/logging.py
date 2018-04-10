'''
A basic class for handling the log files generated by larpix-scripts
Typical usage:
``
sl = ScriptLogger(<script_name>)
log = sl.script_log
log.info(<message>) # print something to script log + stdout
sl.flush_datalog() # store current serial data to file
``
'''

import logging
import time
import sys
import os
import larpix

def mkdir_p(path):
    '''http://stackoverflow.com/a/600612/190597 (tzot)'''
    try:
        os.makedirs(path, exist_ok=True)  # Python>3.2
    except TypeError:
        try:
            os.makedirs(path)
        except OSError as exc: # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else: raise

class MakeFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=0):            
        mkdir_p(os.path.dirname(filename))
        logging.FileHandler.__init__(self, filename, mode, encoding, delay)

class ScriptLogger(class):
    script_logging_format = '%(asctime)s %(levelname)s: %(message)s')
    script_log_level = logging.DEBUG

    def __init__(script_name, script_logfile=None, data_logfile=None):
        self.start_time = time.time()
        if script_logfile is None:
            self.script_logdir = self.default_script_logdir(script_name, \
                                                           self.start_time)
            self.script_logfile = script_logdir + self.default_script_logfile(\
            script_name, self.start_time)
        if data_logfile is None:
            self.data_logdir = self.default_data_logdir(self.start_time)
            self.data_logfile = data_logdir + self.default_data_logfile(\
            self.start_time)

        self.init_script_logging()
        self.script_log.setLevel(self.script_log_level)
        self.script_log.info('initialized script logger')
        self.script_log.info('logging to %s' % self.script_logfile)

        self.init_data_logging()
        self.script_log.info('initialized data logger')
        self.script_log.info('storing data to %s' % self.data_logfile)

    def init_script_logging():
        self.script_log = logging.getLogger(__name__)
        self.script_log_fhandler = logging.FileHandler(self.script_logfile)
        self.script_log_shandler = logging.StreamHandler(sys.stdout)
        self.script_log_formatter = logging.Formatter(\
        self.script_logging_format)
        self.log.addHandler(self.script_log_fhandler)
        self.log.addHandler(self.script_log_shandler)

    def init_data_logging():
        self.enable_datalog()

    def default_datadir(start_time):
        datadir = 'data/' + time.strftime('%Y_%m_%d', start_time) + '/'
        return datadir

    def default_script_logdir(script_name, start_time):
        logdir = self.default_datadir(start_time) + script_name + '_' + \
            time.strftime('%Y_%m_%d_%H_%M_%S', start_time) + '/'
        return logdir

    def default_script_logfile(script_name, start_time):
        logfile = script_name + '_' + \
            time.strftime('%Y_%m_%d_%H_%M_%S', start_time) + '.log'
        return

    def default_data_logdir(start_time):
        logdir = self.default_datadir(start_time) + 'datalog/'
        return logdir

    def default_data_logfile(start_time):
        logfile = 'datalog_' + time.strftime('%Y_%m_%d_%H_%M_%S_%Z') + '.dat'
        return logfile

    def enable_datalog(filename=None):
        if filename is None:
            logfile = self.data_logfile
        else:
            self.data_logfile = filename
        return larpix.enable_logger(self.data_logfile)

    def flush_datalog():
        return larpix.flush_logger()

    def disable_datalog():
        return larpix.disable_logger()
