#!//usr/bin/env python3
# Copyright (C) 2017 Tom Marek <tm.tomas.marek@gmail.com>
#
# Thanks to: 
#    http://code.activestate.com/recipes/439093-get-names-of-all-up-network-interfaces-linux-only/
#
#------------------------------------------------------------------------
# TODO: maybe add total up/download

import array
import fcntl
import os
import re
import socket
import subprocess
import struct
import sys
import time

from argparse import ArgumentParser


colours = {
    'green': '#00FF00',
    'orange': '#FF8000',
    'red': '#FF0000',
}


def all_interfaces():
    is_64bits = sys.maxsize > 2**32
    struct_size = 40 if is_64bits else 32
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    max_possible = 8 # initial value

    while True:
        _bytes = max_possible * struct_size
        names = array.array('B')
        for i in range(0, _bytes):
            names.append(0)
        outbytes = struct.unpack('iL', fcntl.ioctl(
            s.fileno(),
            0x8912,  # SIOCGIFCONF
            struct.pack('iL', _bytes, names.buffer_info()[0])
        ))[0]
        if outbytes == _bytes:
            max_possible *= 2
        else:
            break
    namestr = names.tostring()
    ifaces = []
    for i in range(0, outbytes, struct_size):
        iface_name = bytes.decode(namestr[i:i+16]).split('\0', 1)[0]
        iface_addr = socket.inet_ntoa(namestr[i+20:i+24])
        ifaces.append((iface_name, iface_addr))

    return ifaces

def get_default_route():
    with open('/proc/net/route', 'r') as f:
        for line in f:
            fields = line.strip().split()
            if fields[1] == '00000000' and int(fields[3], 16) & 2:
                return fields[0], socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))

def get_iface_type(iface_name):
    with open('/sys/class/net/%s/type' % iface_name, 'r') as f:
        return f.readline().rstrip()

def get_iface_operstate(iface_name):
    with open('/sys/class/net/%s/operstate' % iface_name, 'r') as f:
        operstate = f.readline().rstrip()

        if operstate == 'up':
            colour = colours['green']
        elif operstate == 'down':
            colour = colours['red']
        else:
            colour = colours['orange']

        return operstate, colour

def get_iface_bandwith(iface_name):
    iface_file_path = '/dev/shm/networking-%s' % iface_name

    # get current time
    current_time = int(round(time.time()))
    # get data from interface
    with open('/sys/class/net/%s/statistics/rx_bytes' % iface_name, 'r') as f:
        rx = int(f.readline().rstrip())
    with open('/sys/class/net/%s/statistics/tx_bytes' % iface_name, 'r') as f:
        tx = int(f.readline().rstrip())

    if not os.path.isfile(iface_file_path):
        with open(iface_file_path, 'w') as f:
            f.write('%d,%d,%d' % (current_time, rx, tx))
            old_time, old_rx, old_tx = current_time, rx, tx

    with open(iface_file_path, 'r') as f:
        old_time, old_rx, old_tx = f.readline().rstrip().split(',')
    with open(iface_file_path, 'w') as f:
        f.write('%d,%d,%d' % (current_time, rx, tx))

    time_delta = current_time - int(old_time) or 1

    rx_delta = rx - int(old_rx)
    tx_delta = tx - int(old_tx)

    rx_Bps = rx_delta / float(time_delta)
    tx_Bps = tx_delta / float(time_delta)

    return (rx_Bps, tx_Bps, rx, tx)

def get_wireless_info(iface):
    if not os.path.isdir('/sys/class/net/%s/wireless' % iface):
        return None

    with open('/proc/net/wireless', 'r') as f:
        for line in f:
            fields = re.sub(r'([^\s\w]|_)+', '', line).split()
            if iface in fields:
                signal = (float(fields[2]) * 100) / 70
                if signal > 75:
                    colour = colours['green']
                elif signal > 40:
                    colour = colours['orange']
                else:
                    colour = colours['red']

    ssid = subprocess.check_output(["iwgetid", "-r"], universal_newlines=True).rstrip()

    return ssid, signal, colour


def _get_iface_string(iface, args):
    # iface name
    out = ' <span foreground="%s"><b>%s</b></span>' % (iface['operstate'][1], iface['iface'])
    
    # wlan info
    if iface['wireless']:
        out += ' <span foreground="%s">(<b>%s</b>,</span> <span foreground="%s"><b>%d%%</b></span><span foreground="%s">)</span>' % (
                iface['operstate'][1], iface['wireless'][0], iface['wireless'][2], iface['wireless'][1], iface['operstate'][1],
            )
    # IP
    out += ' %s' % iface['ip']

    # Bandwith/total
    # Down
    out += ' ('
    out += '<span font="FontAwesome">\uf063</span>%skBs' % int(iface['bandwith'][0]/1000)
    if not args.hide_totals:
        out += '[%0.2fGB]' % (int(iface['bandwith'][2]) / float('1e9'))
    # Up
    out += ' <span font="FontAwesome">\uf062</span>%skBs' % int(iface['bandwith'][1]/1000)
    if not args.hide_totals:
        out += '[%0.2fGB]' % (int(iface['bandwith'][3]) / float('1e9'))
    out += ')'

    return out

def print_out(to_print, args):
    # print the physical interfaces
    if not args.hide_physical:
        final_string = '<span font="FontAwesome">\uf0ac</span>'
        if to_print['phy']:
            for iface in sorted(to_print['phy']):
                final_string += _get_iface_string(to_print['ifaces'][iface], args)
        else:
            final_string += ' None'

    # then print all the logical interfaces (VPNs) excluding loopback
    if not args.hide_logical:
        final_string += ' <span font="FontAwesome">\uf023</span>'
        if len(to_print['log']) > 1:
            for iface in sorted(to_print['log']):
                # http://lxr.linux.no/#linux+v3.0/include/linux/if_arp.h
                if to_print['ifaces'][iface]['iface_type'] != 772:
                    final_string += _get_iface_string(to_print['ifaces'][iface], args)
        else:
            final_string += ' None'

    return final_string


def parse_commandline_arguments(args=None):
    parser = ArgumentParser(prog='networking', description='Networking  i3blocks booklet')

    parser.add_argument('--hide-totals', action='store_true', help='hide total data downloaded')
    parser.add_argument('--hide-physical', action='store_true', help='hide physical interfaces')
    parser.add_argument('--hide-logical', action='store_true', help='hide logical interfaces')

    if args:
        parsed_args = parser.parse_args(args)
    else:
        parsed_args = parser.parse_args()

    return parsed_args, parser

def main(args=None):
    args, parser = parse_commandline_arguments(args)

    to_print = {'phy': [], 'log': [], 'def':None, 'ifaces':{}}
    default_route = get_default_route()

    ifaces = all_interfaces()
    for iface, ip in ifaces:
        if default_route and iface == default_route[0]:
            to_print['def'] = iface

        iface_type = int(get_iface_type(iface))
        to_print['phy' if iface_type == 1 else 'log'].append(iface)
        to_print['ifaces'][iface] = {
            'iface': iface,
            'ip': ip,
            'operstate': get_iface_operstate(iface),
            'bandwith': get_iface_bandwith(iface),
            'iface_type': iface_type,
            'wireless': get_wireless_info(iface),
        }

    print(print_out(to_print, args))


if '__main__' == __name__:
    main()