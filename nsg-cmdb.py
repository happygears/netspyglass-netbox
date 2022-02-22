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
        print("========= get_nsg_device")
        print("========= url : ", self.config["nsg_settings"]["nsg_url"])
        print("========= nsg_token: ", self.config["nsg_settings"]["nsg_token"])
        print("========= netid: ", self.config["nsg_settings"]["netid"])
        self.nsg = nsgapi.NsgAPI(self.log,
                            self.config["nsg_settings"]["nsg_url"],
                            self.config["nsg_settings"]["nsg_token"],
                            self.config["nsg_settings"]["netid"],
                           )

    def log_args(self):
        self.log.info(self.args)

    def start(self):
        self.log.info('CMDB-NetSpyGlass integration script starts')
        get_cmdb_type = self.config["cmdb_settings"]["cmdb_type"]
        self.log.info("CMDB Type : {}".format(get_cmdb_type))

        '''
        if get_cmdb_type == 'servicenow':
            self.run(module_name='nsg-servicenow', class_name='ServiceNow')
        elif get_cmdb_type == 'freshworks':
            self.run(module_name='nsg-freshworks', class_name='FreshWorks')
        else:
            self.log.info("CMDB Type : {} Not Supported".format(get_cmdb_type))
        '''
        
        module_name = VENDOR_SUPPORT.get(get_cmdb_type)[0]
        class_name = VENDOR_SUPPORT.get(get_cmdb_type)[1]
        print("module_name : ", module_name)
        print("class_name : ", class_name)
        self.run(module_name, class_name)

        # # maintain the process indefinitely
        # try:
        #     while True:
        #         self.scheduler.run(blocking=True)
        # except KeyboardInterrupt as e:
        #     return
    
    def run(self, module_name, class_name):
        #__import__ method used
        # to fetch module
        module = __import__(module_name)

        # getting attribute by
        # getattr() method
        my_class = getattr(module, class_name)
        # my_class.welcome('User_1')
        
        cmdb_devices_operational, cmdb_devices_retired = my_class.runs(self)
        # cmdb_devices = my_class.get_snow_cmdb_devices(self)
        self.log.info("output in main file")
        self.log.info("==============OPERATIONAL================")
        print(cmdb_devices_operational)
        self.log.info("==============RETIRED================")
        print(cmdb_devices_retired)
        self.log.info("==============================")

        # self.log = logging.getLogger('nsg-servicenow')
        # nsg_devices = my_class.get_nsg_device(self)
        # self.log = logging.getLogger('nsg-cmdb')
        nsg_devices = self.get_nsg_device()
        self.log.info('NetSpyGlass: {0} devices'.format(len(nsg_devices)))

        cmdb_dev_set = set(cmdb_devices_operational.keys())
        self.log.info('cmdb_dev_set: {0}'.format(cmdb_dev_set))
        nsg_dev_set = set(nsg_devices.keys())
        self.log.info('nsg_dev_set: {0}'.format(nsg_dev_set))

        to_add = set.difference(cmdb_dev_set, nsg_dev_set)  # set of addresses as strings
        self.log.info('TO_ADD:    {0}'.format(to_add))

        to_remove = set.difference(nsg_dev_set, cmdb_dev_set)  # set of addresses as strings
        self.log.info('TO_REMOVE-1: {0}'.format(to_remove))
        
        # additional check // Naidu
        cmdb_retired_dev_set = set(cmdb_devices_retired.keys())
        self.log.info('cmdb_retired_dev_set: {0}'.format(cmdb_retired_dev_set))


        if self.config["nsg_settings"]["skip_delete_non_cmdb_devices"]:
            # This deletes devices that are marked as "retired" in SNOW CMDB
            to_remove = set.intersection(to_remove, cmdb_retired_dev_set)  # set of addresses as strings
            self.log.info('TO_REMOVE-2: {0}'.format(to_remove))


        self.log.info('TO_ADD_FINAL:    {0}'.format(to_add))
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
        # self.log = logging.getLogger('nsg-servicenow')
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
    # parser.add_argument('--netbox-url', required=True)
    # parser.add_argument('--netbox-token', required=False)
    # parser.add_argument('--nsg-url', required=True)
    # parser.add_argument('--nsg-token', required=True)
    # parser.add_argument('--channel', required=True,
    #                     help='NetSpyGlass communication channel name to use with all imported devices')
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
