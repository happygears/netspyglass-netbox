# netspyglass-netbox
NetSpyGlass - Netbox integration

This tool can be used to synchronize devices between Netbox (https://github.com/netbox-community/netbox) DCIM 
and NetSpyGlass (NSG) (https://www.netspyglass.com). Synchronization is unidirectional, that is, devices are 
copied from Netbox to NSG. The tool supports simple whitelist and blacklist filters based on Netbox
device tags and can run in the background, checking and synchronizing devices at specified interval.

## Usage

    $ ./nsg-netbox.py  -h
    usage: nsg-netbox.py [-h] --netbox-url NETBOX_URL --netbox-token NETBOX_TOKEN
                         --nsg-url NSG_URL --nsg-token NSG_TOKEN --channel CHANNEL
                         [--whitelist WHITELIST] [--blacklist BLACKLIST]
                         [--netid NETID] [--interval INTERVAL]
    
    optional arguments:
      -h, --help            show this help message and exit
      --netbox-url NETBOX_URL
      --netbox-token NETBOX_TOKEN
      --nsg-url NSG_URL
      --nsg-token NSG_TOKEN
      --channel CHANNEL     NetSpyGlass communication channel name to use with all
                            imported devices
      --whitelist WHITELIST
                            the name of the Netbox device tag that will be passed
                            to `dcim.devices.filter()` call to filter devices in
                            Netbox. Only devices that have this tag will be
                            synchronized to NetSpyGlass. Default is None, which
                            causes all devices present in Netbox to be
                            synchronized. At this time this can be only a single
                            tag name. Example: "--whitelist=nsg"
      --blacklist BLACKLIST
                            the name of the Netbox device tag that will be passed
                            to `dcim.devices.filter()` call to filter devices in
                            Netbox. Devices that have this tag will not be
                            synchronized to NetSpyGlass. Blacklist filter is
                            applied after the whitelist (if any). Default is None,
                            which turns this off and causes all devices that pass
                            whitelist will be synchronized. At this time this can
                            be only a single tag name. Example: "--
                            blacklist=nsg_ignore"
      --netid NETID         NetSpyGlass network id, usually "1" (default=1)
      --interval INTERVAL   Poll Netbox and NetSpyGlass at this interval (in
                            seconds). (default=300)
    
You will need URL and access token for both Netbox and NSG to set up authentication.

Parameter `--channel` describes communication channel NSG will use to poll devices added
by this tool. All added devices are assumed to support the same channel. See NSG documentation
for more details.

The `whitelist` and `blacklist` parameters take single word as a value, which is expected
to be a Netbox device tag. If parameter `--whitelist` is provided, only devices that have 
the whitelist tag will be added to NSG. If this paramete is missing, all devices found in
Netbox will be synchronized. Blacklist is applied after the whitelist and can be used to
suppress some of the devices even if they pass the whitelist filter.

Use parameter `--interval` to specify synchronization interval.

The tool, once started, does not detach itself from the shell in which it runs and
runs in the loop until stopped.

## Examples

    ./nsg-netbox.py --netbox-url=$NB_URL --netbox-token=$NB_TOKEN \
                    --nsg-url=$NSG_URL --nsg-token=$NSG_TOKEN \
                    --channel=v2public

this command will synchronize all devices between Netbox and NSG at 5 min interval (the default),
adding polling channel 'v2public' to all devices it adds to NSG. Note that the channel name
'v2public' must match one of the channels configured in NSG agent.

    ./nsg-netbox.py --netbox-url=$NB_URL --netbox-token=$NB_TOKEN \
                    --nsg-url=$NSG_URL --nsg-token=$NSG_TOKEN \
                    --channel=v2public \
                    --whitelist=nsg

The same as the above but only devices with Netbox device tag `nsg` will be synchronized

    ./nsg-netbox.py --netbox-url=$NB_URL --netbox-token=$NB_TOKEN \
                    --nsg-url=$NSG_URL --nsg-token=$NSG_TOKEN \
                    --channel=v2public \
                    --whitelist=nsg \
                    --blacklist=nsg_ignore

Only devices with Netbox device tag `nsg` will be synchronized, unless they also have tag `nsg_ignore`.
This setup allows you to mark a broad set of devices to synchronize, but then remove a few of them
if necessary, for example if they are under extended maintenance or have been taken offline temporarily 
for any other reason

