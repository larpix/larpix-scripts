import larpix.larpix as larpix
from larpix.serialport import SerialPort
from bitarray import bitarray
import numpy as np

def extract_lpx_data(word):
    '''
    Parse the raw bytes from Igor's file .lpx file
    returns timestamp, packet_bytes
    '''
    bits = bitarray(endian='little')
    bits.frombytes(word)
    timestamp_bits = bits[54:64]
    packet_bits = bits[0:54]
    timestamp_bits.reverse()
    timestamp = int(timestamp_bits.to01(),2)
    packet_bytes = bits[0:54].tobytes()
    return timestamp, packet_bytes

def fix_lpx_timestamp_rollover(time, ref, time_nbit=10, late_packet_window=10):
    '''
    Corrects for rollovers in the `time_nbit`-bit timestamp `time`
    resulting in an relative timestamp within run
    Works as long as `ref` is known to be <2**`time_nbit`-`late_packet_window` seconds before time
    If `ref` - `time` is < `late_packet_window` it is assumed that this packet is out of order and
    returns -1
    '''
    rollover_dt = 2**time_nbit
    n_rollovers = 0
    if ref-time > 0:
        # skip non-sequential packets
        if (ref - time)%rollover_dt < late_packet_window and abs((ref-time)%rollover_dt) > 0:
            return -1
        n_rollovers = np.ceil(max(float(ref - time) / (rollover_dt),0))
    fixed_time = n_rollovers * rollover_dt + time
    return fixed_time

class LpxLoader:
    '''
    A dummy class to make DataLoader-like read blocks from .lpx data
    '''
    nbytes_word = 8

    def __init__(self, filename, t0=0):
        '''
        Reads from `filename`
        `t0` sets the t0 for the run (since .lpx data only has a 10b timestamp)
        '''
        self.file = open(filename,'rb')
        self.prev_timestamp = t0

    def close(self):
        '''
        Closes file nicely
        '''
        self.file.close()
        self.file = None

    def next_block(self):
        '''
        Reads next word from data file and formats as though it was from Dan's .dat file format
        '''
        bytes = self.file.read(self.nbytes_word)
        if bytes:
            timestamp, packet_bytes = extract_lpx_data(bytes)
            fixed_timestamp = fix_lpx_timestamp_rollover(time=timestamp, ref=self.prev_timestamp)
            #if fixed_timestamp == -1:
            #    print(timestamp, self.prev_timestamp, fixed_timestamp)
            if fixed_timestamp >= 0:
                self.prev_timestamp = fixed_timestamp
            faux_block = {'block_type':'data',
                          'data_type':'read',
                          'data':(SerialPort.start_byte + packet_bytes + b'\x00' +
                                  SerialPort.stop_byte),
                          'lpx_packet_bytes': packet_bytes,
                          'time':fixed_timestamp
                          }
            return faux_block
        return None

class LpxAnalyzer:
    '''
    A dummy class to make LogAnalyzer-like read blocks from .lpx data
    '''
    def __init__(self, filename, t0=0):
        '''
        Reads from `filename`
        `t0` sets the t0 for the run (since .lpx data only has a 10b timestamp
        '''
        self.loader = LpxLoader(filename=filename,t0=t0)

    def close(self):
        '''
        Closes file nicely
        '''
        self.loader.close()

    def next_transmission(self):
        faux_block = self.loader.next_block()
        if not faux_block is None:
            faux_block['packets'] = [larpix.Packet(bytestream=faux_block['lpx_packet_bytes'])]
        return faux_block
