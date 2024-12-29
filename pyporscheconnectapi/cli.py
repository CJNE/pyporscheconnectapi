#!/usr/bin/python

"""Command line interface for Porsche Connect API functions."""

import argparse
import asyncio
import configparser
import json
import logging
import sys
from getpass import getpass
from pathlib import Path

from pyporscheconnectapi.account import PorscheConnectAccount
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.exceptions import PorscheWrongCredentialsError
from pyporscheconnectapi.remote_services import RemoteServices

vehicle_commands = {
    "battery": "Prints the main battery level (BEV)",
    "capabilities": "Get vehicle capabilities",
    "chargingprofile": "Update parameters in configured charging profile",
    "climatise_off": "Stop remote climatisation",
    "climatise_on": "Start remote climatisation",
    "connected": "Check if vehicle is on-line",
    "currentoverview": "Get stored overview for vehicle",
    "direct_charge_off": "Disable direct charging",
    "direct_charge_on": "Enable direct charging",
    "doors_and_lids": "List status of all doors and lids",
    "flash_indicators": "Flash indicators",
    "honk_and_flash": "Flash indicators and sound the horn",
    "location": "Show location of vehicle",
    "lock_vehicle": "Lock vehicle",
    "pictures": "Get vehicle pictures url",
    "storedoverview": "Poll vehicle for current overview",
    "tire_status": "Check if tire pressure are ok",
    "tire_pressures": "Get tire pressure readings",
    "trip_statistics": "Get trip statistics from backend",
    "unlock_vehicle": "Unlock vehicle",
    "vehicle_closed": "Check if all doors and lids are closed",
}

try:
    from rich.console import Console

    console = Console()
    printc = console.print
except ImportError:
    pass

logging.basicConfig()
logging.root.setLevel(logging.WARNING)

_LOGGER = logging.getLogger(__name__)


async def battery(vehicle, _args):
    """Get vehicle battery state of charge (%)."""
    await vehicle.get_stored_overview()
    return vehicle.main_battery_level


async def capabilities(vehicle, _args):
    """Get vehicle capabilities."""
    await vehicle.get_capabilities()
    return vehicle.capabilities


async def chargingprofile(vehicle, args):
    """Manipulate charging profile."""
    await vehicle.get_stored_overview()
    service = RemoteServices(vehicle)
    result = await service.update_charging_profile(
        profile_id=args.profileid,
        minimum_charge_level=args.minimumchargelevel,
    )
    return result.status


async def climatise_off(vehicle, _args):
    """Stop climatisation."""
    service = RemoteServices(vehicle)
    result = await service.climatise_off()
    return result.status


async def climatise_on(vehicle, _args):
    """Start climatisation."""
    service = RemoteServices(vehicle)
    result = await service.climatise_on()
    return result.status


async def connected(vehicle, _args):
    """Get vehicle on-line status."""
    await vehicle.get_current_overview()
    return vehicle.connected


async def currentoverview(vehicle, _args):
    """Get current overview from vehicle."""
    await vehicle.get_current_overview()
    return vehicle.data


async def direct_charge_off(vehicle, _args):
    """Disable direct charging."""
    service = RemoteServices(vehicle)
    result = await service.direct_charge_off()
    return result.status


async def direct_charge_on(vehicle, _args):
    """Enable direct charging."""
    service = RemoteServices(vehicle)
    result = await service.direct_charge_on()
    return result.status


async def doors_and_lids(vehicle, _args):
    """Get stored status of doors and lids from backend."""
    await vehicle.get_stored_overview()
    return vehicle.doors_and_lids


async def flash_indicators(vehicle, _args):
    """Flash the indicators briefly."""
    service = RemoteServices(vehicle)
    result = await service.flash_indicators()
    return result.status


async def honk_and_flash(vehicle, _args):
    """Honk and flash the indicators briefly."""
    service = RemoteServices(vehicle)
    result = await service.honk_and_flash_indicators()
    return result.status


async def location(vehicle, _args):
    """Get the location of the vehicle."""
    await vehicle.get_stored_overview()
    return vehicle.location


async def lock_vehicle(vehicle, _args):
    """Lock the vehicle."""
    service = RemoteServices(vehicle)
    result = await service.lock_vehicle()
    return result.status


async def pictures(vehicle, _args):
    """Get pictures (uri) of the vehicle."""
    await vehicle.get_picture_locations()
    return vehicle.picture_locations


async def storedoverview(vehicle, _args):
    """Get stored overview from back-end."""
    await vehicle.get_stored_overview()
    return vehicle.data


