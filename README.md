# Anker SOLIX Extras

Additional sensors for batteries configured in the
[official Anker SOLIX integration](https://github.com/anker-charging/ha-anker-solix-official).

Extras runs alongside the official integration and adds sensors to your
existing battery's device page. Your existing sensors, controls, and settings
continue to work as before.

This is an independent community project, not developed or supported by Anker.

## Sensors

| Sensor | Source | Refresh | Display |
| --- | --- | --- | --- |
| Battery temperature | Input register 10156, unit ID 1, signed INT16 divided by 10 | 60 seconds | °C, whole degrees by default |

## Important

**Extras uses features outside Anker's officially published and supported Modbus
interface.** Compatibility may vary between devices and firmware versions.
Use this integration at your own risk. The contributors and maintainers accept
no responsibility for damage to your device or other loss resulting from its use.

## Requirements and compatibility

- Home Assistant **2026.10.4 or newer**.
- **Anker SOLIX Official** installed and configured.
- An enabled battery device in the official integration.
- Local Modbus TCP enabled in the Anker app, with the battery reachable from
  Home Assistant. Extras uses your existing connection settings.

These are the models offered during setup:

| Model | Validation |
| --- | --- |
| Solarbank 4 E5000 Pro | Tested successfully with Extras |
| Solarbank Max AC | Independently reported in [upstream issue #58](https://github.com/anker-charging/ha-anker-solix-official/issues/58) |
| Solarbank Max | Inferred from the official integration's shared register map |
| XE / XE AC | Inferred from the official integration's shared register map |

Smart plugs and meters are not supported.

## Installation

### Marketplace / HACS custom repository

1. Install and configure **Anker SOLIX Official** first.
2. In **Marketplace / HACS**, open the menu and choose **Custom repositories**.
3. Add `https://github.com/MattCheetham/HA-Anker-Solix-Extras` with type **Integration**.
4. Find **Anker SOLIX Extras** and download it.
5. Restart Home Assistant to load the new custom integration.
6. Go to **Settings → Devices & services → Add integration**, search for
   **Anker SOLIX Extras**, and select your existing official battery.
7. Open your battery's existing device page. The additional sensors appear
   alongside those provided by the official integration.

Extras is installed through a custom repository. Keep the official integration
installed and configured alongside it.

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

## Using the additional sensors

After setup, open your battery's existing device page to find the Extras sensors.
You can add them to dashboards and automations like any other Home Assistant
sensor. Existing dashboards and automations continue to use their original
entities; Extras does not replace them automatically.

## Removing Extras

1. Update any dashboards or automations that use Extras sensors before removing
   them, choosing replacement sensors where needed.
2. In **Settings → Devices & services**, remove **Anker SOLIX Extras**.
   This removes its sensors while leaving the official integration and device
   in place.
3. Uninstall Extras through **Marketplace / HACS**, then restart Home Assistant.
   For a manual installation, delete only `custom_components/anker_solix_extras`
   before restarting.

**Keep the official integration and the battery device.** You do not need to
delete either to remove Extras.

## Troubleshooting

- **No batteries offered:** check the official integration has loaded, its device
  is enabled, and its model matches the compatibility table above.
- **Sensors unavailable or setup fails:** check the battery's connection and
  that the official integration is working. Reload Extras after restoring the
  connection. Some firmware versions may not provide the additional readings.
- **Duplicate sensors:** another integration may already provide the same
  measurement. Choose which entity to use in your dashboards and automations.
- **Official integration was deleted and added again:** remove the old Extras
  entry and set up Extras again, selecting the newly configured battery.
- **Reporting an issue:** include model, firmware, Core and Extras versions,
  whether the official integration works, and relevant redacted logs. Remove
  IP addresses and serial numbers before posting them publicly.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development, testing, and pull request
guidance. All changes go through review before merging into `main`.

## Licence

[MIT](LICENSE). The battery-plus icon is original project artwork.
