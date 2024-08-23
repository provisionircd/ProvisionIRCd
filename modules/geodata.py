from handle.core import IRCD, Hook, Numeric
from urllib import request
import json
import ipaddress
from time import time


class GeoData:
    data = {}
    clients = {}
    process = []


def api_call(client):
    try:
        response = request.urlopen(f"https://ipapi.co/{client.ip}/json/", timeout=10)
        response_body = response.read()
        json_response = json.loads(response_body.decode())
        json_response["ircd_time_added"] = int(time())
        GeoData.data.update({client.ip: json_response})
        GeoData.clients[client] = json_response
        IRCD.write_data_file(GeoData.data, filename="geodata.json")
    except:
        pass
    GeoData.process.remove(client.ip)
    IRCD.remove_delay_client(client, "geodata")


def country_whois(client, whois_client, lines):
    if whois_client in GeoData.clients and "country_name" in GeoData.clients[whois_client] and 'o' in client.user.modes:
        line = (Numeric.RPL_WHOISSPECIAL, whois_client.name, f"is connecting from country: {GeoData.clients[whois_client]['country_name']}")
        lines.append(line)


def geodata_lookup(client):
    if not ipaddress.ip_address(client.ip).is_global:
        return
    if client.ip in GeoData.data:
        """ Assign cached data to this client. """
        GeoData.clients[client] = GeoData.data[client.ip]
        client.add_md(name="country", value=GeoData.data[client.ip]["country"], sync=1)
        return

    if client.ip not in GeoData.process:
        if client.local:
            IRCD.delay_client(client, 1, "geodata")
        GeoData.process.append(client.ip)
        IRCD.run_parallel_function(target=api_call, args=(client,))


def geodata_expire():
    changed = 0
    for entry in list(GeoData.data):
        added = GeoData.data[entry]["ircd_time_added"]
        if int(time() - added >= 2_629_744):
            changed = 1
            del GeoData.data[entry]
    if changed:
        IRCD.write_data_file(GeoData.data, filename="geodata.json")


def geodata_quit(client, reason):
    if client in GeoData.clients:
        del GeoData.clients[client]


def init(module):
    GeoData.data = IRCD.read_data_file("geodata.json")
    Hook.add(Hook.NEW_CONNECTION, geodata_lookup)
    Hook.add(Hook.REMOTE_CONNECT, geodata_lookup)
    Hook.add(Hook.LOCAL_QUIT, geodata_quit)
    Hook.add(Hook.WHOIS, country_whois)
    Hook.add(Hook.LOOP, geodata_expire)
