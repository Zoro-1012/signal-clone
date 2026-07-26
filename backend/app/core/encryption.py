"""Simulated end-to-end encryption.

The brief states plainly that encryption may be mocked. Rather than skip it, the
message pipeline is routed through a sealing abstraction so that the *shape* of
the system is honest: message bodies are sealed on write and opened on read,
every stored row records which key sealed it, and the call sites are exactly
where a real implementation would go.

This is deliberately NOT security. ``MockCipher`` is reversible by anyone with
the source. It exists so that swapping in a real ratchet is a one-class change
rather than a refactor of the message service, and so the README can describe
precisely what is and is not protected.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.config import settings


@dataclass(frozen=True)
class Envelope:
    """A sealed payload plus the metadata needed to open it later."""

    ciphertext: str
    key_id: str
    algorithm: str


@runtime_checkable
class Cipher(Protocol):
    """The contract a real implementation would have to satisfy."""

    algorithm: str

    def seal(self, plaintext: str) -> Envelope: ...

    def open(self, envelope: Envelope) -> str: ...


class MockCipher:
    """Base64 transport encoding standing in for a real cipher.

    Chosen precisely because it is obviously not encryption: nobody reading this
    code can mistake it for a security control, while it still exercises the
    seal/open round trip and the storage format end to end.
    """

    algorithm = "mock-base64-v1"

    def __init__(self, key_id: str | None = None) -> None:
        self.key_id = key_id or settings.encryption_key_id

    def seal(self, plaintext: str) -> Envelope:
        encoded = base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
        return Envelope(ciphertext=encoded, key_id=self.key_id, algorithm=self.algorithm)

    def open(self, envelope: Envelope) -> str:
        if envelope.algorithm != self.algorithm:
            raise ValueError(f"Cannot open envelope sealed with {envelope.algorithm!r}")
        return base64.b64decode(envelope.ciphertext.encode("ascii")).decode("utf-8")


# Process-wide instance. Swapped wholesale the day real crypto lands.
cipher: Cipher = MockCipher()
