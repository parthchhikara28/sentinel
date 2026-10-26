import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from app.config import settings


def _resolve(hostname: str) -> set[str]:
    return {info[4][0] for info in socket.getaddrinfo(hostname, None)}


async def assert_public_url(url: str) -> None:
    """Raise ValueError if the URL points anywhere private."""
    if settings.allow_private_urls:
        return

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")

    try:
        addresses = await asyncio.to_thread(_resolve, parsed.hostname)
    except socket.gaierror:
        raise ValueError("hostname does not resolve") from None

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(f"URL resolves to a non-public address ({address})")
