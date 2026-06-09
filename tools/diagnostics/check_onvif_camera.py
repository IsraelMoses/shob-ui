r"""
ONVIF camera capability checker.

Usage:
    .\.venv\Scripts\python.exe .\tools\check_onvif_camera.py --host 192.168.1.130 --username admin

The password is requested with getpass and is never printed or saved.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import hashlib
import os
import re
import secrets
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, urlunsplit

import requests


SOAP_ENV = "http://www.w3.org/2003/05/soap-envelope"
WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
TDS = "http://www.onvif.org/ver10/device/wsdl"
TRT = "http://www.onvif.org/ver10/media/wsdl"
TT = "http://www.onvif.org/ver10/schema"
TPTZ = "http://www.onvif.org/ver20/ptz/wsdl"
TEV = "http://www.onvif.org/ver10/events/wsdl"

NS = {
    "s": SOAP_ENV,
    "tds": TDS,
    "trt": TRT,
    "tt": TT,
    "tptz": TPTZ,
    "tev": TEV,
}


def _text(parent: ET.Element | None, path: str) -> str:
    if parent is None:
        return ""
    found = parent.find(path, NS)
    return (found.text or "").strip() if found is not None else ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _iter_local(parent: ET.Element | None, local_name: str):
    if parent is None:
        return
    for element in parent.iter():
        if _local_name(element.tag) == local_name:
            yield element


def _desc_text(parent: ET.Element | None, local_name: str) -> str:
    for element in _iter_local(parent, local_name):
        text = _node_text(element)
        if text:
            return text
    return ""


def _first_desc(parent: ET.Element | None, local_name: str) -> ET.Element | None:
    for element in _iter_local(parent, local_name):
        return element
    return None


def _node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()


def _mask_url(value: str) -> str:
    value = value or ""
    try:
        parts = urlsplit(value)
    except Exception:
        return re.sub(r"://([^:/@\s]+):([^@/\s]+)@", r"://\1:***@", value)
    if parts.username and parts.password:
        netloc = f"{parts.username}:***@{parts.hostname or ''}"
        if parts.port:
            netloc += f":{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return value


def _password_digest(nonce: bytes, created: str, password: str) -> str:
    digest = hashlib.sha1(nonce + created.encode("utf-8") + password.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def _wsse_header(username: str, password: str) -> str:
    nonce = secrets.token_bytes(16)
    created = (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    digest = _password_digest(nonce, created, password)
    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    return f"""
    <s:Header>
      <wsse:Security s:mustUnderstand="1">
        <wsse:UsernameToken>
          <wsse:Username>{xml_escape(username)}</wsse:Username>
          <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest}</wsse:Password>
          <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>
          <wsu:Created>{created}</wsu:Created>
        </wsse:UsernameToken>
      </wsse:Security>
    </s:Header>
    """


def xml_escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class OnvifProbe:
    def __init__(self, host: str, username: str, password: str, timeout: int = 8):
        self.host = host.strip()
        self.username = username
        self.password = password
        self.timeout = timeout
        self.device_url = f"http://{self.host}/onvif/device_service"
        self.media_url = ""
        self.ptz_url = ""
        self.events_url = ""
        self.last_response_text = ""
        self.session = requests.Session()

    def call(self, url: str, body: str) -> ET.Element:
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope
  xmlns:s="{SOAP_ENV}"
  xmlns:wsse="{WSSE}"
  xmlns:wsu="{WSU}"
  xmlns:tds="{TDS}"
  xmlns:trt="{TRT}"
  xmlns:tt="{TT}"
  xmlns:tptz="{TPTZ}"
  xmlns:tev="{TEV}">
  {_wsse_header(self.username, self.password)}
  <s:Body>
    {body}
  </s:Body>
</s:Envelope>
"""
        response = self.session.post(
            url,
            data=envelope.encode("utf-8"),
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=self.timeout,
        )
        if response.status_code == 401:
            raise RuntimeError("Unauthorized (username/password rejected)")
        if response.status_code >= 400:
            details = re.sub(r"\s+", " ", response.text or "").strip()
            if details:
                details = details[:500]
                raise RuntimeError(f"HTTP {response.status_code}: {response.reason} | {details}")
            raise RuntimeError(f"HTTP {response.status_code}: {response.reason}")

        self.last_response_text = response.text
        root = ET.fromstring(response.content)
        fault = root.find(".//s:Fault", NS)
        if fault is not None:
            reason = _text(fault, ".//s:Text") or _node_text(fault.find(".//s:Reason", NS))
            raise RuntimeError(f"SOAP Fault: {reason or ET.tostring(fault, encoding='unicode')}")
        return root

    def get_device_info(self) -> dict[str, str]:
        root = self.call(self.device_url, "<tds:GetDeviceInformation/>")
        return {
            "Manufacturer": _text(root, ".//tds:Manufacturer"),
            "Model": _text(root, ".//tds:Model"),
            "Firmware": _text(root, ".//tds:FirmwareVersion"),
            "Serial": _text(root, ".//tds:SerialNumber"),
            "Hardware": _text(root, ".//tds:HardwareId"),
        }

    def get_capabilities(self) -> dict[str, str]:
        root = self.call(
            self.device_url,
            "<tds:GetCapabilities><tds:Category>All</tds:Category></tds:GetCapabilities>",
        )
        media = _text(root, ".//tt:Media/tt:XAddr")
        ptz = _text(root, ".//tt:PTZ/tt:XAddr")
        events = _text(root, ".//tt:Events/tt:XAddr")
        if not media:
            media = _desc_text(_first_desc(root, "Media"), "XAddr")
        if not ptz:
            ptz = _desc_text(_first_desc(root, "PTZ"), "XAddr")
        if not events:
            events = _desc_text(_first_desc(root, "Events"), "XAddr")
        self.media_url = media
        self.ptz_url = ptz
        self.events_url = events
        return {
            "Media": media,
            "PTZ": ptz,
            "Events": events,
        }

    def get_profiles(self) -> list[dict[str, str]]:
        if not self.media_url:
            return []
        root = self.call(self.media_url, "<trt:GetProfiles/>")
        profiles = []
        candidates = list(root.findall(".//trt:Profiles", NS))
        for element in root.iter():
            if _local_name(element.tag) in {"Profiles", "Profile"} and element not in candidates:
                candidates.append(element)
        for profile in candidates:
            token = profile.attrib.get("token", "")
            if not token:
                continue
            profiles.append({
                "token": token,
                "name": _text(profile, "tt:Name") or _desc_text(profile, "Name"),
                "video_source": _text(profile, ".//tt:VideoSourceConfiguration/tt:Name"),
                "encoder": _text(profile, ".//tt:VideoEncoderConfiguration/tt:Name"),
            })
        return profiles

    def get_stream_uri(self, token: str) -> str:
        if not self.media_url:
            return ""
        root = self.call(
            self.media_url,
            f"""
            <trt:GetStreamUri>
              <trt:StreamSetup>
                <tt:Stream>RTP-Unicast</tt:Stream>
                <tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport>
              </trt:StreamSetup>
              <trt:ProfileToken>{xml_escape(token)}</trt:ProfileToken>
            </trt:GetStreamUri>
            """,
        )
        return _text(root, ".//tt:Uri") or _desc_text(root, "Uri")

    def get_snapshot_uri(self, token: str) -> str:
        if not self.media_url:
            return ""
        root = self.call(
            self.media_url,
            f"""
            <trt:GetSnapshotUri>
              <trt:ProfileToken>{xml_escape(token)}</trt:ProfileToken>
            </trt:GetSnapshotUri>
            """,
        )
        return _text(root, ".//tt:Uri") or _desc_text(root, "Uri")

    def get_ptz_configurations(self) -> list[str]:
        if not self.ptz_url:
            return []
        root = self.call(self.ptz_url, "<tptz:GetConfigurations/>")
        names = []
        configs = list(root.findall(".//tptz:PTZConfiguration", NS))
        for element in root.iter():
            if _local_name(element.tag) == "PTZConfiguration" and element not in configs:
                configs.append(element)
        for cfg in configs:
            names.append(_text(cfg, "tt:Name") or _desc_text(cfg, "Name") or cfg.attrib.get("token", ""))
        return [name for name in names if name]

    def get_event_properties(self) -> dict[str, str]:
        if not self.events_url:
            return {}
        root = self.call(self.events_url, "<tev:GetEventProperties/>")
        topic_ns = [
            _node_text(item)
            for item in root.findall(".//tev:TopicNamespaceLocation", NS)
        ]
        fixed = _text(root, ".//tev:FixedTopicSet") or _desc_text(root, "FixedTopicSet")
        return {
            "FixedTopicSet": fixed,
            "TopicNamespaceLocation": ", ".join(topic_ns),
        }


