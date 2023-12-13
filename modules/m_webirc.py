"""
webirc support
"""
import ipaddress

from handle.core import IRCD, Command, Flag
from handle.validate_conf import conf_error
from handle.core import logging


class WebIRCConf:
    password = None
    options = []
    ip_whitelist = []


def post_load(module):
    if not (webirc_settings := IRCD.configuration.get_items("settings:webirc")):
        return conf_error("WebIRC module is loaded but settings:webirc block is missing in configuration file")

    password = None
    for entry in webirc_settings:
        entry_name = entry.path[1]
        entry_value = entry.path[2]
        if entry_name == "password":
            password = entry_value
        if entry_name == "options":
            WebIRCConf.options.append(entry_value)
        if entry_name == "ip_whitelist":
            for ip in entry.get_path("ip_whitelist"):
                if ip in WebIRCConf.ip_whitelist:
                    continue
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    conf_error(f"Invalid IP address '{ip}' in whitelisted_ip", item=entry)
                    continue
                WebIRCConf.ip_whitelist.append(ip)

    if not password:
        return conf_error(f"settings:webirc:password missing or invalid")

    WebIRCConf.password = password


def init(module):
    Command.add(module, cmd_webirc, "WEBIRC", 4, Flag.CMD_UNKNOWN)


def cmd_webirc(client, recv):
    if client.registered or recv[1] != WebIRCConf.password or client.ip not in WebIRCConf.ip_whitelist:
        return
    client.user.realhost = recv[3] if IRCD.get_setting("resolvehost") else recv[4]
    client.ip = recv[4]
    client.user.cloakhost = IRCD.get_cloak(client)
