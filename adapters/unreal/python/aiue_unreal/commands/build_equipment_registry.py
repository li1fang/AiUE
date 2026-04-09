from __future__ import annotations

from ._delegate import delegate_to_host_command


def run(context: dict, params: dict) -> dict:
    return delegate_to_host_command(context, "build-equipment-registry", params)
