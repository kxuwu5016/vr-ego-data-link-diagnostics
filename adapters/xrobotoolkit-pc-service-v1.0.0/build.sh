#!/usr/bin/env bash
# Build only the affected PC Service library. Does not deploy or start services.
set -euo pipefail

if (( $# != 3 )); then
  echo 'Usage: build.sh <XRoboToolkit-PC-Service-v1.0.0-source> <Qt-prefix> <build-directory>' >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$(realpath "$1")"
QT_PREFIX="$(realpath "$2")"
BUILD="$3"
PATCH="$SCRIPT_DIR/connection_fix.patch"

[[ -d "$SOURCE/.git" ]] || { echo 'Source must be a Git checkout.' >&2; exit 1; }
[[ -f "$SOURCE/RoboticsService/DeviceConnectionManager/CMakeLists.txt" ]] || {
  echo 'DeviceConnectionManager source is missing.' >&2; exit 1;
}
[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$(git -C "$SOURCE" rev-parse v1.0.0)" ]] || {
  echo 'This patch is only verified against upstream v1.0.0.' >&2; exit 1;
}
[[ -d "$QT_PREFIX/lib/cmake/Qt6" ]] || {
  echo 'Expected a Qt 6 prefix containing lib/cmake/Qt6.' >&2; exit 1;
}
export PATH="$QT_PREFIX/bin:$PATH"
if [[ -z "${CXX:-}" && -x "$QT_PREFIX/bin/x86_64-conda-linux-gnu-c++" ]]; then
  export CXX="$QT_PREFIX/bin/x86_64-conda-linux-gnu-c++"
fi
if [[ -z "${CC:-}" && -x "$QT_PREFIX/bin/x86_64-conda-linux-gnu-cc" ]]; then
  export CC="$QT_PREFIX/bin/x86_64-conda-linux-gnu-cc"
fi
command -v cmake >/dev/null || { echo 'cmake is required.' >&2; exit 1; }
command -v patchelf >/dev/null || { echo 'patchelf is required to remove build-machine RPATH.' >&2; exit 1; }
GENERATOR_ARGS=()
if command -v ninja >/dev/null; then
  GENERATOR_ARGS=(-G Ninja)
fi

if git -C "$SOURCE" apply --check "$PATCH"; then
  git -C "$SOURCE" apply "$PATCH"
elif git -C "$SOURCE" apply --reverse --check "$PATCH"; then
  echo 'Patch already applied.'
else
  echo 'Patch cannot be applied cleanly to this checkout.' >&2
  exit 1
fi

cmake "${GENERATOR_ARGS[@]}" -S "$SOURCE/RoboticsService/CommonUtils" -B "$BUILD/common" \
  -DCMAKE_PREFIX_PATH="$QT_PREFIX" \
  -DCMAKE_PROJECT_INCLUDE="$SCRIPT_DIR/qt_components.cmake"
cmake --build "$BUILD/common"

cmake "${GENERATOR_ARGS[@]}" -S "$SOURCE/RoboticsService/DeviceConnectionManager" -B "$BUILD/device" \
  -DCMAKE_PREFIX_PATH="$QT_PREFIX"
cmake --build "$BUILD/device"

LIB="$BUILD/device/libDeviceConnectionManager.so"
[[ -f "$LIB" ]] || { echo 'Compiled library was not created.' >&2; exit 1; }
patchelf --remove-rpath "$LIB"

DEPENDENCIES="$(LD_LIBRARY_PATH="$SOURCE/RoboticsService/bin:$QT_PREFIX/lib:${LD_LIBRARY_PATH:-}" ldd -r "$LIB")"
if grep -Eq 'not found|undefined symbol' <<< "$DEPENDENCIES"; then
  printf '%s\n' "$DEPENDENCIES" >&2
  echo 'The built library has unresolved dependencies.' >&2
  exit 1
fi

echo "Built: $LIB"
echo 'Check its ABI and runtime dependencies against your PC Service package before deployment.'
