## Description

A modern IRCd written in Python 3.10. Support for lower versions has officially been dropped.
<br>
Massive code overhaul, so there might still be some issues.

## Installation

### Without Docker

Install the required packages:
```pip3 install -r requirements.txt```

Edit <b>conf/examples/ircd.example.conf</b> and save it to <b>conf/ircd.conf</b>.<br>
When you are done editting the configuration files, you can start ProvisionIRCd by running ```python3 ircd.py```

### With Docker

1. Make sure you have Docker and Docker Compose installed.
2. Copy `conf/examples/ircd.example.conf` to `conf/ircd.conf` and edit it to your liking.
3. Run `docker-compose up -d`.
4. To stop the server, run `docker-compose down`.

## Features

- Very modular, all modules can be reloaded on the fly (not always recommended)
- IRCv3 features
- Full TLS support
- Extended channel and server bans
- Linking capabilities
- Flexible oper permissions system

## Services

To use Anope with ProvisionIRCd, load the <b>unreal4</b> protocol module in Anope services.conf.

## Issue

If you find a bug or have a feature request, you can <a href="https://github.com/Y4kuzi/ProvisionIRCd/issues/new">submit an issue</a>
<br>
or you can contact me on IRC @ irc.provisionweb.org when I'm not afk.
