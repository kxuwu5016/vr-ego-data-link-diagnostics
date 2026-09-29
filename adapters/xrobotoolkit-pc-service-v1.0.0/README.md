# XRoboToolkit PC Service v1.0.0 adapter

This directory contains the complete patch used in the case study, plus a build script. The upstream project is [XRoboToolkit-PC-Service](https://github.com/XR-Robotics/XRoboToolkit-PC-Service). The patch is limited to tag `v1.0.0`; it is not a generic fix for every PC Service.

The original code refreshes the online timestamp only for a dedicated heartbeat packet, while the connection check marks a device offline after 20 seconds. The patch refreshes the timestamp for a parsed packet belonging to an identified device, resets it when a connection is established or replaced, and re-announces the device when the same identifier reconnects. It also adds one include required by the local Qt build.

## Build

Clone the upstream repository at tag `v1.0.0`. Supply a Qt 6 development prefix compatible with the PC Service package on your computer:

```text
bash ./adapters/xrobotoolkit-pc-service-v1.0.0/build.sh SOURCE QT_PREFIX BUILD_DIR
```

The script applies `connection_fix.patch` to the supplied source checkout and builds `CommonUtils` and `DeviceConnectionManager`. `qt_components.cmake` imports the Qt Network target omitted by the upstream CommonUtils CMake file. The script removes the build-machine RPATH from the output library and checks dependencies in the build environment; it requires `patchelf` and `ldd`. It **does not** replace a running library. The tested local build used Qt 6.6.3. Before deploying elsewhere, verify library dependencies and ABI compatibility against the installed PC Service, stop that service instance, back up its original `libDeviceConnectionManager.so`, replace only that library, and restart the service. A binary built on one computer is not presumed portable to another.

The upstream code is Apache-2.0 licensed. `LICENSE.upstream` is included for attribution. This repository redistributes the patch, not the complete upstream source tree.
