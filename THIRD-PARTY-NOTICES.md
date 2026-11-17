# Third-Party Notices

This repository bundles third-party binaries. They are NOT covered by the
MIT license of this repository and keep their original licenses.

## monfloat/lib/ — LibreHardwareMonitorLib.dll and bundled runtime DLLs

- Source: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- License: MPL-2.0 (Mozilla Public License 2.0)
- Files: all `*.dll` under `monfloat/lib/`
- No modifications were made to these binaries.

MPL-2.0 notice: This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.

## EnergyControl/EnergyControl.exe

- Source: https://github.com/ethandong16/EnergyControl-for-Lenovo
- License: GPL-3.0-only (GNU General Public License v3.0)
- File: `EnergyControl/EnergyControl.exe`
- No modifications were made to this binary. Source is available at the
  upstream repository linked above.

## Not included

- `fnlockec/disasm.txt` (disassembly of Lenovo's proprietary AcpiVpc.sys
  driver) is intentionally excluded from this repository as a derivative of
  copyrighted vendor code. It can be regenerated locally with
  `fnlockec/analyze.py` if needed for driver-update verification.
