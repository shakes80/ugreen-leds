# Third-party notices

The original DXP2800 MCU command framing, checksums, register layout and
acknowledgment protocol were derived from the implementation in:

- Project: `miskcoo/ugreen_leds_controller`
- Source: <https://github.com/miskcoo/ugreen_leds_controller>
- Reviewed revision: `f0fcd8192abdd92244aba9f6f0d10572f5561380`
- Relevant source files: `cli/i2c.cpp`, `cli/ugreen_leds.cpp`,
  `cli/ugreen_leds.h`, `cli/ugreen_leds_cli.cpp`
- Upstream copyright: 2024 `miskcoo@gmail.com`
- Upstream license: MIT, reproduced in
  [licenses/ugreen_leds_controller-MIT.txt](licenses/ugreen_leds_controller-MIT.txt)

This repository adds Python control, device activity and ZFS health policy,
systemd configuration, operational documentation and hardware-free tests.
No separate license grant for project-specific additions has been declared.
