#!/usr/bin/env python3

import argparse
import ipaddress
import logging
import os
import pynetbox
import sched
import sys
import time
import urllib3

import nsgapi


class NsgNetboxIntegration:

    def __init__(self, args) -> None:
        self.args = args
        self.scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)
        self.interval_sec = int(pa.interval)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ])
        self.log = logging.getLogger('nsg-netbox')

    def log_args(self):
        self.log.info(self.args)

    def start(self):
        self.log.info('Netbox-NetSpyGlass integration script starts')
        self.run()
        # maintain the process indefinitely
        try:
            while True:
                self.scheduler.run(blocking=True)
        except KeyboardInterrupt as e:
            return

    def run(self):
        """
        get list of devices in Netbox, then get list of devices in NetSpyGlass, compare
        and update devices in NetSpyGlass. Use `primary_ip` attribute (Netbox) to match devices
        """
        try:
            # schedule next run
            self.scheduler.enter(delay=self.interval_sec, priority=1, action=self.run)

            nsg = nsgapi.NsgAPI(self.log, self.args.nsg_url, self.args.nsg_token, self.args.netid)
            tasks = nsg.get_tasks()
            if tasks:
                self.log.info('NetSpyGlass: tasks: {0}'.format(len(tasks)))
                self.log.warning('skipping cycle because of an active NSG background task')
                return

            nbox = pynetbox.api(url=self.args.netbox_url, token=self.args.netbox_token)

            nbox_devices = self.get_netbox_devices(nbox)
            self.log.info('Netbox:      {0} devices'.format(len(nbox_devices)))

            nsg_devices = nsg.get_devices()
            self.log.info('NetSpyGlass: {0} devices'.format(len(nsg_devices)))

            nb_dev_set = set(nbox_devices.keys())
            nsg_dev_set = set(nsg_devices.keys())
            to_add = set.difference(nb_dev_set, nsg_dev_set)  # set of addresses as strings
            to_remove = set.difference(nsg_dev_set, nb_dev_set)  # set of addresses as strings

            if to_add:
                self.log.info('ADD devices:    {0}'.format(to_add))
                nsg.add_devices(list(self.make_add_device_dict(addr, nbox_devices[addr]) for addr in to_add))

            if to_remove:
                self.log.info('DELETE devices: {0}'.format(to_remove))
                nsg.delete_devices(list(nsg_devices[addr]['id'] for addr in to_remove))

        except pynetbox.core.query.RequestError as e:
            self.log.error('Netbox API call has failed: {0}'.format(e))
        except Exception as e:
            self.log.exception('Unknown exception: %s', e)

    def get_netbox_devices(self, nbox):
        # status = 1 picks up devices with status=Active
        return {self.get_primary_ip(d): d for d in self.netbox_dcim(nbox) if self.condition(d)}

    def netbox_dcim(self, nbox):
        if self.args.whitelist:
            return nbox.dcim.devices.filter(status=1, tag=[self.args.whitelist])
        else:
            return nbox.dcim.devices.filter(status=1)

    def get_primary_ip(self, device):
        return str(ipaddress.ip_interface(device.primary_ip).ip)

    def condition(self, device):
        if self.args.blacklist:
            return device.primary_ip is not None and self.args.blacklist not in device.tags
        else:
            return device.primary_ip is not None

    def make_add_device_dict(self, addr, nb_device):
        """
        Build JSON dictionary that can be used as a body of NSG API call that adds device

        :param nb_device: an object received from `pynetbox.dcim.devices.filter() call`
        :param addr:      device's primary ip as a string
        :return:
        """
        return {'name': nb_device.name, 'address': addr, 'channels': self.args.channel}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--netbox-url', required=True)
    parser.add_argument('--netbox-token', required=True)
    parser.add_argument('--nsg-url', required=True)
    parser.add_argument('--nsg-token', required=True)
    parser.add_argument('--channel', required=True,
                        help='NetSpyGlass communication channel name to use with all imported devices')
    parser.add_argument('--whitelist', required=False,
                        help='the name of the Netbox device tag that will be passed to `dcim.devices.filter()` '
                             'call to filter devices in Netbox. Only devices that have this tag will be '
                             'synchronized to NetSpyGlass. Default is None, which causes all '
                             'devices present in Netbox to be synchronized. At this time this can be only '
                             'a single tag name. Example: "--whitelist=nsg"')
    parser.add_argument('--blacklist', required=False,
                        help='the name of the Netbox device tag that will be passed '
                             'to `dcim.devices.filter()` call to filter devices in '
                             'Netbox. Devices that have this tag will not be '
                             'synchronized to NetSpyGlass. Blacklist filter is '
                             'applied after the whitelist (if any). Default is None, '
                             'which turns this off and causes all devices that pass '
                             'whitelist will be synchronized. At this time this can '
                             'be only a single tag name. Example: "--blacklist=nsg_ignore"')
    parser.add_argument('--netid', required=False,
                        default=1,
                        help='NetSpyGlass network id, usually "1" (default=1)')
    parser.add_argument('--interval', required=False,
                        default=300,
                        help='Poll Netbox and NetSpyGlass at this interval (in seconds). (default=300)')
    parser.add_argument('--log-dir', required=False,
                        default='.',
                        help='Directory where the log will be created')
    pa = parser.parse_args()

    urllib3.disable_warnings()

    nsgnb = NsgNetboxIntegration(pa)
    nsgnb.log_args()
    nsgnb.start()
