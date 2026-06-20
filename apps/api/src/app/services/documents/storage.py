"""Private Azure Blob-compatible object storage for raw document bytes."""

from __future__ import annotations

from typing import Protocol

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient


class ObjectStorageError(Exception):
    """Neutral infrastructure error that never includes provider response details."""


class ObjectNotFoundError(ObjectStorageError):
    """A stored raw object is missing; the worker maps this to a safe terminal failure."""


class ObjectTooLargeError(ObjectStorageError):
    """A private read would exceed its configured worker resource bound."""


class ObjectStorage(Protocol):
    """Minimal raw-object contract used by the Phase 10 document service."""

    async def put_bytes(self, *, key: str, payload: bytes, content_type: str) -> None:
        """Write one immutable private object without generating a public URL."""

    async def delete(self, *, key: str) -> None:
        """Best-effort cleanup for an object whose metadata transaction failed."""

    async def get_bytes(self, *, key: str, maximum_bytes: int) -> bytes:
        """Read a bounded private object without exposing a URL or provider details."""


class AzureBlobObjectStorage:
    """Azure Blob adapter that works with Azurite and Azure Blob Storage alike."""

    def __init__(self, *, connection_string: str, container: str) -> None:
        self._client = BlobServiceClient.from_connection_string(connection_string)
        self._container = self._client.get_container_client(container)

    async def put_bytes(self, *, key: str, payload: bytes, content_type: str) -> None:
        try:
            properties = await self._container.get_container_properties()
            if getattr(properties, "public_access", None) is not None:
                raise ObjectStorageError()
            await self._container.upload_blob(
                name=key,
                data=payload,
                overwrite=False,
                content_settings=ContentSettings(content_type=content_type),
            )
        except AzureError as error:
            raise ObjectStorageError() from error

    async def delete(self, *, key: str) -> None:
        try:
            await self._container.delete_blob(blob=key)
        except AzureError as error:
            raise ObjectStorageError() from error

    async def get_bytes(self, *, key: str, maximum_bytes: int) -> bytes:
        """Return an object only after provider metadata confirms the bounded size."""

        try:
            blob = self._container.get_blob_client(key)
            properties = await blob.get_blob_properties()
            size = getattr(properties, "size", None)
            if not isinstance(size, int) or size < 0:
                raise ObjectStorageError()
            if size > maximum_bytes:
                raise ObjectTooLargeError()
            payload = await (await blob.download_blob()).readall()
            if len(payload) > maximum_bytes:
                raise ObjectTooLargeError()
            return payload
        except ResourceNotFoundError as error:
            raise ObjectNotFoundError() from error
        except ObjectStorageError:
            raise
        except AzureError as error:
            raise ObjectStorageError() from error

    async def close(self) -> None:
        """Close the underlying async transport when a request dependency ends."""

        await self._client.close()
