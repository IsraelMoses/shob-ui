"""
Small ONVIF PTZ client used for IDIS zoom controls.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import re
import secrets
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

import requests


SOAP_ENV = "http://www.w3.org/2003/05/soap-envelope"
WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
TDS = "http://www.onvif.org/ver10/device/wsdl"
TRT = "http://www.onvif.org/ver10/media/wsdl"
TR2 = "http://www.onvif.org/ver20/media/wsdl"
TT = "http://www.onvif.org/ver10/schema"
TPTZ = "http://www.onvif.org/ver20/ptz/wsdl"

NS = {
    "s": SOAP_ENV,
    "tds": TDS,
    "trt": TRT,
    "tr2": TR2,
    "tt": TT,
    "tptz": TPTZ,
}


def xml_escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


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


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _local_attr(attrs: dict[str, str], name: str) -> str:
    for key, value in attrs.items():
        if _local_name(key) == name:
            return value
    return ""


def _node_text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _desc_text(parent: ET.Element | None, local_name: str) -> str:
    if parent is None:
        return ""
    for element in parent.iter():
        if _local_name(element.tag) == local_name:
            text = _node_text(element)
            if text:
                return text
    return ""


def _text(parent: ET.Element | None, path: str) -> str:
    if parent is None:
        return ""
    found = parent.find(path, NS)
    return _node_text(found)


def _service_xaddr(parent: ET.Element, service_name: str) -> str:
    for element in parent.iter():
        if _local_name(element.tag) == service_name:
            return _desc_text(element, "XAddr")
    return ""


def _first_token(parent: ET.Element, local_names: set[str]) -> str:
    for element in parent.iter():
        if _local_name(element.tag) in local_names:
            token = _local_attr(element.attrib, "token")
            if token:
                return token
    return ""


def _normalize_onvif_url(host: str, port: int) -> str:
    host = (host or "").strip()
    port = int(port or 80)
    if host.startswith(("http://", "https://")):
        parts = urlsplit(host)
        scheme = parts.scheme or "http"
        netloc = parts.netloc
        if ":" not in netloc and port != 80:
            netloc = f"{netloc}:{port}"
        return f"{scheme}://{netloc}/onvif/device_service"
    netloc = host
    if ":" not in netloc and port != 80:
        netloc = f"{netloc}:{port}"
    return f"http://{netloc}/onvif/device_service"


class OnvifZoomController:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        onvif_port: int = 80,
        timeout: int = 5,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.onvif_port = int(onvif_port or 80)
        self.timeout = timeout
        self.device_url = _normalize_onvif_url(host, self.onvif_port)
        self.media_url = ""
        self.ptz_url = ""
        self.profile_token = ""
        self.session = requests.Session()
        self.session.trust_env = False

    def _call(self, url: str, body: str) -> ET.Element:
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope
  xmlns:s="{SOAP_ENV}"
  xmlns:wsse="{WSSE}"
  xmlns:wsu="{WSU}"
  xmlns:tds="{TDS}"
  xmlns:trt="{TRT}"
  xmlns:tr2="{TR2}"
  xmlns:tt="{TT}"
  xmlns:tptz="{TPTZ}">
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
            raise RuntimeError("ONVIF username/password rejected")
        if response.status_code >= 400:
            detail = re.sub(r"\s+", " ", response.text or "").strip()[:260]
            if detail:
                raise RuntimeError(f"ONVIF HTTP {response.status_code}: {detail}")
            raise RuntimeError(f"ONVIF HTTP {response.status_code}: {response.reason}")

        root = ET.fromstring(response.content)
        fault = root.find(".//s:Fault", NS)
        if fault is not None:
            reason = _text(fault, ".//s:Text") or _desc_text(fault, "Text")
            raise RuntimeError(f"ONVIF fault: {reason or 'unknown fault'}")
        return root

    def _ensure_ready(self):
        if self.ptz_url and self.profile_token:
            return

        root = self._call(
            self.device_url,
            "<tds:GetCapabilities><tds:Category>All</tds:Category></tds:GetCapabilities>",
        )
        self.media_url = _text(root, ".//tt:Media/tt:XAddr") or _service_xaddr(root, "Media")
        self.ptz_url = _text(root, ".//tt:PTZ/tt:XAddr") or _service_xaddr(root, "PTZ")
        if not self.media_url:
            raise RuntimeError("ONVIF media service was not found")
        if not self.ptz_url:
            raise RuntimeError("This camera did not report ONVIF PTZ/zoom support")

        self.profile_token = self._find_profile_token()
        if not self.profile_token:
            raise RuntimeError("ONVIF media profile token was not found")

    def _find_profile_token(self) -> str:
        token = ""
        try:
            profiles_root = self._call(self.media_url, "<trt:GetProfiles/>")
            token = _first_token(profiles_root, {"Profiles", "Profile"})
        except Exception:
            token = ""
        if token:
            return token

        try:
            profiles_root = self._call(self.media_url, "<tr2:GetProfiles/>")
            token = _first_token(profiles_root, {"Profiles", "Profile"})
        except Exception:
            token = ""
        if token:
            return token

        try:
            configs_root = self._call(self.ptz_url, "<tptz:GetConfigurations/>")
            token = _first_token(configs_root, {"PTZConfiguration"})
        except Exception:
            token = ""
        return token

    def continuous_zoom(self, velocity: float, timeout_seconds: float = 1.2):
        self._ensure_ready()
        velocity = max(min(float(velocity), 1.0), -1.0)
        timeout_seconds = max(float(timeout_seconds), 0.2)
        self._call(
            self.ptz_url,
            f"""
            <tptz:ContinuousMove>
              <tptz:ProfileToken>{xml_escape(self.profile_token)}</tptz:ProfileToken>
              <tptz:Velocity>
                <tt:Zoom x="{velocity:.2f}"/>
              </tptz:Velocity>
              <tptz:Timeout>PT{timeout_seconds:.1f}S</tptz:Timeout>
            </tptz:ContinuousMove>
            """,
        )

    def stop_zoom(self):
        self._ensure_ready()
        self._call(
            self.ptz_url,
            f"""
            <tptz:Stop>
              <tptz:ProfileToken>{xml_escape(self.profile_token)}</tptz:ProfileToken>
              <tptz:PanTilt>false</tptz:PanTilt>
              <tptz:Zoom>true</tptz:Zoom>
            </tptz:Stop>
            """,
        )
