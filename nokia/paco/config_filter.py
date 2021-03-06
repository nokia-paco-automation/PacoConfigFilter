"""
This is a module that removes the parts from the pacoparser generated config which are not considered base config.
These config parts will further be handled by other tools and will therefore not be pushed by the initial configuration process.
"""
import argparse
import copy
import json
import os
import sys
import logging
from typing import List

# define the NetworkInsatnces to keep
# used in contains match, no need to define the exact name of the NI
keep_nis = ['infrastructure', "default"]


def process(i: str, o: str):
    """
    The meta process of stripping down the config.

    If o is None, the config is printed to the cli.

    :param i: the input file as string
    :param o: the output file as string or None
    :return: None
    """
    data = load_data(i)
    drop_nis(data)
    in_use_interfaces = deduce_in_use_interfaces(data)
    remove_bfd_interfaces(in_use_interfaces, data)
    remove_interfaces(in_use_interfaces, data)
    finish(data, o)


class Interface:
    """
    This is just an helper container to store interface infos (interface name and unit / index number)
    Maybe even overkill ... but we can.
    """
    def __init__(self, interface_name: str, unit: int):
        self.interface_name = interface_name
        self.unit = unit

    @staticmethod
    def new_interface_from_string(s: str):
        parts = s.split(".")
        return Interface(parts[0], int(parts[1]))

    def config_rep(self):
        return f"{self.interface_name}.{self.unit}"

    def __str__(self):
        return f"IRB: {self.interface_name}, Unit: {self.unit}"

    def __repr__(self):
        return self.__str__()


def remove_interfaces(interfaces: List[Interface], data):
    """
    Remove all interfaces other then the given irbs.

    :param interfaces: The interfaces to keep
    :param data: The config
    :return: None
    """
    result = {}

    for entry in data['interface']:

        # add all ethernet interfaces
        if "ethernet" in entry['name']:
            interf = copy.deepcopy(entry)
            interf['subinterface'] = []
            result[entry['name']] = interf

        # process interfaces with subinterfaces
        for interface in interfaces:
            if entry['name'] == interface.interface_name:
                if entry['name'] not in result:
                    interf = copy.deepcopy(entry)
                    interf['subinterface'] = []
                    result[entry['name']] = interf

                for subif in entry['subinterface']:
                    if subif['index'] == interface.unit:
                        interf['subinterface'].append(subif)

    data['interface'] = [x for x in result.values()]


def remove_bfd_interfaces(irbs, data):
    """
    Remove all other then the provided irb interfaces from the bfd part of the config.
    :param irbs: the irb interfaces to keep
    :param data: the config
    :return: None
    """
    match = []
    for entry in data['bfd']['subinterface']:
        for irb in irbs:
            if entry['id'] == irb.config_rep():
                match.append(entry)
    data['bfd']['subinterface'] = match


def deduce_in_use_interfaces(data):
    """
    Figure out what the IRB interfaces are in the (remaining) NetworkInstances
    :param data: the config blob
    :return: None
    """
    interfs = set()
    for entry in data['network-instance']:
        for interface in entry['interface']:
            interfs.add(interface['name'])

    result = []
    for x in interfs:
        result.append(Interface.new_interface_from_string(x))
    return result


def finish(data, o: str):
    """
    Finish the process by writing the data to disk.

    :param data: the python struct that is to be written to the file
    :param o: the ouput filename
    :return: None
    """
    if o is not None:
        with open(o, "w+") as outfile:
            json.dump(data, outfile, indent="  ")
    else:
        print(json.dumps(data, indent="  "))


def drop_nis(data):
    """
    Delete all the Network instances that do not match the "keep_nis" as substrings of the NI name.
    :param data: The switch config. It will be updated in place
    :return: None
    """
    result = []
    for entry in data['network-instance']:
        for match_name_part in keep_nis:
            if match_name_part in entry['name']:
                result.append(entry)
    data['network-instance'] = result


def load_data(i: str):
    """
    Load data from the given file.
    :param i: filename with path
    :return: the json data
    """
    if not os.path.isfile(i):
        logging.error(f"Inputfile {i} does not exist.")
        sys.exit(1)
    with open(i, 'r') as file:
        data = json.load(file)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Filter PacoParser Full Config for Base Bootstrap Config')
    parser.add_argument('-i', metavar='FILE', required=True, type=str, help='Input file / Paco Full Switch Config')
    parser.add_argument('-o', metavar='FILE', required=False, type=str, help='Output file', )

    args = parser.parse_args()

    process(args.i, args.o)
