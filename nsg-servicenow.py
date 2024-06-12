
import logging
import requests
from requests.auth import HTTPBasicAuth

class ServiceNow:
    
    def runs(self):
        try:
            self.log_snow = logging.getLogger('nsg-servicenow')
            self.log_snow.info(self.args)
            self.log_snow.info("nsg-servicenow API processing starts here.....")

            # Set the request parameters
            url = self.config["cmdb_settings"]["cmdb_url"]
            user = self.config["cmdb_settings"]["cmdb_username"]
            pwd = self.config["cmdb_settings"]["cmdb_password"]
            self.log_snow.info("CMDB URL : {}".format(self.config["cmdb_settings"]["cmdb_url"]))
            self.log_snow.info("CMDB Username : {}".format(self.config["cmdb_settings"]["cmdb_username"]))
            self.log_snow.info("CMDB Password : {}".format(self.config["cmdb_settings"]["cmdb_password"]))

            # Set proper headers
            headers = {"Accept": "application/json", "Content-Type": "application/json"}

            def get_snow_cmdb_devices(url, device_status):
                operational_status = { "operational" : 1, "retired" : 6}
                device_status = operational_status.get(device_status)

                query_url = '?asset_tag=nsg-cmdb-testing&operational_status={}'.format(device_status)
                url = ''.join([url, query_url])

                # Do the HTTP request
                response = requests.get(url, auth=(user, pwd), headers=headers)
                print("Response code : ", response.status_code)

                # Check for HTTP codes other than 200
                if response.status_code != 200: 
                    print('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.content)
                    exit()
                
                response = response.json()
                # print("Response Type :", type(response))

                devices = response.get("result")
                final_dict = {}
                for device in devices:
                    sub_dict = {}
                    sub_dict['name'] = device['name']
                    sub_dict['ip_address'] = device['ip_address']
                    sub_dict['asset_tag'] = device['asset_tag']
                    sub_dict['sys_class_name'] = device['sys_class_name']
                    sub_dict['operational_status'] = device['operational_status']
                    final_dict[device['ip_address']] = sub_dict
                return final_dict


            devices_operational = get_snow_cmdb_devices(url, device_status='operational')
            self.log_snow.info("Operational Devices : {}".format(devices_operational))
            
            devices_retired = get_snow_cmdb_devices(url, device_status='retired')
            self.log_snow.info("Retired Devices : {}".format(devices_retired))

            return devices_operational, devices_retired

        except Exception as e:
            self.log_snow.exception('Unknown exception: %s', e)

