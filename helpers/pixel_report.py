# Utilities to check pixel data

def pixel_check(packets):
    '''Examine the data returning from the pixels'''
    results = {}
    for pkt in packets:
        if pkt.packet_type != pkt.DATA_PACKET:
            continue
        chip_id = pkt.chipid
        chip_result = None
        if chip_id in results.keys():
            chip_result = results[chip_id]
        else:
            chip_result = {'chip_id': chip_id,
                           'bad_parity':0,
                           'fifo_half':0,
                           'fifo_full':0,
                           'n_hits': [0]*32,
                           'mean_adc':[0]*32}
            results[chip_id] = chip_result
        if not pkt.has_valid_parity():
            chip_result['bad_parity'] += 1
        if pkt.fifo_half_flag:
            chip_result['fifo_half'] += 1
        if pkt.fifo_full_flag:
            chip_result['fifo_full'] += 1
        chan_id = pkt.channel_id
        chip_result['n_hits'][chan_id] += 1
        chip_result['mean_adc'][chan_id] += pkt.dataword
    # Convert ADC sum to ADC mean
    for chip_id, result in list(results.items()):
        for chan_id in range(32):
            if result['n_hits'][chan_id] > 0:
                result['mean_adc'][chan_id] /= float(result['n_hits'][chan_id])
    return results

def print_pixel_report(results):
    '''Print the results the pixel check'''
    chip_ids = sorted(results.keys())
    print('ID bad_parity n_hits mean_adc fifo_half fifo_full')
    for chip_id in chip_ids:
        result = results[chip_id]
        print('Chip %d:  Total hits = %d  (bad_parity=%d fifo_half=%d fifo_full=%d)' % (
                chip_id,
                sum(result['n_hits']),
                result['bad_parity'],
                result['fifo_half'],
                result['fifo_full']))
        print('  chan n_hits mean_adc')
        for chan_id in range(32):
            if result['n_hits'][chan_id] == 0:
                # Skip quiet channels
                continue
            print('  %d %d %0.2f' % (chan_id,
                                     result['n_hits'][chan_id],
                                     result['mean_adc'][chan_id]))
    return

def pixel_report(packets):
    '''Run the pixel report'''
    results = pixel_check(packets)
    print_pixel_report(results)
    return results
