# Axis Home

Axis's rooms in Home Assistant. Each room in [Axis](https://github.com/bgreenfield-dev/axis) shows up as a device. A device has:

- its scene as a select
- its lights as a switch
- Resume
- how many lights are held
- how often it agrees with Home Assistant
- its settings, including every curve light's night and day level in each scene

Axis is the source of truth. A change made in Home Assistant goes to Axis, which checks it, saves it and sends the final value back.

It also lets automations send you notices in Axis.

## Install

1. In HACS, add this repository as a custom repository (category Integration). Install **Axis Home**, then restart Home Assistant.
2. In Axis, run `home config ha link http://<axis address>:<port>` with the address Home Assistant reaches Axis at. Axis adds the integration in Home Assistant and pairs it through the Home Assistant connection it already has, so there's nothing to type here.

To add it by hand instead, go to Settings → Devices & services → Add integration → Axis Home. Enter the Axis address and a pairing code from `server pair` in Axis.

## Notices

An **Axis** device has a notify entity, `notify.axis`. Use it in any automation:

```yaml
action: notify.send_message
target:
  entity_id: notify.axis
data:
  title: Washer done
  message: The washing machine finished its cycle.
```

`axis_home.notify` takes a priority and a link too:

```yaml
action: axis_home.notify
data:
  title: Front door open
  message: It's been open for 10 minutes.
  priority: urgent # quiet, low, normal or urgent
  url: https://example.com/door
```

They arrive from Axis's Home Assistant source as "A notification from an automation", so `ha notices` in Axis switches them off or sets their priority. Without a priority, that setting decides. The link only opens from the notice's Open button. This needs Axis 0.19.6 or later.

## What it can reach

Axis Home signs in as its own kind of login. It can only read and change rooms and send notices: it can't reach anything else in Axis. Axis declares each room's entities, so a new setting in Axis becomes a new entity here without an update. When a room's entities change, for example a new scene, the integration reloads by itself.

The two sides check each other's protocol on connect. When they don't match, a Repairs issue says which side to update.

## Development

```
pip install aiohttp pytest pytest-asyncio
python -m pytest -q tests
```