def print_section(title: str):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_result(label: str, value: str):
    print(f"{label}: {value or '-'}")


def compact_xml(value: str, max_chars: int = 3000) -> str:
    compact = re.sub(r">\s+<", "><", value or "").strip()
    compact = re.sub(r"\s+", " ", compact)
    compact = _mask_url(compact)
    if len(compact) > max_chars:
        return compact[:max_chars] + "... [truncated]"
    return compact


def run(args: argparse.Namespace) -> int:
    password = args.password
    if not password:
        password = getpass.getpass("Camera password: ")

    probe = OnvifProbe(
        host=args.host,
        username=args.username,
        password=password,
        timeout=args.timeout,
    )

    print_section("ONVIF Device")
    print_result("Host", args.host)
    print_result("Username", args.username)
    print_result("Password", "<hidden>")
    print_result("Device service", probe.device_url)

    try:
        info = probe.get_device_info()
        print_section("Device Information")
        for key, value in info.items():
            print_result(key, value)
    except Exception as exc:
        print_section("Device Information")
        print(f"FAILED: {exc}")

    try:
        caps = probe.get_capabilities()
        print_section("Capabilities")
        print_result("Media service", caps.get("Media", ""))
        print_result("PTZ service", caps.get("PTZ", ""))
        print_result("Events service", caps.get("Events", ""))
    except Exception as exc:
        print_section("Capabilities")
        print(f"FAILED: {exc}")

    profiles: list[dict[str, str]] = []
    try:
        profiles = probe.get_profiles()
        print_section("Media Profiles")
        if not profiles:
            print("No profiles returned.")
            if args.debug:
                print()
                print("Raw GetProfiles response:")
                print(compact_xml(probe.last_response_text, args.debug_chars))
        for idx, profile in enumerate(profiles, start=1):
            print(f"[{idx}] token={profile['token']} name={profile['name'] or '-'}")
            print_result("    video_source", profile.get("video_source", ""))
            print_result("    encoder", profile.get("encoder", ""))
    except Exception as exc:
        print_section("Media Profiles")
        print(f"FAILED: {exc}")

    if profiles:
        profile = profiles[0]
        token = profile.get("token", "")
        print_section(f"Stream / Snapshot for profile {token}")
        try:
            print_result("Stream URI", _mask_url(probe.get_stream_uri(token)))
        except Exception as exc:
            print(f"Stream URI FAILED: {exc}")
        try:
            print_result("Snapshot URI", _mask_url(probe.get_snapshot_uri(token)))
        except Exception as exc:
            print(f"Snapshot URI FAILED: {exc}")

    try:
        ptz_configs = probe.get_ptz_configurations()
        print_section("PTZ")
        if ptz_configs:
            print("SUPPORTED")
            for item in ptz_configs:
                print_result("Configuration", item)
        else:
            print("No PTZ configurations returned.")
    except Exception as exc:
        print_section("PTZ")
        print(f"FAILED: {exc}")

    try:
        events = probe.get_event_properties()
        print_section("Events")
        if events:
            for key, value in events.items():
                print_result(key, value)
        else:
            print("No event service or no event properties returned.")
    except Exception as exc:
        print_section("Events")
        print(f"FAILED: {exc}")

    print()
    print("Done. No password was saved.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check ONVIF camera capabilities.")
    parser.add_argument("--host", default=os.environ.get("ONVIF_HOST", "192.168.1.130"))
    parser.add_argument("--username", default=os.environ.get("ONVIF_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("ONVIF_PASSWORD", ""))
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--debug", action="store_true", help="Print safe raw XML snippets for empty results.")
    parser.add_argument("--debug-chars", type=int, default=3000)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
