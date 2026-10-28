# Deployment validation

The initial deployment ran on the original Intel DXP2800, firmware-reported
system version `EM_DXP2800_V1.0.26`, with Proxmox kernel `7.0.14-26-pve`.
Installation and automated checks completed on October 27, 2026, local time.
The owner confirmed the physical LEDs looked correct on October 28, 2026.

Verified:

- MCU response checksums and command acknowledgments on the identified I801
  adapter at address `0x3a`.
- Steady white power and link, empty ATA bay 1 dark, and installed ATA bay 2
  white while idle.
- Actual controller blink-mode readback during a bounded 512 MiB read-only
  direct disk read and traffic to the existing gateway.
- Empty bay remained dark and power remained steady white during activity.
  The occupied drive returned to steady white after I/O completed.
- Service restart, enabled startup configuration and fresh runtime state,
  with no automatic crash restarts during verification.
- Healthy ZFS pools and storage, unchanged guest identities/power states,
  working management services and trusted HTTPS, preserved native NIC/keyboard
  LED triggers, and a clean package/systemd audit.

Fault and missing-device behavior was checked using synthetic ZFS fixtures.
No live pool was faulted. Startup was enabled and service restart was tested;
no host reboot was performed for this change.

The repository's service source, systemd unit, configuration example and
modules-load file match the working deployment byte for byte at project
creation. GitLab packaging does not redeploy or modify NAS1.

Raw inventories, private backup archives, credentials, runtime controller
state and host logs stay in the deployment's private evidence storage.