async def tire_status(vehicle, _args):
    """Get tire pressure status from back-end."""
    await vehicle.get_stored_overview()
    return vehicle.tire_pressure_status


async def tire_pressures(vehicle, _args):
    """Get tire pressures from back-end."""
    await vehicle.get_stored_overview()
    return vehicle.tire_pressures


async def trip_statistics(vehicle, _args):
    """Get pictures (uri) of the vehicle."""
    await vehicle.get_trip_statistics()
    return vehicle.trip_statistics


async def unlock_vehicle(vehicle, args):
    """Unock the vehicle."""
    service = RemoteServices(vehicle)
    result = await service.unlock_vehicle(args.pin)
    return result.status


async def vehicle_closed(vehicle, _args):
    """Check with backend if doors and lids are closed."""
    await vehicle.get_stored_overview()
    return vehicle.vehicle_closed


async def main(args):
    """Get arguments from parser and run command."""
    try:
        with Path.open(args.session_file) as json_file:
            token = json.load(json_file)
    except FileNotFoundError:
        token = {}
    except json.decoder.JSONDecodeError:
        token = {}

    if args.debug:
        logging.root.setLevel(logging.DEBUG)

    email = args.email or input("Please enter Porsche Connect email: ")
    password = args.password or getpass()

    connection = Connection(email, password, token=token)
    controller = PorscheConnectAccount(connection=connection)

    response = {}
    try:
        if args.command == "list":
            vehicles = await controller.get_vehicles()
            for vehicle in vehicles:
                response = response | vehicle.data
        elif args.command == "token":
            response = controller.token
        elif args.vin is not None:
            vins = [args.vin]
        elif args.all:
            vehicles = await controller.get_vehicles()
            vins = (v.vin for v in vehicles)
        else:
            sys.exit("--vin or --all is required")
        for vin in vins:
            vehicle = await controller.get_vehicle(vin)
            if vehicle is not None:
                response = await globals()[args.func](vehicle, args)
    except PorscheWrongCredentialsError as e:
        sys.exit(e.message)
    else:
        printc(response)
    await connection.close()
    with Path.open(args.session_file, "w", encoding="utf-8") as json_file:
        json.dump(connection.token, json_file, ensure_ascii=False, indent=2)


def add_arg_vin(parser):
    """Add vin to the argument parser."""
    group = parser.add_mutually_exclusive_group(
        required=True,
    )
    group.add_argument("-v", "--vin", dest="vin", default=None)
    group.add_argument("-a", "--all", dest="all", action="store_true")


def cli():
    """Get configuration parameters and command line argumentsn and run main loop."""
    config = configparser.ConfigParser()
    config["porsche"] = {
        "email": "",
        "password": "",
        "session_file": ".session",
    }
    config.read([".porscheconnect.cfg", Path("~/.porscheconnect.cfg").expanduser()])
    parser = argparse.ArgumentParser(description="Porsche Connect CLI")
    subparsers = parser.add_subparsers(help="command help", dest="command")

    parser.add_argument("-d", "--debug", dest="debug", action="store_true")
    parser.add_argument(
        "-e",
        "--email",
        dest="email",
        default=config.get("porsche", "email"),
    )
    parser.add_argument(
        "-p",
        "--password",
        dest="password",
        default=config.get("porsche", "password"),
    )
    parser.add_argument(
        "-s",
        "--sessionfile",
        dest="session_file",
        default=config.get("porsche", "session_file"),
    )

    subparsers.add_parser("list")
    subparsers.add_parser("token")

    for vcmd, vdesc in vehicle_commands.items():
        parser_command = subparsers.add_parser(vcmd, help=vdesc)
        parser_command.set_defaults(func=vcmd)
        add_arg_vin(parser_command)
        if vcmd == "unlock_vehicle":
            parser_command.add_argument(
                "-n",
                "--pin",
                required=True,
                dest="pin",
                default=None,
            )
        if vcmd == "chargingprofile":
            parser_command.add_argument(
                "--profileid",
                dest="profileid",
                type=int,
                required=False,
                help="Profile id",
            )
            parser_command.add_argument(
                "--chargelevel",
                dest="minimumchargelevel",
                type=int,
                required=False,
                default=None,
                help="Minimum charge level",
            )
            parser_command.add_argument(
                "--profileactive",
                dest="profileactive",
                type=bool,
                required=False,
                default=None,
                help="Profile active status",
            )

    args = parser.parse_args()

    if args.command:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main(args))
    else:
        parser.print_help(sys.stderr)
