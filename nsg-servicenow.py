'''
class ServiceNow:
    def welcome(str):
        print("Hi ! % s Welcome to ServiceNow" % str)
'''

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
import requests
from requests.auth import HTTPBasicAuth

import nsgapi

class ServiceNow:

    def __init__(self, log) -> None:
        self.log = logging.getLogger('nsg-servicenow')
    
    def runs(self):
        try:
            self.log.info(self.args)
            print("Hello Naidu")
            # my_class.get_snow_cmdb_devices(self)
            # get_snow_cmdb_devices(self)
            # snow_cmdb_devices = self.get_snow_cmdb_devices()
            # print("snow_cmdb_devices : ", snow_cmdb_devices)

            def get_snow_cmdb_devices(self):
                print("get_snow_cmdb_devices")
                # Set the request parameters
                url = self.config["cmdb_settings"]["cmdb_url"]
                user = self.config["cmdb_settings"]["cmdb_username"]
                pwd = self.config["cmdb_settings"]["cmdb_password"]

                

                def get_devices(url, device_status):
                    operational_status = { "operational" : 1, "retired" : 6}
                    device_status = operational_status.get(device_status)

                    query_url = '?asset_tag=nsg-cmdb-testing&operational_status={}'.format(device_status)
                    url = ''.join([url, query_url])

                    # url = 'https://dev78298.service-now.com/api/now/table/cmdb_ci?asset_tag=nsg-cmdb-testing&operational_status=6'
                    # print("url : ", url)
                    
                    # Set proper headers
                    headers = {"Accept": "application/json", "Content-Type": "application/json"}
                    
                    # Do the HTTP request
                    response = requests.get(url, auth=(user, pwd), headers=headers)
                    print("Response code : ", response.status_code)

                    # Check for HTTP codes other than 200
                    if response.status_code != 200: 
                        print('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.content)
                        exit()
                    
                    response = response.json()
                    print("Response Type :", type(response))
                    return response


                # snow_cmdb_devices = get_devices(url, device_status='operational')
                # print("get_operational_devices :", snow_cmdb_devices)
                
                snow_cmdb_devices = get_devices(url, device_status='retired')
                print("get_retired_devices :", snow_cmdb_devices)

                return snow_cmdb_devices
            
            get_snow_cmdb_devices(self)

        except Exception as e:
            self.log.exception('Unknown exception: %s', e)

    def get_nsg_device(self):
        
        print("========= get_nsg_device")
        print("========= url : ", self.config["nsg_settings"]["nsg_url"])
        print("========= nsg_token: ", self.config["nsg_settings"]["nsg_token"])
        print("========= netid: ", self.config["nsg_settings"]["netid"])
        nsg = nsgapi.NsgAPI(self.log,
                            self.config["nsg_settings"]["nsg_url"],
                            self.config["nsg_settings"]["nsg_token"],
                            self.config["nsg_settings"]["netid"],
                           )
        # tasks = nsg.get_tasks()
        # if tasks:
        #     self.log.info('NetSpyGlass: tasks: {0}'.format(len(tasks)))
        #     self.log.warning('skipping cycle because of an active NSG background task')
        #     return
        
        nsg_devices = nsg.get_devices()
        # self.log = logging.getLogger('nsg-servicenow')
        self.log.info('NetSpyGlass: {0} devices'.format(len(nsg_devices)))
        return nsg_devices
    
    # def get_snow_cmdb_devices(self):
    #     print("get_snow_cmdb_devices")
    #     # Set the request parameters
    #     url = self.config["cmdb_settings"]["cmdb_url"]
    #     user = self.config["cmdb_settings"]["cmdb_username"]
    #     pwd = self.config["cmdb_settings"]["cmdb_password"]

        

    #     def get_devices(url, device_status):
    #         operational_status = { "operational" : 1, "retired" : 6}
    #         device_status = operational_status.get(device_status)

    #         query_url = '?asset_tag=nsg-cmdb-testing&operational_status={}'.format(device_status)
    #         url = ''.join([url, query_url])

    #         # url = 'https://dev78298.service-now.com/api/now/table/cmdb_ci?asset_tag=nsg-cmdb-testing&operational_status=6'
    #         # print("url : ", url)
            
    #         # Set proper headers
    #         headers = {"Accept": "application/json", "Content-Type": "application/json"}
            
    #         # Do the HTTP request
    #         response = requests.get(url, auth=(user, pwd), headers=headers)
    #         print("Response code : ", response.status_code)

    #         # Check for HTTP codes other than 200
    #         if response.status_code != 200: 
    #             print('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.content)
    #             exit()
            
    #         response = response.json()
    #         print("Response Type :", type(response))
    #         return response


    #     # snow_cmdb_devices = get_devices(url, device_status='operational')
    #     # print("get_operational_devices :", snow_cmdb_devices)
        
    #     snow_cmdb_devices = get_devices(url, device_status='retired')
    #     print("get_retired_devices :", snow_cmdb_devices)

    #     return snow_cmdb_devices

