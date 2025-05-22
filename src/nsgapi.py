import http
import json
import math
import requests

DEVICE_FIELDS_MATCH = ("id", "name", "address")
NSG_ADD_DEVICES_BATCH_SIZE = 50  # max number of devices to add to NSG in one request
DEFAULT_TIMOUT = 60


class NsgAPI:

    def __init__(self, log, url, token, netid) -> None:
        self.log = log
        self.url = url
        self.token = token
        self.netid = netid
        headers = self.make_headers()
        self.sess = requests.Session()
        self.sess.headers.update(headers)
        self.sess.stream = True
        self.sess.verify = False

    def query(self, nsgql, **kwargs):
        full_url = self.concatenate_url('v2/query/net/{0}/data'.format(self.netid))
        body = self.make_nsgql_query_request(nsgql)
        response = self.sess.post(full_url, json=body,
                                  timeout=kwargs.get("timeout", DEFAULT_TIMOUT),
                                  headers=kwargs.get("headers"),
                                  verify=kwargs.get("verify"))
        return self.parse_and_log_response('', response)

    def get_devices(self, **kwargs):
        resp = self.query('SELECT id AS id,name,address FROM devices WHERE physicalDevice=1', **kwargs)
        if not resp:
            self.log.error('get_devices: NetSpyGlass query returns empty response')
            return {}
        body = resp[0]
        if 'error' in body and body['error']:
            self.log.error('NetSpyGlass query error: {0}'.format(body['error']))
            return
        return {row['address']: row for row in body['rows']}

    def add_devices(self, devices, **kwargs) -> dict[str: dict]:
        """
        add several devices. Each item in list `devices` is expected to be a dictionary with
        keys 'name', 'address', 'channel'

        This function uses asynchronous API call to add devices but does not wait for the task to complete

        :param devices:  list of dictionaries
        """
        if not devices:
            return None

        full_url = self.concatenate_url('apiv3/net/{0}/device'.format(self.netid))
        result = {}
        for i in range(math.ceil(len(devices)/NSG_ADD_DEVICES_BATCH_SIZE)):
            current = devices[i*NSG_ADD_DEVICES_BATCH_SIZE:(i+1)*NSG_ADD_DEVICES_BATCH_SIZE]
            self.log.info('ADD:  {0}'.format(list(current)))
            timeout = kwargs.pop("timeout") if kwargs.get("timeout") else DEFAULT_TIMOUT
            response = self.sess.post(full_url, json=current, timeout=timeout, **kwargs)
            res = self.parse_and_log_response(f'ADD devices response ', response)
            if isinstance(res, list):
                for row in res:
                    result[row.get("address")] = row
        return result

    def delete_devices(self, device_ids, **kwargs):
        """
        delete several devices identified by their IDs in the list `devices_ids`

        This function uses asynchronous API call to delete devices but does not wait for the task to complete

        :param device_ids:  list of device ids
        """
        self.log.info(f'Device ids to REMOVE:  {list(device_ids)}')
        if not device_ids:
            return None
        for dev_id in device_ids:
            full_url = self.concatenate_url(f"apiv3/net/{self.netid}/device/{dev_id}")
            timeout = kwargs.pop("timeout") if kwargs.get("timeout") else DEFAULT_TIMOUT
            response = self.sess.delete(full_url, timeout=timeout, **kwargs)
            self.parse_and_log_response(f'DELETE device id={dev_id}', response)
        return

    def get_tasks(self, **kwargs):
        full_url = self.concatenate_url('v2/ui/net/{0}/tasks/'.format(self.netid))
        filter_ = {'active': '1'}
        timeout = kwargs.pop("timeout") if kwargs.get("timeout") else DEFAULT_TIMOUT
        response = self.sess.get(full_url, params=filter_, timeout=timeout, **kwargs)
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
            self.log.error(f'{name} JSON decoder error: {e} input={response.content}')
            return None
        if name:
            self.log.info(f'NSG {name} server={nsg_server} response={decoded}')
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

    def get_device_tags(self, device_filter: dict = {}, **kwargs) -> dict:
        """
        :param device_filter: dict describes device match:
                              one of "id": device_id (int)
                              "name": device name (str)
                              "address": device primary ip address
        :return:              list of devices with list of device tags
        """

        url = self.concatenate_url('v2/tags/net/{0}/external/'.format(self.netid))

        resp = self.sess.get(url=url,
                             params={k: v for k, v in device_filter if k in DEVICE_FIELDS_MATCH} or None,
                             **kwargs
                             )
        if resp.status_code != http.HTTPStatus.OK:
            self.log.error('NetSpyGlass GET tags error: {} {0}'.format(resp.status_code, resp.text))
            return list()

        try:
            result = resp.json()
        except json.JSONDecodeError as e:
            raise ValueError(e.msg)
        return result

    def post_device_tags(self, tag_list: list[dict], operation: str = "ADD", **kwargs) -> dict:
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
        resp = self.sess.post(url=url,
                              json=tag_list,
                              **kwargs
                              )
        if resp.status_code != http.HTTPStatus.OK:
            self.log.error('NetSpyGlass POST tags error: {} {0}'.format(resp.status_code, resp.text))
            return list()
        return self.parse_and_log_response(f"{operation} TAGS", resp)


