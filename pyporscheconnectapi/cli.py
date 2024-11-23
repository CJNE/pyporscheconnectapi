import argparse
import asyncio
import configparser
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.exceptions import PorscheWrongCredentials
from pyporscheconnectapi.account import PorscheConnectAccount
from pyporscheconnectapi.remote_services import RemoteServices
import os
import sys
import logging
import json
from getpass import getpass

vehicle_commands = {
    "capabilities": "Get vehicle capabilities",
    "currentoverview": "Get stored overview for vehicle",
    "storedoverview": "Poll vehicle for current overview",
    "trip_statistics": "Get trip statistics from backend",
    "pictures": "Get vehicle pictures url",
    "location": "Show location of vehicle",
    "climatise_on": "Start remote climatisation",
    "climatise_off": "Stop remote climatisation",
    "direct_charge_on": "Enable direct charging",
    "direct_charge_off": "Disable direct charging",
    "flash_indicators": "Flash indicators",
    "honk_and_flash": "Flash indicators and sound the horn",
    "lock_vehicle": "Lock vehicle",
    "unlock_vehicle": "Unlock vehicle",
    "chargingprofile": "Update parameters in configured charging profile",
}

try:
    from rich.console import Console

    console = Console()
    print = console.print
except ImportError:
    pass

logging.basicConfig()
logging.root.setLevel(logging.WARNING)

_LOGGER = logging.getLogger(__name__)


async def main(args):
    try:
        with open(args.session_file) as json_file:
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

    try:
        if args.command == "list":
            vehicles = await controller.get_vehicles()
            for vehicle in vehicles:
                print(vehicle)
                print(json.dumps(vehicle.data, indent=2))
        elif args.command == "token":
            data = controller.token
            print(json.dumps(data, indent=2))
        else:
            vins = []
            if args.vin is not None:
                vins = [args.vin]
            elif args.all:
                vehicles = await controller.get_vehicles()
                vins = map(lambda v: v.vin, vehicles)
            else:
                sys.exit("--vin or --all is required")
            for vin in vins:
                data = {}
                vehicle = await controller.get_vehicle(vin)
                if vehicle is not None:
                    if args.command == "capabilities":
                        data = await vehicle.get_capabilities()
                        print(json.dumps(vehicle.capabilities, indent=2))
                    elif args.command == "currentoverview":
                        await vehicle.get_current_overview()
                        print(json.dumps(vehicle.data, indent=2))
                    elif args.command == "storedoverview":
                        await vehicle.get_stored_overview()
                        print(json.dumps(vehicle.data, indent=2))
                    elif args.command == "trip_statistics":
                        await vehicle.get_trip_statistics()
                        print(json.dumps(vehicle.trip_statistics, indent=2))
                    elif args.command == "pictures":
                        await vehicle.get_picture_locations()
                        print(json.dumps(vehicle.picture_locations, indent=2))
                    elif args.command == "location":
                        await vehicle.get_stored_overview()
                        print(json.dumps(vehicle.location, indent=2))
                    elif args.command == "climatise_on":
                        service = RemoteServices(vehicle)
                        result = await service.climatise_on()
                        print(result.status)
                    elif args.command == "climatise_off":
                        service = RemoteServices(vehicle)
                        result = await service.climatise_off()
                        print(result.status)
                    elif args.command == "direct_charge_on":
                        service = RemoteServices(vehicle)
                        result = await service.direct_charge_on()
                        print(result.status)
                    elif args.command == "direct_charge_off":
                        service = RemoteServices(vehicle)
                        result = await service.direct_charge_off()
                        print(result.status)
                    elif args.command == "flash_indicators":
                        service = RemoteServices(vehicle)
                        result = await service.flash_indicators()
                        print(result.status)
                    elif args.command == "honk_and_flash":
                        service = RemoteServices(vehicle)
                        result = await service.honk_and_flash_indicators()
                        print(result.status)
                    elif args.command == "lock_vehicle":
                        service = RemoteServices(vehicle)
                        result = await service.lock_vehicle()
                        print(result.status)
                    elif args.command == "unlock_vehicle":
                        service = RemoteServices(vehicle)
                        result = await service.unlock_vehicle(args.pin)
                        print(result.status)
                    elif args.command == "chargingprofile":
                        await vehicle.get_stored_overview()
                        service = RemoteServices(vehicle)
                        result = await service.updateChargingProfile(
                            profileId=args.profileid,
                            minimumChargeLevel=args.minimumchargelevel,
                        )
                        print(result.status)

    except PorscheWrongCredentials as e:
        sys.exit(e.message)

    await connection.close()
    with open(args.session_file, "w", encoding="utf-8") as json_file:
        json.dump(connection.token, json_file, ensure_ascii=False, indent=2)


def add_arg_vin(parser):
    group = parser.add_mutually_exclusive_group(
        required=True,
    )
    group.add_argument("-v", "--vin", dest="vin", default=None)
    group.add_argument("-a", "--all", dest="all", action="store_true")


def cli():
    config = configparser.ConfigParser()
    config["porsche"] = {
        "email": "",
        "password": "",
        "session_file": ".session",
    }
    config.read([".porscheconnect.cfg", os.path.expanduser("~/.porscheconnect.cfg")])
    parser = argparse.ArgumentParser(description="Porsche Connect CLI")
    subparsers = parser.add_subparsers(help="command help", dest="command")

    parser.add_argument("-d", "--debug", dest="debug", action="store_true")
    parser.add_argument(
        "-e", "--email", dest="email", default=config.get("porsche", "email")
    )
    parser.add_argument(
        "-p", "--password", dest="password", default=config.get("porsche", "password")
    )
    parser.add_argument(
        "-s",
        "--sessionfile",
        dest="session_file",
        default=config.get("porsche", "session_file"),
    )

    parser.add_argument("--nowait", dest="nowait", action="store_true")

    subparsers.add_parser("list")
    subparsers.add_parser("token")

    for vc in vehicle_commands:
        parser_command = subparsers.add_parser(vc, help=vehicle_commands[vc])
        add_arg_vin(parser_command)
        if vc == "unlock_vehicle":
            parser_command.add_argument(
                "-n", "--pin", required=True, dest="pin", default=None
            )
        if vc == "chargingprofile":
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
