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

                    '''
                    {
                        "result": [
                            {
                            "attested_date": "",
                            "skip_sync": "false",
                            "operational_status": "6",
                            "sys_updated_on": "2022-02-11 10:26:46",
                            "attestation_score": "",
                            "discovery_source": "",
                            "first_discovered": "",
                            "sys_updated_by": "admin",
                            "due_in": "",
                            "sys_created_on": "2022-02-11 05:35:06",
                            "sys_domain": {
                                "link": "https://dev78298.service-now.com/api/now/table/sys_user_group/global",
                                "value": "global"
                            },
                            "install_date": "",
                            "gl_account": "",
                            "invoice_number": "",
                            "sys_created_by": "admin",
                            "warranty_expiration": "",
                            "asset_tag": "nsg-cmdb-testing",
                            "fqdn": "",
                            "change_control": "",
                            "owned_by": "",
                            "checked_out": "",
                            "sys_domain_path": "/",
                            "business_unit": "",
                            "delivery_date": "",
                            "maintenance_schedule": "",
                            "install_status": "1",
                            "cost_center": "",
                            "attested_by": "",
                            "supported_by": "",
                            "dns_domain": "",
                            "name": "iad1-bb01",
                            "assigned": "",
                            "life_cycle_stage": "",
                            "purchase_date": "",
                            "subcategory": "IP",
                            "short_description": "",
                            "assignment_group": "",
                            "managed_by": "",
                            "managed_by_group": "",
                            "can_print": "false",
                            "last_discovered": "",
                            "sys_class_name": "cmdb_ci_ip_router",
                            "manufacturer": "",
                            "sys_id": "73d994e20721011074e4ff4c7c1ed065",
                            "po_number": "",
                            "checked_in": "",
                            "sys_class_path": "/!!/!2/!!/!.",
                            "life_cycle_stage_status": "",
                            "mac_address": "",
                            "vendor": "",
                            "company": "",
                            "justification": "",
                            "model_number": "",
                            "department": "",
                            "assigned_to": "",
                            "start_date": "",
                            "comments": "",
                            "cost": "",
                            "sys_mod_count": "3",
                            "monitor": "false",
                            "serial_number": "",
                            "ip_address": "10.10.10.3",
                            "model_id": {
                                "link": "https://dev78298.service-now.com/api/now/table/cmdb_model/d92cdce60721011074e4ff4c7c1ed035",
                                "value": "d92cdce60721011074e4ff4c7c1ed035"
                            },
                            "duplicate_of": "",
                            "sys_tags": "",
                            "cost_cc": "USD",
                            "order_date": "",
                            "schedule": "",
                            "support_group": "",
                            "environment": "",
                            "due": "",
                            "attested": "false",
                            "correlation_id": "",
                            "unverified": "false",
                            "attributes": "",
                            "location": "",
                            "asset": {
                                "link": "https://dev78298.service-now.com/api/now/table/alm_asset/552cdce60721011074e4ff4c7c1ed037",
                                "value": "552cdce60721011074e4ff4c7c1ed037"
                            },
                            "category": "Resource",
                            "fault_count": "0",
                            "lease_id": ""
                            }
                        ]
                    }
                    '''
                    devices = response.get("result")
                    final_dict = {}
                    for device in devices:
                        sub_dict = {}
                        # print("Type =====> : ", type(device))
                        # print(device)
                        sub_dict['name'] = device['name']
                        sub_dict['ip_address'] = device['ip_address']
                        sub_dict['asset_tag'] = device['asset_tag']
                        sub_dict['sys_class_name'] = device['sys_class_name']
                        sub_dict['operational_status'] = device['operational_status']
                        final_dict[device['ip_address']] = sub_dict
                    return final_dict


                snow_cmdb_devices_operational = get_devices(url, device_status='operational')
                print("get_snow_cmdb_devices_operational :", snow_cmdb_devices_operational)
                
                snow_cmdb_devices_retired = get_devices(url, device_status='retired')
                print("get_snow_cmdb_devices_retired :", snow_cmdb_devices_retired)

                return snow_cmdb_devices_operational, snow_cmdb_devices_retired
            
            snow_cmdb_devices_operational, snow_cmdb_devices_retired = get_snow_cmdb_devices(self)
            
            return snow_cmdb_devices_operational, snow_cmdb_devices_retired 


        except Exception as e:
            self.log.exception('Unknown exception: %s', e)

    # def get_nsg_device(self):
        
    #     print("========= get_nsg_device")
    #     print("========= url : ", self.config["nsg_settings"]["nsg_url"])
    #     print("========= nsg_token: ", self.config["nsg_settings"]["nsg_token"])
    #     print("========= netid: ", self.config["nsg_settings"]["netid"])
    #     nsg = nsgapi.NsgAPI(self.log,
    #                         self.config["nsg_settings"]["nsg_url"],
    #                         self.config["nsg_settings"]["nsg_token"],
    #                         self.config["nsg_settings"]["netid"],
    #                        )
    #     # tasks = nsg.get_tasks()
    #     # if tasks:
    #     #     self.log.info('NetSpyGlass: tasks: {0}'.format(len(tasks)))
    #     #     self.log.warning('skipping cycle because of an active NSG background task')
    #     #     return
        
    #     nsg_devices = nsg.get_devices()
    #     # self.log = logging.getLogger('nsg-servicenow')
    #     self.log.info('NetSpyGlass: {0} devices'.format(len(nsg_devices)))
    #     self.log.info('nsg_devices : {}'.format(nsg_devices))
    #     return nsg_devices
    
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

