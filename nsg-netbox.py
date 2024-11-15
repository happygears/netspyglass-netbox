#!/usr/bin/env python3

import argparse
import http
import ipaddress
import logging
import os
import re

import pynetbox
from pynetbox.core.query import Request as nbox_Request
import sched
import time
import urllib3
import yaml
import requests
import socket
import nsgapi


class NsgNetboxIntegration:

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.domain = None
        self.config = self.load_config(self.args.config
                                       or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                       "config",
                                                       "config.yaml"))
        if not self.config:
            raise ValueError("config not laded")
        self.log = logging.getLogger('nsg-netbox')
        self.nsg = nsgapi.NsgAPI(self.log, self.args.nsg_url, self.args.nsg_token, self.args.netid)
        self.nbox = pynetbox.api(url=self.args.netbox_url, token=self.args.netbox_token)
        version = self.nbox_version()
        if version and version > 2.6:
            self.active = "active"
        else:
            self.active = 1
        self.domain = self.config.get('domain')
        self.channels={}
        if args.channel:
            self.channels["*"] = [args.channel, ]
        else:
            self.channels = self.config.get("default_channels", {})
        if not self.channels:
            raise ValueError("channels not specified")
        self.scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)

        self.interval_sec = int(pa.interval)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ])

    def load_config(self, config_file: str) -> dict or None:
        """
        load and parse local config
        :param config_file: config file path
        :return: parsed config dict or None
        """
        try:
            with open(config_file, 'r') as f:
                conf = yaml.safe_load(f)
                # conf.update(self.resolve_refs(conf))
                return conf
        except FileNotFoundError:
            self.log.error(f"config file: {config_file} not found")
        except yaml.YAMLError as err:
            self.log.error(f"load config yaml error: {err}")
        return None

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

        def wait_tasks_done():
            # wait for nsg tasks finished
            while True:
                tasks = self.nsg.get_tasks()
                if not tasks:
                    break
                time.sleep(2)

        try:
            tasks = self.nsg.get_tasks()
            if tasks:
                self.log.info('NetSpyGlass: tasks: {0}'.format(len(tasks)))
                self.log.warning('skipping cycle because of an active NSG background task')
                # schedule next run
                self.scheduler.enter(delay=self.interval_sec, priority=1, action=self.run)
                return

            nbox_devices = self.get_netbox_devices()
            self.log.info(f'Netbox:      {len(nbox_devices):>6} devices')

            nsg_devices = self.nsg.get_devices()
            nsg_devices = {k: v for k, v in nsg_devices.items()
                           if v.get('address') not in (self.config.get('nsg_blacklist').get('address', [])
                                                       if self.config.get('nsg_blacklist') else [])
                           and v.get('name') not in (self.config.get('nsg_blacklist').get('name', [])
                                                     if self.config.get('nsg_blacklist') else [])
                           and v.get('id') not in (self.config.get('nsg_blacklist', {}).get('deviceId', [])
                                                   if self.config.get('nsg_blacklist') else [])
                           }
            self.log.info(f'NetSpyGlass: {len(nsg_devices):>6} devices')

            tags_ = self.nsg.get_device_tags()
            tags = {}
            for i in tags_:
                key = i.get("device", {}).get("address")
                if not tags.get(key):
                    tags[key] = {"id": i.get("device", {}).get("id"),
                                 "tags": dict(t.split(".", maxsplit=1) for t in i.get("tags", {}))}
                else:
                    tags[key]["tags"].update(dict(t.split(".", maxsplit=1) for t in i.get("tags", {})))

            nb_dev_set = set(nbox_devices.keys())
            nsg_dev_set = set(nsg_devices.keys())
            to_add = set.difference(nb_dev_set, nsg_dev_set)  # set of addresses as strings
            to_remove = set.difference(nsg_dev_set, nb_dev_set)  # set of addresses as strings

            if to_remove:
                self.log.info('DELETE devices: {0}'.format(to_remove))
                self.nsg.delete_devices(list(nsg_devices[addr]['id'] for addr in to_remove))
                wait_tasks_done()
                remove_tags = make_remove_tag_dict(nsg_devices=to_remove, nsg_tags=tags)
                if remove_tags:
                    for i in remove_tags:
                        self.log.info(f" tags list to delete: {i}")
                    self.nsg.post_device_tags(tag_list=remove_tags, operation="DELETE")

            if to_add:
                payload = list(self.make_add_device_dict(addr, nbox_devices[addr]) for addr in to_add)
                self.log.info('ADD devices:    {0}'.format(to_add))
                self.nsg.add_devices(payload)

            tag_list = make_add_tag_dict(nbox_devices=nbox_devices,
                                         nsg_tags=tags)
            # wait for devices added to nsg
            wait_tasks_done()

            if tag_list:
                for i in tag_list:
                    self.log.info(f" tags list to update: {i}")
                self.nsg.post_device_tags(tag_list=tag_list)
            else:
                self.log.info(f" no devices with new/changed tags found")

        except pynetbox.core.query.RequestError as e:
            self.log.error('Netbox API call has failed: {0}'.format(e))
        except Exception as e:
            self.log.exception('Unknown exception: %s', e)
        # schedule next run
        self.scheduler.enter(delay=self.interval_sec, priority=1, action=self.run)

    def nbox_version(self) -> float:
        """
        get netbox minor version
        :return: netbox version
        """
        headers = dict(accept="application/json;")
        headers["authorization"] = "Token {}".format(self.nbox.token)
        version = None

        res = requests.get(url=self.nbox.base_url + "/status", headers=headers)
        if res.status_code == http.HTTPStatus.OK:
            try:
                resp = res.json()
                version = resp.get("netbox-version")
            except requests.exceptions.JSONDecodeError:
                pass
        if not version:
            res = requests.get(url=self.nbox.base_url, headers=headers)
            version = res.headers.get("API-Version", "")
            if not version:
                return None
        try:
            return float(".".join(version.split("-")[0].split(".")[:2]))
        except ValueError:
            return None

    def get_netbox_devices(self):
        result = {}
        filters = {}
        if self.config and self.config.get('filters'):
            for fk, fv in self.config['filters'].items():
                if 'custom_fields' in fk:
                    fk = 'cf_{}'.format(fk.split('.')[1])
                filters[fk] = fv
        else:
            filters = {"status": self.active}

        if self.config and self.config.get('whitelist'):
            filters['tag'] = self.config['whitelist']

        devices = self.netbox_dcim(model="devices", filters=filters)
        for device in devices:
            ip = self.get_primary_ip(device)
            if ip:
                result[ip] = device
            else:
                host = f"{device.name}.{self.domain}" if self.domain and self.domain not in device.name else device.name
                try:
                    ip = socket.gethostbyname(host)
                    if ip:
                        result[ip] = device
                    else:
                        self.log.error("get_netbox_devices: can't resolve device name: {}".format(device.name))
                except Exception as e:
                    self.log.error("get_netbox_devices: can't resolve device name: {}: {}".format(device.name, e))
            device.nsg_tags = self.extract_tags(device)
        return result

    def netbox_dcim(self, model: str = "devices", filters: dict = None) -> list[pynetbox.core.response.Record]:
        entity = getattr(self.nbox.dcim, model)
        if not filters:
            return entity.all()
        return entity.filter(**filters)

    @staticmethod
    def get_primary_ip(device: pynetbox.models.dcim.Devices) -> str or None:
        return str(ipaddress.ip_interface(device.primary_ip).ip) if device.primary_ip else None

    def condition(self, device: pynetbox.models.dcim.Devices):
        if self.config and self.config.get('blacklist'):
            return device.primary_ip is not None and not any([tag in device.tags for tag in self.config['blacklist']])
        else:
            return device.primary_ip is not None

    def make_add_device_dict(self, addr: str, nb_device: pynetbox.models.dcim.Devices) -> dict:
        """
        Build JSON dictionary that can be used as a body of NSG API call that adds device

        :param nb_device: an object received from `pynetbox.dcim.devices.filter() call`
        :param addr:      device's primary ip as a string
        :return:
        """
        channels = []
        for k, v in self.channels.items():
            if k != "*":
                if re.findall(k, nb_device.name):
                    channels.extend(v)
        if not channels:
            channels.extend(self.channels.get("*", []))

        return {'name': nb_device.name, 'address': addr, 'channels': ", ".join(channels)}

    def extract_tags(self, instance: pynetbox.core.response.Record) -> dict[str: any]:
        """
        Find all tags described in config from netbox Record instance (Device)
        
        :param instance: netbox record
        :return: dict of found tags
        """
        result = {}
        for tag, attrs in self.config.get("nsgTags", {}).items():
            if attrs:
                if attrs.get("path"):
                    value = self.extract_tag(instance, attrs)
                else:
                    continue
                if value:
                    result[tag] = value
        return result

    def extract_tag(self, inst: pynetbox.core.response.Record,
                    tag: dict[str: str]) -> str or int or float or None:
        """
        Find given tag in the record

        :param inst: netbox record
        :param tag: tag description from config
        :return: found tag or None
        """
        if not isinstance(tag, dict):
            return None
        path = tag.get("path")
        if not path:
            return None
        nodes = path.split(".")
        try:
            cur = getattr(inst, nodes[0])
        except AttributeError:
            return None
        if not isinstance(cur, (str, int, float, bool)):
            for node in nodes[1:]:
                if isinstance(cur, dict):
                    cur = cur.get(node, {})
                    if isinstance(cur, (str, int, float, bool)):
                        break
                elif isinstance(cur, (list, tuple, set)):
                    return cur
                else:
                    try:
                        cur = getattr(cur, node)
                    except AttributeError:
                        return None
        if isinstance(cur, pynetbox.core.response.Record):
            cur = f"{cur}"
        regexp = tag.get("regexp")
        if regexp:
            from re import findall
            cur1 = findall(regexp, cur)
            if cur1:
                cur = cur1[0]

        subst = tag.get("mapping")
        if subst:
            if isinstance(subst, dict):
                cur = subst.get(cur, subst.get("*", cur))
        if cur:
            tr = tag.get("transform")
            if tr == "upper":
                cur = cur.upper()
            elif tr == "lower":
                cur = cur.lower()
            if tr == "capitalize":
                cur = cur.capitalize()
        return cur


