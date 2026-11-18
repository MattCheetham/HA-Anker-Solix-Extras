# Anker SOLIX Extras

Additional sensors for batteries configured in the
[official Anker SOLIX integration](https://github.com/anker-charging/ha-anker-solix-official).

Extras runs alongside the official integration and adds its entities to the
existing battery's device page. The official integration continues to own the
device and its existing entities, controls, and settings. Extras uses its own
read-only Modbus connection and does not modify the official integration.

This is an independent community project, not developed or supported by Anker.
Version **0.1** is in development; no GitHub release has been published yet.

## Sensors

| Sensor | Source | Refresh | Display |
| --- | --- | --- | --- |
| Battery temperature | Input register 10156, unit ID 1, signed INT16 divided by 10 | 60 seconds | °C, whole degrees by default |

Display precision can be changed in Home Assistant's entity settings. The
underlying fractional measurement is preserved. Failed reads make the sensor
unavailable; they are not replaced with zero or an invented temperature.

Register 10156 is **outside Anker's officially published and supported Modbus
interface**. Its behaviour may vary with model or firmware. The temperature
sensor in the predecessor fork was verified on a Solarbank 4 E5000 Pro against
a working manual Modbus sensor. The separate Extras integration still needs its
own hardware acceptance test.

## Requirements and compatibility

- Home Assistant **2026.10.4 or newer**.
- The official `anker_solix_official` custom integration installed and configured.
- An enabled battery device whose official integration entry has loaded.
- Local Modbus TCP enabled in the Anker app, with the battery reachable from
  Home Assistant. Extras uses the address and port already configured officially.

These are the models offered during setup:

| Model | Evidence for temperature register |
| --- | --- |
| Solarbank 4 E5000 Pro | Hardware-tested in the predecessor fork |
| Solarbank Max AC | Independently reported in [upstream issue #58](https://github.com/anker-charging/ha-anker-solix-official/issues/58) |
| Solarbank Max | Inferred from the official integration's shared register map |
| XE / XE AC | Inferred from the official integration's shared register map |

Smart plugs and meters are not offered. Setup attempts to read temperature
before creating an Extras entry, but a successful read alone cannot establish
that an undocumented value means the same thing on every firmware. Compare it
with a known working source when testing a new model.

## Installation

### Marketplace / HACS custom repository

1. Install and configure **Anker SOLIX Official** first. If using the earlier
   temperature fork, return to the official channel before testing Extras.
2. In **Marketplace / HACS**, open the menu and choose **Custom repositories**.
3. Add `https://github.com/MattCheetham/HA-Anker-Solix-Extras` with type **Integration**.
4. Find **Anker SOLIX Extras** and download it. Until the first release is
   published, this installs the default development branch.
5. Restart Home Assistant to load the new custom integration.
6. Go to **Settings → Devices & services → Add integration**, search for
   **Anker SOLIX Extras**, and select your existing official battery.
7. Open the battery's existing device page and find **Battery temperature**.

The repository is a custom repository, not a default Marketplace listing.
Install Extras and Official together: they have different domains and folders.
Do not remove or recreate your official integration entry to install Extras.

### Manual installation

Copy `custom_components/anker_solix_extras` from this repository into your Home
Assistant configuration directory's `custom_components` folder. The result is:

```text
config/
  custom_components/
    anker_solix_official/  # existing official integration
    anker_solix_extras/    # this integration
      __init__.py
      manifest.json
      ...
```

Restart Home Assistant and follow setup steps 6–7 above. Do not nest the Extras
folder inside the official integration's folder.

## Testing and rollback

1. Keep your existing manual temperature sensor, dashboards, and automations
   unchanged while testing. Record the official device and entity IDs first.
2. Add Extras and verify its temperature agrees with your existing sensor.
   Confirm the new entity is on the **same device page**, and the existing
   official entities still update.
3. Reload Extras, then restart Home Assistant, and confirm the association and
   entity IDs remain stable.
4. If you want to switch automations to Extras later, update their references
   explicitly: the new entity is independently owned and does not take over
   the old manual sensor's ID or history.

To roll back, remove **only the Anker SOLIX Extras configuration entry** from
Settings → Devices & services. This removes Extras entities, leaves the
official entry and device in place, and closes the Extras connection. You can
then remove the Extras files through Marketplace / HACS or delete only the
`custom_components/anker_solix_extras` directory and restart Home Assistant.

Avoid deleting the shared battery device from its device page: that device
belongs to the official integration. Any automation you changed to use Extras
must be pointed back to its original sensor before removing Extras.

## How linking and connections work

Setup selects an official configuration entry and looks up its registered
battery device. The new entity has its own Extras configuration entry and
unique ID, but attaches directly to the existing device. It does not add a new
device, change the official device's owner, or change its identifiers.

Extras checks the official entry's current address on every update, so changes
made through the official reconfigure flow are picked up. If the official
entry/device is disabled or unavailable, Extras stops reading and becomes
unavailable. Removing the official device leaves Extras waiting for its linked
battery; it does not create a replacement device. If you delete and recreate
the official entry, remove the old Extras entry and set Extras up again for the
new official entry.

The Modbus connection is separate from the official integration's connection.
No official Python modules or private coordinator data are imported. This
avoids tying Extras to internal Anker implementation changes. Devices must
allow an additional TCP connection; persistent connection errors may indicate
a firmware connection limit.

## Troubleshooting

- **No batteries offered:** check the official integration has loaded, its device
  is enabled, and its model matches the compatibility table above.
- **Temperature cannot be read:** check Modbus TCP and local connectivity. The
  firmware may not implement register 10156. Extras does not write registers
  or change battery operating mode to try to enable it.
- **Temperature unavailable:** restore connectivity or the official entry, then
  reload Extras if needed. Never interpret an unavailable reading as 0 °C.
- **Two temperature sensors:** keep the old manual sensor during validation.
  The predecessor fork also exposed temperature, so use the official channel
  when testing the companion integration.
- **Reporting an issue:** include model, firmware, Core and Extras versions,
  whether the official integration works, and relevant redacted logs. Remove
  IP addresses and serial numbers before posting them publicly.

## Development

Use Python **3.14** on Linux. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements_dev.txt
ruff check .
ruff format --check .
pytest --cov=custom_components.anker_solix_extras --cov-report=term-missing
```

The published test plugin pins Core 2026.10.4. CI also upgrades Core to 2026.11.2
after installing the test environment, to exercise the same device-linking
behaviour on the current release. Tests use real Home Assistant registries and
mock the official integration and Modbus transport; no battery is required.

Build a local installation ZIP with `python scripts/build_zip.py`. It writes
`dist/anker_solix_extras.zip`, containing the `anker_solix_extras` folder ready
to extract into `custom_components`. It does not create a tag or publish anything.

See [AGENTS.md](AGENTS.md) for development constraints. Use focused conventional
commits. GitHub Actions runs tests, Ruff, Hassfest, and HACS validation; it does
not create releases. Version publication is a separate, deliberate step.

## Licence

[MIT](LICENSE). The battery-plus icon is original project artwork.
