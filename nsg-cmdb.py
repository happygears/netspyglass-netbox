#!/usr/bin/env python3

import argparse
import ipaddress
import logging
import os
# import pynetbox
import sched
import sys
import time
import urllib3
import yaml

import nsgapi

VENDOR_SUPPORT = {'servicenow': ['nsg-servicenow', 'ServiceNow'],
                  'freshworks': ['nsg-freshworks', 'FreshWorks']
                 }

class NsgCmdbIntegration:

    def __init__(self, args) -> None:
        self.args = args
        self.config = None
        if args.config:
            with open(args.config, 'r') as f:
                self.config = yaml.safe_load(f)
                print("Config :", self.config)
        self.scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)
        self.interval_sec = int(pa.interval)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ])
        self.log = logging.getLogger('nsg-cmdb')
        self.log_nsgapi = logging.getLogger('nsgapi')
        # self.log_servicenow = logging.getLogger('nsg-servicenow')
        self.log.info("NSG URL : {}".format(self.config["nsg_settings"]["nsg_url"]))
        self.log.info("NSG Token : {}".format(self.config["nsg_settings"]["nsg_token"]))
        self.log.info("NSG Network ID : {}".format(self.config["nsg_settings"]["netid"]))
        self.nsg = nsgapi.NsgAPI(self.log_nsgapi,
                                 self.config["nsg_settings"]["nsg_url"],
                                 self.config["nsg_settings"]["nsg_token"],
                                 self.config["nsg_settings"]["netid"],
                                )

    def log_args(self):
        self.log.info(self.args)

    def start(self):
        self.log.info('CMDB-NetSpyGlass integration starts here.......')
        get_cmdb_type = self.config["cmdb_settings"]["cmdb_type"]
        self.log.info("CMDB Type : {}".format(get_cmdb_type))
        
        module_name = VENDOR_SUPPORT.get(get_cmdb_type)[0]
        class_name = VENDOR_SUPPORT.get(get_cmdb_type)[1]
        self.log.info("vendor module name : {}".format(module_name))
        self.log.info("vendor class name : {}".format(class_name))
        self.run(module_name, class_name)

        # # maintain the process indefinitely
        # try:
        #     while True:
        #         self.scheduler.run(blocking=True)
        # except KeyboardInterrupt as e:
        #     return
    
    def run(self, module_name, class_name):
        #__import__ method used to fetch module
        module = __import__(module_name)

        # getting attribute by getattr() method
        my_class = getattr(module, class_name)
        
        cmdb_devices_operational, cmdb_devices_retired = my_class.runs(self)

        self.log.info("============== START >> OPERATIONAL DEVICES << START =============")
        self.log.info('{}'.format(cmdb_devices_operational))
        self.log.info("============== END >> OPERATIONAL DEVICES << END =================")

        self.log.info("============== START >> RETIRED DEVICES << START =================")
        self.log.info('{}'.format(cmdb_devices_retired))
        self.log.info("============== END >> RETIRED DEVICES << END =====================")

        nsg_devices = self.get_nsg_device()

        cmdb_dev_set = set(cmdb_devices_operational.keys())
        self.log.info('cmdb_dev_set: {0}'.format(cmdb_dev_set))

        nsg_dev_set = set(nsg_devices.keys())
        self.log.info('nsg_dev_set: {0}'.format(nsg_dev_set))

        to_add = set.difference(cmdb_dev_set, nsg_dev_set)  # set of addresses as strings
        self.log.info('TO_ADD: {0}'.format(to_add))

        to_remove = set.difference(nsg_dev_set, cmdb_dev_set)  # set of addresses as strings
        self.log.info('TO_REMOVE-ALL_DEVICES: {0}'.format(to_remove))
        
        # additional check || This gets the CMDB "retired" devices
        cmdb_retired_dev_set = set(cmdb_devices_retired.keys())
        self.log.info('CMDB Retired devices: {0}'.format(cmdb_retired_dev_set))

        # This block checks for flag "skip_delete_non_cmdb_devices"
        # If "skip_delete_non_cmdb_devices" = True, skips delete devices that are added in NSG directly
        # i.e. deletes only devices that are marked as "retired" in SNOW CMDB
        if self.config["nsg_settings"]["skip_delete_non_cmdb_devices"]:
            to_remove = set.intersection(to_remove, cmdb_retired_dev_set)  # set of addresses as strings
            self.log.info('TO_REMOVE-NON_CMDB_DEVICES: {0}'.format(to_remove))


        # This logs final set of devices that are added/deleted in NSG
        self.log.info('TO_ADD_FINAL   : {0}'.format(to_add))
        self.log.info('TO_REMOVE_FINAL: {0}'.format(to_remove))

        if to_add:
            self.log.info('ADD devices:    {0}'.format(to_add))
            self.nsg.add_devices(list(self.make_add_device_dict(addr, cmdb_devices_operational[addr]) for addr in to_add))

        if to_remove:
            self.log.info('DELETE devices: {0}'.format(to_remove))
            self.nsg.delete_devices(list(nsg_devices[addr]['id'] for addr in to_remove))

    def get_nsg_device(self):

        tasks = self.nsg.get_tasks()
        if tasks:
            self.log.info('NetSpyGlass: tasks: {0}'.format(len(tasks)))
            self.log.warning('skipping cycle because of an active NSG background task')
            return
        
        nsg_devices = self.nsg.get_devices()
        self.log.info('NetSpyGlass: {0} devices'.format(len(nsg_devices)))
        self.log.info('nsg_devices : {}'.format(nsg_devices))
        return nsg_devices
    
    def make_add_device_dict(self, addr, cmdb_devices):
        """
        Build JSON dictionary that can be used as a body of NSG API call that adds device

        :param cmdb_devices :  dict of CMDB devices
        :param addr         :  device's primary ip as a string
        :return:
        """
        return {'name': cmdb_devices['name'], 'address': addr, 'channels': self.config["nsg_settings"]["nsg_channel"]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, help='Config yaml file that lists the configurations')
    parser.add_argument('--netid', required=False,
                        default=1,
                        help='NetSpyGlass network id, usually "1" (default=1)')
    parser.add_argument('--interval', required=False,
                        default=300,
                        help='Poll Netbox and NetSpyGlass at this interval (in seconds). (default=300)')
    pa = parser.parse_args()

    urllib3.disable_warnings()

    nsgcmdb = NsgCmdbIntegration(pa)
    nsgcmdb.log_args()
    nsgcmdb.start()
