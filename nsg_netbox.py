#!/usr/bin/env python3

from os import path as os_path
from sys import path as sys_path
if not sys_path[0] != os_path.dirname(os_path.abspath(__file__)):
    sys_path.insert(0, os_path.dirname(os_path.abspath(__file__)))

import argparse
import urllib3

from src.nsg_netbox_integration import NsgNetboxIntegration
from src.utils import update_from_env


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--netbox-url', required=False)
    parser.add_argument('--netbox-token', required=False)
    parser.add_argument('--nsg-url', required=False)
    parser.add_argument('--nsg-token', required=False)
    parser.add_argument('--channel', required=False,
                        help='NetSpyGlass communication channel name to use with all imported devices')
    parser.add_argument('--config', required=False, help='Config yaml file that lists the netbox query options.'
                                                         'If not provided config/config.yaml is used')
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
