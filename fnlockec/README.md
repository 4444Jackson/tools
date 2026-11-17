# FnLockEC

免重启切换联想 Fn Lock（Fn+Esc 功能）的工具。直写 EC 固件级设置，即时生效且持久保存，无需 Vantage、无需热键驱动、无需重启进 BIOS。

## 原理

通过联想 `AcpiVpc.sys`（VPC2004 ACPI 设备）创建的控制设备 `\\.\EnergyDrv`：

- IOCTL `0x831020E8`（METHOD_BUFFERED，输入 1 字节）
  - `0x02` → 驱动执行 ACPI `HALS`，返回 4 字节状态，**bit 10 = Fn Lock 开关**
  - `0x0E` → ACPI `SALS`，开 Fn Lock（F1-F12 为标准功能键）
  - `0x0F` → ACPI `SALS`，关 Fn Lock（多媒体键优先）
- 接口语义源自 Linux `ideapad-laptop` 驱动逆向；IOCTL 分发逻辑经本目录 `analyze.py` + `disasm.txt`（capstone 反汇编 AcpiVpc.sys 的产物）实证

## 运行要求

- **联想机型**，BIOS ACPI 里有 `VPC2004` 设备且装有官方 `AcpiVpc` 驱动（设备管理器里正常即可）
- Windows + Python 3（纯标准库 ctypes，零第三方依赖）
- 管理员权限

## 使用

- `fnlock.bat`：双击出菜单；也支持 CLI：`fnlock.bat status|on|off|toggle`
- 或直接 `python FnLockEC.py status|on|off|toggle`

## 全局热键（可选，不装零开销）

bat 菜单头部实时显示：当前 Fn Lock ON/OFF、热键是什么（未设则显示「未设」）。

- `[2] 热键监听 开/关`：反向操作——未注册则注册（热键未设时会先进现场设键流程），已注册则删除监听（常驻归零）。注册的是登录触发的计划任务（隐藏窗口常驻监听，约 10MB 内存），按热键即切换 Fn Lock
- `[3] 重设快捷键`：**直接在键盘上按下想要的组合键**（需含 Ctrl/Alt/Shift/Win 至少一个修饰键），程序捕捉后写入 `fnlock.json`；监听已注册时自动用新键重建。也可手动编辑 `fnlock.json`（支持 ctrl/alt/shift/win + 字母/数字/F1-F12/space/esc 等）
- 注意：热键被其他程序占用时监听会自动退出并在控制台提示，换热键即可

## 兼容性

- 已实测：昭阳 K4e-IIL（BIOS DJCN31WW / EC DJEC20WW，AcpiVpc 内部版本同 EnergyVpc）
- 理论兼容同驱动架构的 IdeaPad/Legion 等机型，但 **IOCTL 编号与方法语义是本驱动版本逆向所得**，其他驱动版本可能不同。脚本对失败情况均有报错提示，不会盲写
- `analyze.py` 可在驱动更新后重新反汇编验证 IOCTL 表

## 免责声明

本工具直接向 EC/ACPI 写入配置，属非官方接口。请在了解风险后自行决定使用；作者不对固件异常、保修问题等负责。请遵守当地法律及设备厂商条款。
