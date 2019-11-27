#!/usr/bin/env python3

import argparse
import json
import ipaddress
import logging
import os
import pynetbox
import sched
import sys
import time
import urllib3

import nsgapi

logging.basicConfig(
    filename=os.getenv('LOG_DIR', '.') + '/nsg-netbox.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('nsg-netbox')


class NsgNetboxIntegration:

    def __init__(self, args) -> None:
        self.args = args
        self.scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)
        self.interval_sec = int(pa.interval)

    def log_args(self):
        log.info(self.args)

    def start(self):
        self.run()
        # maintain the process indefinitely
        while True:
            self.scheduler.run(blocking=True)

    def run(self):
        """
        get list of devices in Netbox, then get list of devices in NetSpyGlass, compare
        and update devices in NetSpyGlass. Use `primary_ip` attribute (Netbox) to match devices
        """
        try:
            # schedule next run
            self.scheduler.enter(delay=self.interval_sec, priority=1, action=self.run)
            nb = pynetbox.api(url=self.args.netbox_url, token=self.args.netbox_token)

            # TODO: user should be able to pass custom filter via command line args
            # status = 1 picks up devices with status=Active
            nb_devices = {str(ipaddress.ip_interface(d.primary_ip).ip): d
                          for d in nb.dcim.devices.filter(status=1) if d.primary_ip is not None}
            log.info('Netbox:      {0} devices'.format(len(nb_devices)))

            nsg = nsgapi.NsgAPI(log, self.args.nsg_url, self.args.nsg_token, self.args.netid)
            nsg_devices = nsg.get_devices()
            log.info('NetSpyGlass: {0} devices'.format(len(nsg_devices)))

            nb_dev_set = set(nb_devices.keys())
            nsg_dev_set = set(nsg_devices.keys())
            to_add = set.difference(nb_dev_set, nsg_dev_set)     # set of addresses as strings
            to_remove = set.difference(nsg_dev_set, nb_dev_set)  # set of addresses as strings

            if to_add:
                log.info('ADD devices:    {0}'.format(to_add))
                nsg.add_devices(list(self.make_add_device_dict(nb_devices, addr) for addr in to_add))

            if to_remove:
                log.info('DELETE devices: {0}'.format(to_remove))
                nsg.delete_devices(list(nsg_devices[addr]['id'] for addr in to_remove))

        except pynetbox.core.query.RequestError as e:
            log.error('Netbox API call has failed: {0}'.format(e))
        except Exception as e:
            log.exception('Unknown exception: %s', e)

    def make_add_device_dict(self, nb_devices, addr):
        return {'name': nb_devices[addr].name, 'address': addr, 'channels': self.args.channel}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--netbox-url', required=True)
    parser.add_argument('--netbox-token', required=True)
    parser.add_argument('--nsg-url', required=True)
    parser.add_argument('--nsg-token', required=True)
    parser.add_argument('--channel', required=True,
                        help='NetSpyGlass communication channel name to use with all imported devices')
    parser.add_argument('--tags', required=False,
                        help='comma-separated list of device tags to copy from Netbox to NetSpyGlass (optional)')
    parser.add_argument('--netid', required=False,
                        default=1,
                        help='NetSpyGlass network id, usually "1" (default=1)')
    parser.add_argument('--interval', required=False,
                        default=300,
                        help='Poll Netbox and NetSpyGlass at this interval (in seconds). (default=300)')
    pa = parser.parse_args()

    urllib3.disable_warnings()

    log.info('Netbox-NetSpyGlass integration script starts')

    nsgnb = NsgNetboxIntegration(pa)
    nsgnb.log_args()
    nsgnb.start()
