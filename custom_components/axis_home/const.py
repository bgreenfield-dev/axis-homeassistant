"""Constants for Axis Home."""

DOMAIN = "axis_home"
VERSION = "0.2.1"

# The rooms protocol both sides speak (Axis: apps/server/src/rooms-ha.ts HA_PROTOCOL).
HA_PROTOCOL = 1
# The hub's socket protocol (Axis: packages/core/src/protocol.ts PROTOCOL_VERSION).
SOCKET_PROTOCOL = 1
SERVER_DEVICE = "@server"

CONF_URL = "url"
CONF_CODE = "code"
CONF_TOKEN = "token"

PLATFORMS = ["select", "switch", "number", "sensor", "button", "notify"]
