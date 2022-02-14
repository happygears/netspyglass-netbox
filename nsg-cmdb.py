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
        
        cmdb_devices = my_class.runs(self)
        # cmdb_devices = my_class.get_snow_cmdb_devices(self)
        self.log.info("output in main file")
        print(cmdb_devices)
        # self.log = logging.getLogger('nsg-servicenow')
        nsg_devices = my_class.get_nsg_device(self)
        self.log.info('NetSpyGlass: {0} devices'.format(len(nsg_devices)))

        # nb_dev_set = set(cmdb_devices.keys())
        # nsg_dev_set = set(nsg_devices.keys())
        # to_add = set.difference(nb_dev_set, nsg_dev_set)  # set of addresses as strings
        # to_remove = set.difference(nsg_dev_set, nb_dev_set)  # set of addresses as strings

        # if to_add:
        #     self.log.info('ADD devices:    {0}'.format(to_add))
        #     nsg.add_devices(list(self.make_add_device_dict(addr, cmdb_devices[addr]) for addr in to_add))

        # if to_remove:
        #     self.log.info('DELETE devices: {0}'.format(to_remove))
        #     nsg.delete_devices(list(nsg_devices[addr]['id'] for addr in to_remove))




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
