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
import yaml

import nsgapi


class NsgNetboxIntegration:

    def __init__(self, args) -> None:
        self.args = args
        self.config = None
        if args.config:
            with open(args.config, 'r') as f:
                self.config = yaml.safe_load(f)
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
        return {self.get_primary_ip(d): d for d in self.netbox_dcim(nbox) if self.condition(d)}

    def netbox_dcim(self, nbox):
        if not self.config:
            return nbox.dcim.devices.filter(status=1)
        if not self.config.get('filters'):
            self.config['filters'] = {'status': 1}
        filters = {}
        for fk, fv in self.config['filters'].items():
            if 'custom_fields' in fk:
                fk = 'cf_{}'.format(fk.split('.')[1])
            filters[fk] = fv
        if self.config.get('whitelist'):
            filters['tag'] = self.config['whitelist']
        return nbox.dcim.devices.filter(**filters)

    def get_primary_ip(self, device):
        return str(ipaddress.ip_interface(device.primary_ip).ip)

    def condition(self, device):
        if self.config.get('blacklist'):
            return device.primary_ip is not None and not any([tag in device.tags for tag in self.config['blacklist']])
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
    parser.add_argument('--netbox-token', required=False)
    parser.add_argument('--nsg-url', required=True)
    parser.add_argument('--nsg-token', required=True)
    parser.add_argument('--channel', required=True,
                        help='NetSpyGlass communication channel name to use with all imported devices')
    parser.add_argument('--config', required=False, help='Config yaml file that lists the netbox query options')
    parser.add_argument('--netid', required=False,
                        default=1,
                        help='NetSpyGlass network id, usually "1" (default=1)')
    parser.add_argument('--interval', required=False,
                        default=300,
                        help='Poll Netbox and NetSpyGlass at this interval (in seconds). (default=300)')
    pa = parser.parse_args()

    urllib3.disable_warnings()

    nsgnb = NsgNetboxIntegration(pa)
    nsgnb.log_args()
    nsgnb.start()
