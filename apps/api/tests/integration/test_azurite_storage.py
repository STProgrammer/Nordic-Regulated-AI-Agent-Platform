"""Opt-in live Azurite evidence for the private raw-object adapter."""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from app.core.config import AppSettings
from app.services.documents.storage import AzureBlobObjectStorage


def test_azurite_adapter_can_write_and_delete_a_private_synthetic_object() -> None:
    """Run only against a deliberately available local emulator, never a cloud account."""

    if os.getenv("NORDIC_RUN_AZURITE_TEST") != "1":
        pytest.skip("set NORDIC_RUN_AZURITE_TEST=1 with a local Azurite endpoint to run")
    asyncio.run(_write_and_delete())


async def _write_and_delete() -> None:
    settings = AppSettings(environment="local")
    storage = AzureBlobObjectStorage(
        connection_string=settings.object_storage_connection_string_value(),
        container=settings.object_storage_container,
    )
    key = f"phase10-integration/{uuid4()}"
    try:
        await storage.put_bytes(
            key=key, payload=b"synthetic azurite check", content_type="text/plain"
        )
    finally:
        try:
            await storage.delete(key=key)
        finally:
            await storage.close()
