r"""
ONVIF event checker.

Usage:
    .\.venv\Scripts\python.exe .\tools\check_onvif_events.py --host 192.168.1.130 --username admin --seconds 20

The password is requested with getpass and is never printed or saved.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
import xml.etree.ElementTree as ET

from check_onvif_camera import NS, OnvifProbe, _desc_text, _local_name, _node_text


def _print_event_summary(root: ET.Element) -> int:
    count = 0
    for notification in root.iter():
        if _local_name(notification.tag) != "NotificationMessage":
            continue
        count += 1
        topic = _desc_text(notification, "Topic")
        message = _desc_text(notification, "Message")
        source = _desc_text(notification, "Source")
        data = _desc_text(notification, "Data")
        print(f"Event #{count}")
        print(f"  Topic: {topic or '-'}")
        if source:
            print(f"  Source: {source}")
        if data:
            print(f"  Data: {data}")
        if message and message not in {source, data}:
            print(f"  Message: {message[:300]}")
    return count


class OnvifEventProbe(OnvifProbe):
    def create_pullpoint_subscription(self) -> str:
        root = self.call(
            self.events_url or self.device_url,
            """
            <tev:CreatePullPointSubscription>
              <tev:InitialTerminationTime>PT60S</tev:InitialTerminationTime>
            </tev:CreatePullPointSubscription>
            """,
        )
        address = _desc_text(root, "Address")
        if not address:
            raise RuntimeError("CreatePullPointSubscription returned no subscription address")
        return address

    def pull_messages(self, subscription_url: str, timeout_seconds: int = 5, limit: int = 20) -> ET.Element:
        return self.call(
            subscription_url,
            f"""
            <tev:PullMessages>
              <tev:Timeout>PT{max(int(timeout_seconds), 1)}S</tev:Timeout>
              <tev:MessageLimit>{max(int(limit), 1)}</tev:MessageLimit>
            </tev:PullMessages>
            """,
        )


def run(args: argparse.Namespace) -> int:
    password = args.password or getpass.getpass("Camera password: ")
    probe = OnvifEventProbe(
        host=args.host,
        username=args.username,
        password=password,
        timeout=args.timeout,
    )

    print("ONVIF Events probe")
    print("=" * 72)
    print(f"Host: {args.host}")
    print(f"Username: {args.username}")
    print("Password: <hidden>")
    print()

    try:
        caps = probe.get_capabilities()
        print(f"Events service: {caps.get('Events') or '-'}")
    except Exception as exc:
        print(f"Capabilities FAILED: {exc}")
        return 1

    try:
        props = probe.get_event_properties()
        print(f"FixedTopicSet: {props.get('FixedTopicSet') or '-'}")
        print(f"TopicNamespaceLocation: {props.get('TopicNamespaceLocation') or '-'}")
    except Exception as exc:
        print(f"GetEventProperties FAILED: {exc}")

    try:
        subscription_url = probe.create_pullpoint_subscription()
        print(f"Subscription: {subscription_url}")
    except Exception as exc:
        print(f"CreatePullPointSubscription FAILED: {exc}")
        return 1

    deadline = time.time() + max(args.seconds, 1)
    total = 0
    print()
    print(f"Listening for events for {args.seconds}s. Trigger motion/alarm now if needed...")
    while time.time() < deadline:
        remaining = max(1, min(args.timeout, int(deadline - time.time())))
        try:
            root = probe.pull_messages(subscription_url, timeout_seconds=remaining, limit=args.limit)
            total += _print_event_summary(root)
        except Exception as exc:
            print(f"PullMessages FAILED: {exc}")
            return 1

    print()
    print(f"Done. Events received: {total}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check ONVIF PullPoint events.")
    parser.add_argument("--host", default=os.environ.get("ONVIF_HOST", "192.168.1.130"))
    parser.add_argument("--username", default=os.environ.get("ONVIF_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("ONVIF_PASSWORD", ""))
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
