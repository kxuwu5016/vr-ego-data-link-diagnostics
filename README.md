# VR 具身机器人 Ego Data 采集的数据链路排障

**以 PICO VR / XRoboToolkit 为例，定位 PC Service 超时误判与本机代理干扰。** 这是一套独立于具体机械臂的电脑端排障代码，用来区分头显到 PC Service、PC Service 到本机 SDK、以及追踪数据本身的故障。仓库提供完整的 Python 命令行程序、离线测试，以及 XRoboToolkit PC Service v1.0.0 的源码补丁和构建脚本。它不包含机器人或夹爪控制代码。

本项目来自一次 PICO VR + XRoboToolkit 的实际排障，但诊断方法可用于其他采用“设备 → 电脑服务 → 本机 SDK”链路的遥操作系统。**通用的是分层诊断方法；PC Service 补丁仅针对 XRoboToolkit v1.0.0。** [案例与验证记录](docs/CASE_STUDY.md)。

## 故障地图

```text
XR 设备 ──网络/TCP──> 电脑服务 ──本机 gRPC/SDK──> 应用程序 ──控制链路──> 机器人
          ① 网络可达    ② 在线/重连状态   ③ 代理与回环地址    ④ 位姿有效性      ⑤ 单独排查
```

| 看到的现象 | 建议先查 |
| --- | --- |
| 服务没有收到设备 TCP 流 | IP、Wi-Fi、端口和设备端发送设置 |
| 服务收到流，但 SDK 看不到在线设备 | 服务的在线计时、心跳和重连通知 |
| 服务看得到设备，但 SDK 连不到 `127.0.0.1` | 本机端口、终端代理变量和 `no_proxy` |
| SDK 已连接，时间戳或位姿仍无效 | 追踪数据与控制器状态 |
| 位姿持续有效，机器人却停机 | 机器人控制链路；与本工具分开排查 |

## 使用

需要 Python 3.10+；诊断命令只读取本机环境、日志或检查 TCP 可达性，不向机器人发送控制。

```bash
./teleop-link env
./teleop-link tcp --host 127.0.0.1 --port 60061
./teleop-link jsonl /path/to/read-samples.jsonl
./teleop-link log /path/to/sdk.log --marker 'server connect' --marker 'device found'
```

`env` 只输出代理**变量名**和风险判断，不输出代理 URL 或凭据。它依据 [gRPC C-Core 的代理选择规则](https://github.com/grpc/grpc/blob/master/doc/core/default_http_proxy_mapper.md)检查小写变量；风险提示并不等同于 SDK 连接失败的证明。`tcp` 只证明 TCP 端口可达，不证明 gRPC 正常或设备在线。`jsonl` 默认识别 `tracking_timestamp_ns` / `timestamp_ns` 与 `right_controller_pose` / `pose7`；其他方案可用 `--timestamp-key`、`--pose-key` 指定字段。`log` 用用户指定的字面标记计数，适配不同服务的日志。

如果某个 **只需要连接本机服务** 的 SDK 命令确实受到代理影响，可以明确由用户执行：

```bash
./teleop-link run-local-sdk -- python3 /path/to/your-read-only-sdk-check.py
```

这个命令只为其子进程清除 HTTP/HTTPS/ALL/GRPC 代理变量，并设置 `no_proxy=127.0.0.1,localhost`；不修改父终端、VPN 或系统代理。它会执行用户提供的任意命令，因此应先使用只读 SDK 检查程序。完整实现位于 [`src/teleop_link_diag/cli.py`](src/teleop_link_diag/cli.py)。

## XRoboToolkit v1.0.0 补丁

[`adapters/xrobotoolkit-pc-service-v1.0.0/`](adapters/xrobotoolkit-pc-service-v1.0.0/) 包含完整的 `connection_fix.patch`、`build.sh` 和说明。补丁解决的是本案例中的两个服务端行为：

- 在识别设备后，解析到有效数据包时更新在线时间，避免仍有 Tracking 数据却因专用心跳超时被判离线。
- 同一设备标识重新建立连接时，重新向 SDK 通知设备上线。

该补丁来自 [XRoboToolkit PC Service v1.0.0](https://github.com/XR-Robotics/XRoboToolkit-PC-Service/tree/v1.0.0) 的源码差异。仓库只包含补丁，不包含上游完整源码或编译好的库。编译需要与读者安装包兼容的 Qt 运行环境；`build.sh` 不会安装库或重启服务。其他 PC Service、版本和操作系统需要单独适配。

## 验证

`python3 -m unittest discover -s tests -v` 运行本仓库的离线测试，包括代理凭据不出现在报告中、`localhost` 不等于字面 `127.0.0.1`、以及时间戳与位姿分别计数。案例中的 PC Service 补丁还经过模拟 TCP 设备的连续 Tracking、超时及重连检查；详见[案例记录](docs/CASE_STUDY.md)。

本工具不声称解决所有追踪延迟、Wi-Fi 丢包或机器人控制错误。出现相同的“全零”输出时，应依据两端日志确认断点，不能只凭症状套用补丁。

## 许可证与上游来源

本仓库原创通用代码采用 [MIT 许可证](LICENSE)。XRoboToolkit PC Service 补丁基于 Apache-2.0 上游源码；其许可证副本与来源说明放在适配器目录。发布前请检查日志中是否包含设备标识、局域网地址或代理凭据。
