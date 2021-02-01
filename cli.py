#! /usr/bin/env python3

import argparse
import asyncio
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from sys import argv
import logging
import json

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)


parser = argparse.ArgumentParser(description='Porsche Connct CLI.')
parser.add_argument('command', choices=['list', 'overview', 'maintenance', 'summary', 'capabilities'])
parser.add_argument('-e', '--email', dest='email', required=True)
parser.add_argument('-p', '--password', dest='password', required=True)
parser.add_argument('-s', '--sessionfile', dest='session_file', default='.session')
parser.add_argument('-v', '--vin', dest='vin', default=None)
parser.add_argument('-a', '--all', dest='all', action='store_true')
parser.add_argument('-c', '--country', dest='country', default='de')
parser.add_argument('-l', '--language', dest='language', default='DE')

args = parser.parse_args()


try:
    with open(args.session_file) as json_file:
        tokens = json.load(json_file)
except FileNotFoundError:
    tokens = {}
except json.decoder.JSONDecodeError:
    tokens = {}

async def main():
    conn = Connection(args.email, args.password, tokens=tokens, country=args.country, language=args.language)
    client = Client(conn)

    if args.command == "list":
        vehicles = await client.getVehicles()
        print(json.dumps(vehicles, indent=2))
    else:
        vins = []
        if args.vin is not None: vins = [ args.vin ]
        elif args.all:
            vehicles = await client.getVehicles()
            vins = map(lambda v : v['vin'], vehicles)
        else:
            die("--vin or --all is required")
        for vin in vins:
            if args.command == "overview":
                data = await conn.get(f"https://api.porsche.com/service-vehicle/se/sv_SE/vehicle-data/{vin}/stored")
                print(json.dumps(data, indent=2))
            elif args.command == "maintenance":
                data = await conn.get(f"https://api.porsche.com/predictive-maintenance/information/{vin}")
                print(json.dumps(data, indent=2))
            elif args.command == "summary":
                data = await conn.get(f"https://api.porsche.com/service-vehicle/vehicle-summary/{vin}")
                print(json.dumps(data, indent=2))
            elif args.command == "capabilities":
                data = await conn.get(f"https://api.porsche.com/service-vehicle/vcs/capabilities/{vin}")
                print(json.dumps(data, indent=2))


    await conn.close()
    with open(args.session_file, 'w', encoding='utf-8') as json_file:
        json.dump(conn.tokens, json_file, ensure_ascii=False, indent=2)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())

