# 案例：PICO VR 具身 Ego Data 采集时手柄数据读不到

测试环境：XRoboToolkit Unity Client v1.1.1、PC Service v1.0.0、Linux 电脑与 Python SDK。本文只讨论手柄数据到达电脑程序的链路；不把机器人控制错误归入同一故障。

## 两个断点

1. **电脑服务层**：PC Service 原实现仅在收到专用心跳包时刷新在线计时。连续的 Tracking 数据存在时仍可能超过 20 秒被判离线；同一设备标识重连后也没有重新通知 SDK。完整修复是 [`connection_fix.patch`](../adapters/xrobotoolkit-pc-service-v1.0.0/connection_fix.patch)，构建入口是 [`build.sh`](../adapters/xrobotoolkit-pc-service-v1.0.0/build.sh)。
2. **本机 SDK 层**：失败终端继承了代理变量，`no_proxy` 有 `localhost`，但无 SDK 使用的 `127.0.0.1`。SDK 的本机 gRPC 连接因此失败。在同一组代理变量下，仅清理 SDK 子进程的代理环境后，结果由 179 帧全部零时间戳变为 179 帧中 148 帧非零。通用的检查和隔离代码在 [`cli.py`](../src/teleop_link_diag/cli.py)。

这两个故障会给应用相似的“全零”表象。它们是两处独立断点，不是“VPN 开关导致故障”的证明。用户确认 VPN 在成功和失败期间始终开启；代理变量的来源没有保存足够证据，因此不归因于某个 VPN 应用。

## 时间线与数据

| 时间（2026 年 9 月，中国标准时间） | 观察 | 能得出的结论 |
| --- | --- | --- |
| 28 日 11:20、11:27、14:42 | 只读记录分别有 1160/1191、3540/3572、1755/1786 帧非零时间戳 | 这些时段 SDK 数据链路工作；当时终端的代理变量未保存 |
| 29 日 10:44 | SDK 连到服务，但服务未报告在线设备 | 断点在服务内部状态或更前段，不能归为 SDK 代理故障 |
| 29 日 11:59 | 头显 TCP Tracking 仍流入，服务判设备离线 | 与原版在线计时逻辑缺陷吻合 |
| 29 日 13:19 | 用户终端 SDK 没有连到本机服务 | 与代理环境对照实验对应 |
| 29 日 13:24 | 只读记录 563/594 帧非零时间戳，右手柄有效位姿 233 帧 | 真正的右手柄数据到达应用；未宣称整个时段位姿连续 |
| 29 日 15:24 | 主机采样 437/443 行非零，容器收到 2176 个 Pico 包；因右扳机松开结束 | 修复后的 Pico 数据链路在一次用户跟随运行中有效 |
| 29 日 15:29 | 主机采样 387/392 行非零，容器收到 1926 个 Pico 包；FR3 报通信约束错误 | Pico 数据仍到达；FR3 停止属于另一条控制链路 |

## 服务端验证与边界

使用模拟 TCP 设备、同一设备标识进行离线测试：重连后 SDK 再次收到上线通知；连续发送 Tracking 46 秒且没有专用心跳时未在 20 秒被错误标记离线；停止发送后仍按超时规则离线。服务端修复使用与本机运行库兼容的 Qt 6.6.3 构建，并仅部署在个人 PC Service 目录。重新安装上游服务可能覆盖该本地库。

两项修复在后来的成功运行中同时存在，因此不能把某一次成功单独归功于其中一项。代理故障的因果证据来自复制失败终端环境后的前后对照；PC Service 行为来自上游 v1.0.0 源码、故障日志与模拟设备测试。适用于其他遥操作方案的是分层定位方法，服务端补丁仍只适用于对应版本。

上游参考：[gRPC C-Core 代理说明](https://github.com/grpc/grpc/blob/master/doc/core/default_http_proxy_mapper.md)、[PC Service v1.0.0 心跳处理](https://github.com/XR-Robotics/XRoboToolkit-PC-Service/blob/v1.0.0/RoboticsService/DeviceConnectionManager/Model/tcpconnectionmodel.cpp)、[PC Service v1.0.0 连接检查](https://github.com/XR-Robotics/XRoboToolkit-PC-Service/blob/v1.0.0/RoboticsService/DeviceConnectionManager/Manage/TCPConnectionManage/tcpserverworker.cpp)。