def update_from_env(nspace: argparse.Namespace):
    for i in ('NSG_TOKEN', 'NETBOX_URL', 'NETBOX_TOKEN', 'NSG_URL'):
        attr = i.lower()
        if not getattr(nspace, attr):
            setattr(nspace, attr, os.environ.get(i))


def make_add_tag_dict(nbox_devices: dict[str: pynetbox.models.dcim.Devices],
                      nsg_tags: dict[str: any]) -> list[dict[str: any]]:
    """
    Make payload for nsg tags POST request

    :param nbox_devices: list of netbox devices
    :param nsg_tags: list of existing devices tags
    :return:  list of tags to update
    """
    tags = []
    for address, device in nbox_devices.items():
        n_tags = nsg_tags.get(address, {})
        row = {"category": "device",
               "device": {"address": address},
               "tags": []
               }
        if not n_tags or [f"{k}.{v}" for k, v in device.nsg_tags.items() if n_tags.get("tags", {}).get(k) != str(v)]:
            row["tags"] = [f"{k}.{v}" for k, v in device.nsg_tags.items()]
        if n_tags.get("id"):
            row["device"] = {"id": n_tags.get("id")}
        if row.get("tags"):
            tags.append(row)
    return tags


def make_remove_tag_dict(nsg_devices: dict[str], nsg_tags: dict[str: any]) -> list[dict[str: any]]:
    """
    Make payload for nsg tags POST request

    :param nsg_devices: list of nsg devices to delete
    :param nsg_tags: list of existing devices tags
    :return:  list of devices witch tags to remove
    """
    tags = []
    for ip in nsg_devices:
        if nsg_tags.get(ip):
            row = {"category": "device",
                   "device": {"address": ip},
                   "tags": []
                   }
            tags.append(row)
    return tags


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--netbox-url', required=False)
    parser.add_argument('--netbox-token', required=False)
    parser.add_argument('--nsg-url', required=False)
    parser.add_argument('--nsg-token', required=False)
    parser.add_argument('--channel', required=False,
                        help='NetSpyGlass communication channel name to use with all imported devices')
    parser.add_argument('--config', required=False, help='Config yaml file that lists the netbox query options')
    parser.add_argument('--netid', required=False,
                        default=1,
                        help='NetSpyGlass network id, usually "1" (default=1)')
    parser.add_argument('--interval', required=False,
                        default=300,
                        help='Poll Netbox and NetSpyGlass at this interval (in seconds). (default=300)')
    pa = parser.parse_args()
    update_from_env(pa)
    urllib3.disable_warnings()

    nsgnb = NsgNetboxIntegration(pa)
    nsgnb.log_args()
    nsgnb.start()
