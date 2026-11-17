# Lenovo EC Tools

三个互相独立的联想笔记本小工具，围绕 EC/ACPI 直连，不依赖 Vantage。

| 工具 | 功能 | 依赖 |
|---|---|---|
| [`monfloat/`](monfloat/) | TrafficMonitor 风格浮窗：CPU/GPU 占用率+真实温度、内存、网络、风扇（自动探测） | Python + pythonnet + psutil + PawnIO 驱动 |
| [`fnlockec/`](fnlockec/) | 免重启切换 Fn Lock，可注册自定义全局热键 | Python（纯标准库），限联想 VPC2004 机型 |
| [`EnergyControl/`](EnergyControl/) | 电池充电档位切换（养护/标准/快充），直写 EC 固件 | 联想 EnergyVpc 架构（AcpiVpc.sys） |

均实测于昭阳 K4e-IIL（81Y2）。各目录内有独立 README（原理/兼容性/免责声明）。

## 免责声明

本仓库的工具直接与 EC/ACPI 固件接口通信，属非官方接口。请在了解风险后自行决定使用；作者不对固件异常、保修问题等负责。请遵守当地法律及设备厂商条款。与 Lenovo 无隶属或背书关系。

## 许可

- 本仓库原创脚本（monfloat.py、FnLockEC.py、analyze.py、各 bat/ps1）：MIT，见 [LICENSE](LICENSE)
- 借用的第三方二进制及各自许可证：见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)
  - LibreHardwareMonitor 运行库（MPL-2.0）
  - EnergyControl.exe（GPL-3.0-only，源码见上游仓库）
- 联想专有驱动的反汇编产物不随仓库分发
