"""
    Network status helpers.

    All of this is optional-hardware territory: a plain Pi Zero (or a board
    with a physically disabled radio) simply never has a wlan0, and the
    desktop emulator has no /sys at all. Everything here degrades to
    False/None in those cases -- callers hide their UI accordingly.
"""
import json
import urllib.request


def wlan_connected(iface: str = "wlan0") -> bool:
    """True when the wireless interface exists and has an active link."""
    try:
        with open(f"/sys/class/net/{iface}/operstate") as f:
            return f.read().strip() == "up"
    except OSError:
        return False


def fetch_json(url: str, timeout: float = 6.0):
    """GET a small JSON (or bare-number) API response. Raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "PillBoy3000"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())
