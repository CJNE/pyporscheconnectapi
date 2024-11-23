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

vehicle_commands = ["capabilities", "currentoverview", "storedoverview"]

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
                    if args.command == "currentoverview":
                        await vehicle.get_current_overview()
                        print(json.dumps(vehicle.data, indent=2))
                    elif args.command == "storedoverview":
                        await vehicle.get_stored_overview()
                        print(json.dumps(vehicle.data, indent=2))
                    elif args.command == "chargingprofile":
                        service = RemoteServices(vehicle)
                        await service.updateChargingProfile(
                            profileId=args.profileid,
                            minimumChargeLevel=args.minimumchargelevel,
                        )
                    elif args.command == "capabilities":
                        data = await vehicle.get_capabilities()
                        print(json.dumps(vehicle.capabilities, indent=2))

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
        add_arg_vin(subparsers.add_parser(vc))

    parser_command_chargingprofile = subparsers.add_parser(
        "chargingprofile", help="Update parameters in configured charging profile"
    )
    add_arg_vin(parser_command_chargingprofile)
    parser_command_chargingprofile.add_argument(
        "--profileid", dest="profileid", type=int, required=False, help="Profile id"
    )
    parser_command_chargingprofile.add_argument(
        "--chargelevel",
        dest="minimumchargelevel",
        type=int,
        required=False,
        default=None,
        help="Minimun charge level",
    )
    parser_command_chargingprofile.add_argument(
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
