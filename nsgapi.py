import http
import json
import requests

DEVICE_FIELDS_MATCH = ("id", "name", "address")


class NsgAPI:

    def __init__(self, log, url, token, netid) -> None:
        self.log = log
        self.url = url
        self.token = token
        self.netid = netid
        self.sess = requests.Session()

    def query(self, nsgql):
        full_url = self.concatenate_url('v2/query/net/{0}/data'.format(self.netid))
        headers = self.make_headers()
        # session = requests.Session()
        body = self.make_nsgql_query_request(nsgql)
        response = self.sess.post(full_url, json=body, timeout=60, headers=headers, verify=False, stream=True)
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
        self.log.info('ADD:  {0}'.format(list(devices)))
        if not devices:
            return None
        full_url = self.concatenate_url('v2/ui/net/{0}/devices/'.format(self.netid))
        headers = self.make_headers()

        response = self.sess.post(full_url, json=devices, timeout=60, headers=headers, verify=False, stream=True)
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
        headers = self.make_headers()
        response = self.sess.delete(full_url, timeout=60, headers=headers, verify=False, stream=True)
        return self.parse_and_log_response('DELETE', response)

    def get_tasks(self):
        full_url = self.concatenate_url('v2/ui/net/{0}/tasks/'.format(self.netid))
        headers = self.make_headers()
        filter = {'active': '1'}
        response = self.sess.get(full_url, params=filter, timeout=60, headers=headers, verify=False, stream=True)
        return self.parse_and_log_response('TASKS', response)

    def make_headers(self):
        headers = {'X-NSG-Auth-API-Token': self.token, 'Content-Type': 'application/json'}
        return headers

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

    def get_device_tags(self, device_filter: dict = {}) -> dict:
        """
        :param device_filter: dict describes device match:
                              one of "id": device_id (int)
                              "name": device name (str)
                              "address": device primary ip address
        :return:              list of devices with list of device tags
        """

        url = self.concatenate_url('v2/tags/net/{0}/external/'.format(self.netid))
        headers = self.make_headers()

        resp = self.sess.get(url=url,
                             headers=headers,
                             params={k:v for k, v in device_filter if k in DEVICE_FIELDS_MATCH} or None,
                             verify=False
                             )
        if resp.status_code != http.HTTPStatus.OK:
            self.log.error('NetSpyGlass GET tags error: {} {0}'.format(resp.status_code, resp.text))
            return list()

        try:
            result = resp.json()
        except json.JSONDecodeError as e:
            raise ValueError(e.msg)
        return result

    def post_device_tags(self, tag_list: list[dict], operation: str = "ADD") -> dict:
        """
        :param tag_list: list of dict
                            {
                             "category": "device",
                             "device": {} - dict to match device by "id": id or "address": address
                             "tags": [] list of tags in format: tagName.tagValue
                             }
        :return:              list of devices with list of device tags
        """

        url = self.concatenate_url('v2/tags/net/{0}/external/'.format(self.netid))
        headers = self.make_headers()
        resp = self.sess.post(url=url,
                              headers=headers,
                              verify=False,
                              json=tag_list
                              )
        if resp.status_code != http.HTTPStatus.OK:
            self.log.error('NetSpyGlass POST tags error: {} {0}'.format(resp.status_code, resp.text))
            return list()
        return self.parse_and_log_response(f"{operation} TAGS", resp)


