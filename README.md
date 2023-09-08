# ProSAFE VLAN Manager

This is a utility & library to manage VLANs on Netgear ProSAFE series switches.

Currently implemented and tested devices, and their firmware versions:

- GS108Ev3
    - V2.06.10EN
    - V2.06.24EN
- GS116Ev2
    - V2.6.0.48

## Intro

This utility/library gives you the ability to manage your VLANs in a declarative way, that is, __write your configuration, and the program will validate and apply it all in once__.

The web interface is convenient when you only have one switch to configure. But the web interface requires every modification to meet internal constraints. That will make changing pvids, adding/deleting VLANs a complex work to do, and you have to jump back and forth to adjust the settings.

With "ProSAFE VLAN Manager", you can automate every modification, and focus only on the network structure, released from the burden of manually configuring the switches.

You can apply your configuration with the following command:

```bash
# Note: you have to setup the environment before running this command
python -m prosafe apply -c path/to/your/config.toml
```

The format for configuration is in section [Example configuration](#example-configuration).

About more information on how to use this tool in command line, print the help message with the commands below.

```bash
python -m prosafe --help
python -m prosafe apply --help
```

## How does this work?

This program is basically a "spider" that mimic user actions on the web interface. I guess this answer is clear enough.

Netgear has their own configuration utility and protocol, called "ProSAFE Plus Utility" and "NSDP"(Netgear Switch Discovery Protocol). But they are proprietary and obsolete/EOL. Using the program or analysing the protocol doesn't improve the situation.

So, I just write my own program to automate all the actions I need to perform.

## Supported actions

All 802.1Q VLAN operations, including:

- Add/delete VLAN
- Change port pvid
- Change ports membership in a VLAN
    - Including *T*agged, *U*ntagged, Ignored(internal state)

And extra functions like:

- Read switch information
- ~~Export statistics~~ __TBD__

Note the tool itself won't turn on the advanced 802.1Q VLAN function for you. You have to manually enable it, as it may break your current network configuration.

## Example configuration

The configuration file is written in __TOML__.

```toml
[base]
anykey = "won't be parsed, everything important are under 'switches'"

[switches.switch1]
# switch1 is the switch's nickname, only useful in logs and config backups
# multiple switches can be defined, so long as they have different names
address = "192.168.0.101"
password = "password1"
model = "gs108ev3"

[switches.switch1.ports]
# vlans: port vlan membership, defaults to 'not participate'/IGNORED,
# format: vlan id + port status
# U: Untagged
# T: Tagged
#
# Any port omitted will be allocated to VLAN{original pvid}.
1 = { pvid = 1,     vlans = ['1T', '2T', '23T']}
2 = { pvid = 2,     vlans = ['2U']}
3 = { pvid = 1,     vlans = ['1T', '23T']}
4 = { pvid = 1,     vlans = ['1U']}
5 = { pvid = 1,     vlans = ['1U']}
6 = { pvid = 1,     vlans = ['1U']}
7 = { pvid = 99,    vlans = ['99U']}

# this is also a valid configuration format for toml
# just a reminder
[switches.switch1.ports.8]
pvid = 1
vlans = ['1U']

[switches.switch2]
address = "192.168.0.239"
password = "password2"
model = "gs116ev2"

[switches.switch2.ports]
1 = { pvid = 1,     vlans = ['1T']}
2 = { pvid = 2,     vlans = ['2U']}
3 = { pvid = 1,     vlans = ['1U']}
```
