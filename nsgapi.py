
import json
import requests


class NsgAPI:

    def __init__(self, log, url, token, netid) -> None:
        self.log = log
        self.url = url
        self.token = token
        self.netid = netid

    def query(self, nsgql):
        full_url = self.concatenate_url('v2/query/net/{0}/data'.format(self.netid))
        headers = {'X-NSG-Auth-API-Token': self.token}
        session = requests.Session()
        body = self.make_nsgql_query_request(nsgql)
        with session.post(full_url, json=body, timeout=60, headers=headers, verify=False, stream=True) as response:
            return self.parse_and_log_response('', response)

    def get_devices(self):
        resp = self.query('SELECT id,name,address FROM devices WHERE physicalDevice=1')
        if not resp:
            # log.error('NetSpyGlass query returns empty response')
            return {}
        body = resp[0]
        if 'error' in body and body['error']:
            self.log.error('NetSpyGlass query error: {0}'.format(body['error']))
            return
        return {row['address']: row for row in body['rows']}

    def add_devices(self, devices):
        """
        add several devices. Each item in list `devices` is expected to be a dictionary with
        keys 'name', 'address', 'channel'

        This function uses asynchronous API call to add devices but does not wait for the task to complete

        :param devices:  list of dictionaries
        """
        print('ADD:  {0}'.format(list(devices)))
        if not devices:
            return None
        full_url = self.concatenate_url('v2/ui/net/{0}/devices/'.format(self.netid))
        headers = {'X-NSG-Auth-API-Token': self.token, 'Content-Type': 'application/json'}
        session = requests.Session()
        with session.post(full_url, json=devices, timeout=60, headers=headers, verify=False, stream=True) as response:
            return self.parse_and_log_response('ADD', response)

    def delete_devices(self, device_ids):
        """
        delete several devices identified by their IDs in the list `devices_ids`

        This function uses asynchronous API call to delete devices but does not wait for the task to complete

        :param device_ids:  list of device ids
        """
        print('REMOVE:  {0}'.format(list(device_ids)))
        if not device_ids:
            return None
        full_url = self.concatenate_url(
            'v2/ui/net/{0}/devices/{1}'.format(self.netid, ','.join(str(x) for x in device_ids)))
        headers = {'X-NSG-Auth-API-Token': self.token}
        session = requests.Session()
        with session.delete(full_url, timeout=60, headers=headers, verify=False, stream=True) as response:
            return self.parse_and_log_response('DELETE', response)

    def parse_and_log_response(self, name, response):
        headers = response.headers
        nsg_server = headers.get('Nsg-Server', '')
        try:
            decoded = response.json()
        except json.JSONDecodeError as e:
            self.log.error('JSON decoder error: {0} input={1}'.format(e, response.content))
            return None
        if name:
            self.log.info('NSG {0} server={1} response={2}'.format(name, nsg_server, decoded))
        return decoded

    def concatenate_url(self, uri_path):
        if uri_path[0] == '/':
            return self.url + uri_path
        else:
            return self.url + '/' + uri_path

    def make_nsgql_query_request(self, nsgql):
        query = {
            'targets': []
        }
        query['targets'].append(
            {
                'nsgql': nsgql,
                'format': 'json'
            }
        )
        return query
