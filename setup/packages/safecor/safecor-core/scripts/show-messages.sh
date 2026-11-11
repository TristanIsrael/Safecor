#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


mosquitto_sub --unix /tmp/mqtt_msg_local.sock -t '#' --pretty -v