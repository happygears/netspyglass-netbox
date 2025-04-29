#!/usr/bin/env python3

import argparse
import ipaddress
import logging
import os
import re
import sched
from sys import path as sys_path
import time
import yaml
import socket
from src import nsgapi

from src.netbox_client import NetboxClient, NboxRecord, NboxDevice
from src.utils import make_add_tag_dict, make_remove_tag_dict
from requests.exceptions import RequestException


class NsgNetboxIntegration:
    """
    Main class to fetch tags from Netbox and save to NSG API
    """
    def __init__(self, args: argparse.Namespace) -> None:

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ])

        for key in ("netbox_url", "netbox_token", "nsg_url", "nsg_token"):
            if not getattr(args, key):
                raise ValueError(f"property {key} not defined")
        self.args = args
        self.domain = None
        self.log = logging.getLogger('nsg-netbox')
        app_root = sys_path[0]
        self.config = self.load_config(os.path.join(app_root, self.args.config)
                                       or os.path.join(app_root, "config", "config.yaml"))
        if not self.config:
            raise ValueError("config not laded")
        nsg_tags = self.config.get("nsgTags") or {}
        self.nbox_tags = set(x for x in nsg_tags.keys())

        self.netbox = NetboxClient(url=self.args.netbox_url, token=self.args.netbox_token)
        self.nsg = nsgapi.NsgAPI(self.log, self.args.nsg_url, self.args.nsg_token, self.args.netid)

        version = self.netbox.version
        if not version:
            raise ValueError("can not get netbox version")
        if version > 2.6:
            self.active = "active"
        else:
            self.active = 1
        self.domain = self.config.get('domain')
        self.channels = {}
        if args.channel:
            self.channels["*"] = [args.channel, ]
        else:
            self.channels = self.config.get("default_channels", {})
        if not self.channels:
            raise ValueError("channels not specified")
        self.scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)

        self.interval_sec = int(args.interval)

    def load_config(self, config_file: str) -> dict or None:
        """
        load and parse local config
        :param
            config_file: config file path
        :return: parsed config dict or None
        """
        try:
            with open(config_file, 'r') as f:
                conf = yaml.safe_load(f)
                # conf.update(self.resolve_refs(conf))
                for _, val in conf.items():
                    if isinstance(val, dict):
                        for key, item in val.items():
                            if key == "path":
                                parts = item.split(".")
                                if parts[0].startswith("$"):
                                    conf[parts[0][1:]] = True
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
            self.log.error(f"Netbox-NetSpyGlass schedule starts error: {e}")
            return

    def run(self):
        """
        get list of devices in Netbox, then get list of devices in NetSpyGlass, compare
        and update devices in NetSpyGlass. Use `primary_ip` attribute (Netbox) to match devices
        """
        def wait_tasks_done():
            # wait for nsg tasks finished
            while True:
                tasks1 = self.nsg.get_tasks()
                if not tasks1:
                    break
                time.sleep(2)

        try:
            # schedule next run
            self.scheduler.enter(delay=self.interval_sec, priority=1, action=self.run)

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
                category = i.get("category")
                key = i.get("device", {}).get("address")
                device_id = i.get("device", {}).get("id")
                if category == "device":
                    if not tags.get(key):
                        tags[key] = {"device_id": device_id,
                                     "tags": set(i.get("tags", {}))}
                    else:
                        try:
                            tags[key]["tags"].update(i.get("tags", []))
                        except TypeError as e:
                            self.log.error(f"tags dict update Type error: {e}")
                            pass
                        except ValueError as e:
                            self.log.error(f"tags dict update Value error: {e}")
                            pass
                elif category == "interface":
                    name = i.get("component", {}).get("name")
                    idx = i.get("component", {}).get("index")
                    if not tags.get(key):
                        tags[key] = {"device_id": device_id,
                                     "tags": set(),
                                     "interfaces": {name: {
                                         "index": idx,
                                         "tags": set(i.get("tags", {}))}}
                                     }
                    else:
                        iname = i.get("component", {}).get("name")
                        iface = tags[key].get("interfaces", {}).get(iname, {})
                        if not tags[key].get("interfaces", {}):
                            tags[key]["interfaces"] = {}
                        if iface.get("tags"):
                            iface["tags"].update(i.get("tags", {}))
                        else:
                            tags[key]["interfaces"][name] = {"index": idx, "tags": set(i.get("tags", {}))}

            nb_dev_set = set(nbox_devices.keys())
            nsg_dev_set = set(nsg_devices.keys())
            to_add = set.difference(nb_dev_set, nsg_dev_set)  # set of addresses as strings
            to_remove = set.difference(nsg_dev_set, nb_dev_set)  # set of addresses as strings

            if to_remove:
                self.log.info('DELETE devices: {0}'.format(to_remove))
                remove_tags = make_remove_tag_dict(nsg_devices=to_remove, nsg_tags=tags)
                if remove_tags:
                    for i in remove_tags:
                        self.log.info(f" tags list to delete: {i}")
                    self.nsg.post_device_tags(tag_list=remove_tags, operation="DELETE")
                self.nsg.delete_devices(list(nsg_devices[addr]['id'] for addr in to_remove))

            if to_add:
                payload = list(self.make_add_device_dict(addr, nbox_devices[addr]) for addr in to_add)
                self.log.info('ADD devices:    {0}'.format(to_add))
                added_devices = self.nsg.add_devices(payload)
                nsg_devices.update(**added_devices)

            tag_list = make_add_tag_dict(nbox_devices=nbox_devices,
                                         nsg_tags=tags)
            # wait for devices added to nsg
            wait_tasks_done()

            if tag_list:
                for i in tag_list:
                    ip = i.get("device", {}).get("address")
                    device_id = nsg_devices.get(ip, {}).get("id")
                    if device_id:
                        i["device"].update(id=device_id)
                    self.log.info(f" tags list to update: {i}")
                    i["tags"] = list(i["tags"])
                self.nsg.post_device_tags(tag_list=tag_list)
            else:
                self.log.info(f" no devices with new/changed tags found")

        except RequestException as e:
            self.log.error('Netbox API call has failed: {0}'.format(e))
        except Exception as e:
            self.log.exception('Unknown exception: %s', e)

    def get_netbox_devices(self) -> dict[str: NboxDevice]:
        """
        Get list of devices from Netbox
        :return: map of Netbox devices {ip_address: device}
        """
        def resolve_ip(host_name: str) -> str or None:
            try:
                dns_ip = socket.gethostbyname(host_name)
                if dns_ip:
                    return dns_ip
                else:
                    return None
            except socket.gaierror as e:
                self.log.error(f"get_netbox_devices: can't resolve device ip: {host_name}: {e}")
                return None

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
        # self._cache["tags"] = self.netbox.get(entity="tags")
        devices = self.netbox.get(entity="devices", filters=filters)
        devices_idx = {}
        devices_with_ifaces = []
        for device in devices:
            nbox_device = NboxDevice(device)
            devices_idx[nbox_device.id] = nbox_device
            ip = self.get_primary_ip(device)
            if ip:
                result[ip] = device
            else:
                ip = resolve_ip(nbox_device.name)
                if not ip and self.domain:
                    ip = resolve_ip(f"{nbox_device.name}.{self.domain}")
                if not ip:
                    self.log.error(f"get_netbox_devices: cant resolve ip address for device {nbox_device.name}")
                    continue
            nbox_device.primary_ip = ip
            result[ip] = nbox_device
            nbox_device.nsg_tags = self.extract_tags(nbox_device)
            if nbox_device.interface_count:
                devices_with_ifaces.append(nbox_device)
        if hasattr(self.args, "ifaces") and self.args.ifaces:  # proceed interfaces turned off now
            interfaces = self.get_neetbox_interfaces(device=devices_with_ifaces)
            for iFace in interfaces:
                id_ = iFace.device_id
                if not id_:
                    continue
                if not devices_idx.get(id_):
                    self.log.warning(f"get_netbox_devices: interface {iFace} belongs to unknown device {id_}")
                devices_idx[id_].iFaces_tags[iFace.name] = iFace.nsg_tags
        return result

    def get_neetbox_interfaces(self, device: NboxDevice or list[NboxDevice]) -> list[NboxRecord]:
        """
        Get list og interfaces filtered by devices
        :param device: list of devices which interfaces to get
        :return: list of interfaces with found tags
        """
        filters = {}
        if isinstance(device, NboxRecord):
            filters["device_id"] = [device.id]
        elif isinstance(device, (list, tuple, set)):
            filters["device_id"] = [x.id for x in device]
        else:
            raise ValueError("device_id should be NboxDevice or iterable")

        iFaces = self.netbox.get(entity="interfaces", filters=filters)
        if not iFaces:
            return []
        result = []
        for iFace in iFaces:
            iface = NboxRecord(iFace)
            tags = self.extract_tags(iface, "nsgInterfaceTags")
            iface.nsg_tags = tags
            result.append(iface)
        return result

    @staticmethod
    def get_primary_ip(device: NboxDevice) -> str or None:
        primary_ip = device.get("primary_ip", device.get("primary_ip4"))
        if isinstance(primary_ip, dict):
            primary_ip = primary_ip.get("address")
        return str(ipaddress.ip_interface(primary_ip).ip) if primary_ip else None

    def condition(self, device: NboxDevice):
        if self.config and self.config.get('blacklist'):
            return device.primary_ip is not None and not any([tag in device.tags for tag in self.config['blacklist']])
        else:
            return device.primary_ip is not None

    def make_add_device_dict(self, addr: str, nb_device: NboxDevice) -> dict:
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

        # return {'name': nb_device.name, 'address': addr, 'channels': ", ".join(channels)}  # v2 api
        return {'name': nb_device.name, 'address': addr, 'polling': ", ".join(channels)}  # v3 api

    def extract_tags(self, instance: NboxRecord, tag_type: str = "nsgTags") -> set[str]:
        """
        Find all tags described in config from netbox Record instance (Device)

        :param tag_type: type of tags: nsgTags, nsgInterfaceTags
        :param instance: netbox record
        :return: dict of found tags
        """
        result = set()
        for tag, attrs in self.config.get(tag_type, {}).items():
            if attrs and isinstance(attrs, dict):
                if attrs.get("path"):
                    value = self.extract_tag_1(instance, attrs)
                    # self.log.info(f"{f'{instance._type}:{instance}':30} {tag:20} : {value}")
                else:
                    continue
                if value:
                    if isinstance(value, set):
                        result.update((f"{tag}.{x}" for x in value))
                    else:
                        result.add(f"{tag}.{value}")

        return result

    def extract_tag_1(self, inst: NboxRecord,
                      tag: dict[str: str]) -> set[str or int or float]:
        """
        Find given tags in the record

        :param inst: netbox record
        :param tag: tag description from config
        :return: found tag or None
        """

        def transform(value: str or int or float, tag_: dict[str:str]):
            result = value
            regexp = tag_.get("regexp")
            if regexp:
                from re import findall
                cur1 = findall(regexp, value)
                if cur1:
                    result = cur1[0]

            subst = tag_.get("mapping")
            if subst:
                if isinstance(subst, dict):
                    result = subst.get(value, subst.get("*", value))

            transformation = tag_.get("transform")
            if transformation and isinstance(result, str):
                result = result.strip()
                if transformation.lower() == "upper":
                    return result.upper()
                elif transformation.lower() == "lower":
                    return result.lower()
                if transformation.lower() == "capitalize":
                    return result.capitalize()
                return result.replace(" ", "_")
            return result

        res = set()
        if not isinstance(tag, dict):
            return res
        path = tag.get("path")
        if not path:
            return res
        nodes = path.split(".") if isinstance(path, str) else path
        if len(nodes) == 0:
            return res
        try:
            cur = getattr(inst, nodes[0])
            if cur is None:
                return res
        except AttributeError:
            return res

        if len(nodes) == 1:
            if isinstance(cur, NboxRecord):
                res.add(transform(f"{cur}", tag))
            elif isinstance(cur, (list, tuple, set)):
                for i in cur:
                    if isinstance(i, NboxRecord):
                        res.add(transform(f"{i}", tag))
                    else:
                        res.add(transform(i, tag))
            else:
                res.add(transform(cur, tag))
        else:
            if isinstance(cur, NboxRecord):
                res.update(self.extract_tag_1(cur, {**tag, "path": nodes[1:]}))
            elif isinstance(cur, (list, tuple, set)):
                for i in cur:
                    if isinstance(i, NboxRecord):
                        res.update(self.extract_tag_1(i, {**tag, "path": nodes[1:]}))
                    else:
                        res.add(transform(i, {**tag, "path": nodes[1:]}))

        return res

