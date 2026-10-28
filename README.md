# UGREEN DXP2800 LEDs

A small host service that restores useful front-panel status and activity
indicators on the original Intel-based UGREEN DXP2800 running Proxmox VE.
It uses the LED MCU's SMBus interface and requires no kernel-specific build.

| Indicator | Behavior |
|---|---|
| Power | Steady white while configured ZFS pools are healthy; flashing amber for ZFS faults or unavailable health data |
| LAN | White link indicator with activity blinking; amber when the monitored link is down |
| SATA bays | Empty bay off; installed disk white with activity blinking; flashing amber for a mapped ZFS device fault |

This is the source of the service deployed and verified on NAS1. The owner
confirmed that the physical LEDs look correct on October 28, 2026.

## Hardware and requirements

- Original DXP2800 with a DMI product version beginning `EM_DXP2800_`.
  Validated on `EM_DXP2800_V1.0.26` and Proxmox kernel `7.0.14-26-pve`.
- Debian/Proxmox, Python 3, `python3-smbus`, systemd and OpenZFS with JSON
  output from `zpool status -j`.
- The MCU at I2C address `0x3a` on the SMBus I801 adapter. The program locates
  the adapter at startup, so its bus number can change.

Other UGREEN models and hardware revisions have different controllers and
are outside this implementation's validated scope. The hardware guard rejects
unrecognized model/version strings.

## Configuration

The example configuration matches the current deployment:

```json
{
  "interface": "nic0",
  "bays": {"disk1": 1, "disk2": 2},
  "pools": ["rpool", "datapool"],
  "brightness": 255,
  "poll_interval": 0.2,
  "health_interval": 10
}
```

Set `interface` to the physical Ethernet interface whose traffic should drive
the LAN LED. Bay values are physical ATA port numbers, not `/dev/sdX` numbers;
USB devices are excluded. Set `pools` to the pools that must be present and
healthy. Brightness ranges from 0 to 255. Poll intervals are in seconds.

ZFS pool/device states and error counters drive fault indications. SMART
predictive-failure monitoring remains the responsibility of the host's
existing monitoring tools. LAN color reflects the local link, not an external
Internet connectivity test. NVMe pool faults affect the power indicator.

## Fresh installation

NAS1 already runs this version. These commands are for a fresh installation
on matching hardware. Preserve an existing installation and its configuration
before attempting an update.

Run the commands from the repository root on the Linux host:

```sh
(
set -eu
# Stop here if an installation already exists.
if test -e /usr/local/sbin/ugreen-leds; then
  echo 'An installation already exists; back it up before updating.'
  exit 1
fi

sudo apt-get install --no-install-recommends python3-smbus
sudo modprobe i2c-dev
sudo install -D -m 0755 src/ugreen-leds /usr/local/sbin/ugreen-leds
sudo install -D -m 0644 config/ugreen-leds.example.json /etc/ugreen-leds.json
sudo install -D -m 0644 systemd/ugreen-leds.service /etc/systemd/system/ugreen-leds.service
sudo install -D -m 0644 modules-load/ugreen-leds.conf /etc/modules-load.d/ugreen-leds.conf
sudo install -D -m 0644 licenses/ugreen_leds_controller-MIT.txt /usr/local/share/doc/ugreen-leds/LICENSE.protocol
sudo install -D -m 0644 THIRD_PARTY_NOTICES.md /usr/local/share/doc/ugreen-leds/THIRD_PARTY_NOTICES.md

# Edit the interface and pool names to match this host before enabling it.
sudo editor /etc/ugreen-leds.json
sudo ugreen-leds --status
sudo ugreen-leds --once
sudo systemctl daemon-reload
sudo systemctl enable --now ugreen-leds.service
)
```

The status command reads the four known LED registers. No general I2C bus
scan is needed. The service serializes controller transactions, validates
response checksums and command acknowledgments, and reconciles MCU readback
periodically. Its systemd unit restricts filesystem and device access.

## Operation

```sh
sudo ugreen-leds --status
systemctl status ugreen-leds.service
sudo journalctl -u ugreen-leds.service
cat /run/ugreen-leds/status.json
```

After a deliberate configuration edit, restart the service and inspect its
runtime state and hardware readback. Stop the service before using `--once`
or `--restore` for manual control; `--status` can be used while it runs.

The daemon turns the indicators off when stopped and reapplies the configured
states when started. A host reboot is not required for installation.

## Validation and tests

```sh
python3 -m unittest discover -s tests -v
```

The tests use synthetic ZFS data and a fake SMBus device. They require neither
root privileges, I2C hardware nor the `smbus` package. GitLab CI runs the same
suite. [Deployment validation](docs/validation.md) records the real hardware
activity, restart and regression checks and their limits.

## Recovery

Disable and stop the service before restoring saved MCU settings:

```sh
sudo systemctl disable --now ugreen-leds.service
sudo ugreen-leds --restore /path/to/saved-led-state.json
```

The restore input is a JSON object with a `leds` mapping, as produced by
`ugreen-leds --status`. Remove installed files only after checking for local
changes. Reload systemd after removing the unit. Backups and original
hardware state remain in the deployment's private recovery directory and are
intentionally absent from this repository.

## Attribution

The MCU protocol derives from
[miskcoo/ugreen_leds_controller](https://github.com/miskcoo/ugreen_leds_controller),
pinned to `f0fcd8192abdd92244aba9f6f0d10572f5561380`.
The upstream copyright and MIT license are retained in
[third-party notices](THIRD_PARTY_NOTICES.md) and [the license file](licenses/ugreen_leds_controller-MIT.txt).
