"""Inspect local SDK connectivity without contacting or controlling a robot."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
from typing import Mapping, Sequence


PROXY_PRIORITY = ("grpc_proxy", "https_proxy", "http_proxy")
BYPASS_PRIORITY = ("no_grpc_proxy", "no_proxy")
PROXY_VARIABLES = (
    "grpc_proxy", "https_proxy", "http_proxy", "all_proxy",
    "GRPC_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
)
BYPASS_VARIABLES = ("no_grpc_proxy", "no_proxy", "NO_GRPC_PROXY", "NO_PROXY")


def _first_nonempty(env: Mapping[str, str], names: Sequence[str]) -> str | None:
    return next((name for name in names if env.get(name)), None)


def _bypasses_host(value: str, host: str) -> bool:
    host_ip = None
    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    for raw_entry in value.split(","):
        entry = raw_entry.strip().lower()
        if entry == "*" or entry == host.lower():
            return True
        if host_ip is not None:
            try:
                if host_ip in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                pass
    return False


def proxy_report(env: Mapping[str, str], host: str = "127.0.0.1") -> dict[str, object]:
    """Return variable *names* and risk flags; never include proxy URLs."""
    selected_proxy = _first_nonempty(env, PROXY_PRIORITY)
    selected_bypass = _first_nonempty(env, BYPASS_PRIORITY)
    bypasses = bool(selected_bypass and _bypasses_host(env[selected_bypass], host))
    return {
        "target_host": host,
        "set_proxy_variables": [name for name in PROXY_VARIABLES if env.get(name)],
        "set_bypass_variables": [name for name in BYPASS_VARIABLES if env.get(name)],
        "grpc_core_proxy_variable": selected_proxy,
        "grpc_core_bypass_variable": selected_bypass,
        "target_bypassed": bypasses,
        "potential_grpc_proxy_interference": bool(selected_proxy and not bypasses),
        "interpretation": (
            "Environment suggests a possible proxy route; test the SDK separately."
            if selected_proxy and not bypasses
            else "No proxy-route risk found in gRPC C-Core's documented lowercase variables."
        ),
    }


def tcp_report(host: str, port: int, timeout: float) -> dict[str, object]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            reachable = True
            error = None
    except OSError as exc:
        reachable = False
        error = type(exc).__name__
    return {
        "host": host,
        "port": port,
        "tcp_reachable": reachable,
        "error_type": error,
        "limitation": "TCP reachability does not prove gRPC health or device presence.",
    }


def summarize_jsonl(
    path: Path, timestamp_key: str | None = None, pose_key: str | None = None
) -> dict[str, object]:
    total = valid_time = valid_pose = malformed = 0
    selected_time = timestamp_key
    selected_pose = pose_key
    with path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(row, dict):
                malformed += 1
                continue
            total += 1
            if selected_time is None:
                selected_time = next(
                    (key for key in ("tracking_timestamp_ns", "timestamp_ns") if key in row),
                    None,
                )
            if selected_pose is None:
                selected_pose = next(
                    (key for key in ("right_controller_pose", "pose7") if key in row),
                    None,
                )
            valid_time += bool(selected_time and row.get(selected_time))
            valid_pose += bool(selected_pose and row.get(selected_pose) is not None)
    return {
        "file": str(path),
        "total_rows": total,
        "nonzero_timestamp_rows": valid_time,
        "non_null_pose_rows": valid_pose,
        "malformed_rows": malformed,
        "timestamp_key": selected_time,
        "pose_key": selected_pose,
        "limitation": "A timestamp or pose proves data arrived, not that tracking was continuous.",
    }


def summarize_log(path: Path, markers: Sequence[str]) -> dict[str, object]:
    counts = {marker: 0 for marker in markers}
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            for marker in markers:
                counts[marker] += line.count(marker)
    return {"file": str(path), "marker_counts": counts}


def direct_sdk_environment(env: Mapping[str, str]) -> dict[str, str]:
    """Build an environment for an SDK that only talks to localhost."""
    result = dict(env)
    for name in PROXY_VARIABLES:
        result.pop(name, None)
    for name in BYPASS_VARIABLES:
        result.pop(name, None)
    result["no_proxy"] = "127.0.0.1,localhost"
    result["NO_PROXY"] = result["no_proxy"]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="teleop-link", description="Read-only XR teleoperation link diagnostics"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    env = sub.add_parser("env", help="Inspect proxy risk without printing proxy URLs")
    env.add_argument("--host", default="127.0.0.1")

    tcp = sub.add_parser("tcp", help="Check only TCP reachability")
    tcp.add_argument("--host", default="127.0.0.1")
    tcp.add_argument("--port", type=int, default=60061)
    tcp.add_argument("--timeout", type=float, default=1.0)

    data = sub.add_parser("jsonl", help="Summarize SDK sample timestamps and poses")
    data.add_argument("path", type=Path)
    data.add_argument("--timestamp-key")
    data.add_argument("--pose-key")

    log = sub.add_parser("log", help="Count literal markers in a service or SDK log")
    log.add_argument("path", type=Path)
    log.add_argument("--marker", action="append", required=True)

    run = sub.add_parser(
        "run-local-sdk",
        help="Launch a localhost-only SDK command without inherited proxies (explicit command required)",
    )
    run.add_argument("argv", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "env":
        result = proxy_report(os.environ, args.host)
    elif args.command == "tcp":
        if not (1 <= args.port <= 65535) or args.timeout <= 0:
            raise SystemExit("port must be 1..65535 and timeout must be positive")
        result = tcp_report(args.host, args.port, args.timeout)
    elif args.command == "jsonl":
        result = summarize_jsonl(args.path, args.timestamp_key, args.pose_key)
    elif args.command == "log":
        result = summarize_log(args.path, args.marker)
    else:
        command = list(args.argv)
        if command and command[0] == "--":
            command.pop(0)
        if not command:
            raise SystemExit("run-local-sdk requires a command after --")
        os.execvpe(command[0], command, direct_sdk_environment(os.environ))
        return 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
