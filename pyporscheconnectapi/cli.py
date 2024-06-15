import argparse
import asyncio
import configparser
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from pyporscheconnectapi.exceptions import WrongCredentials
import os
import sys
import logging
import json
from getpass import getpass

try:
    from rich import print
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
    conn = Connection(email, password, token=token)

    client = Client(conn)

    try:
        if args.command == "list":
            data = await client.getVehicles()
            print(json.dumps(data, indent=2))
        elif args.command == "token":
            data = await client.getToken()
            print(json.dumps(data, indent=2))
        else:
            vins = []
            if args.vin is not None:
                vins = [args.vin]
            elif args.all:
                vehicles = await client.getVehicles()
                vins = map(lambda v: v["vin"], vehicles)
            else:
                sys.exit("--vin or --all is required")
            for vin in vins:
                data = {}
                if args.command == "overview":
                    if args.nowait:
                        data = await client.getStoredOverview(vin)
                    else:
                        data = await client.getCurrentOverview(vin)
                elif args.command == "capabilities":
                    data = await client.getCapabilities(vin)
                print(json.dumps(data, indent=2))

    except WrongCredentials as e:
        sys.exit(e.message)

    await conn.close()
    with open(args.session_file, "w", encoding="utf-8") as json_file:
        json.dump(conn.token, json_file, ensure_ascii=False, indent=2)


def add_arg_vin(parser):
    group = parser.add_mutually_exclusive_group(
        required=True,
    )
    group.add_argument("-v", "--vin", dest="vin", default=None)
    group.add_argument("-a", "--all", dest="all", action="store_true")


def add_arg_model(parser):
    parser.add_argument("-m", "--model", dest="model", default=None)


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

    parser_command_list = subparsers.add_parser("list")

    parser_command_capabilities = subparsers.add_parser("capabilities")
    add_arg_vin(parser_command_capabilities)

    parser_command_overview = subparsers.add_parser("overview")
    add_arg_vin(parser_command_overview)

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))
