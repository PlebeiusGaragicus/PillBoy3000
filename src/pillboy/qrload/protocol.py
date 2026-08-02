"""
    PB1 animated-QR transfer protocol.

    A payload is a JSON manifest:
        {"v": 1, "type": "game" | "message" | "image", "name": str, "data": str}
      - game:    data = python source defining one GameView subclass
      - message: data = plain text
      - image:   data = base64-encoded JPEG or PNG (should already fit 240x240;
                 the webapp sends JPEG, stepped down in quality/size to cap
                 the transfer at ~60 QR frames)

    Wire encoding: JSON -> UTF-8 -> zlib deflate -> base64 -> split into chunks.
    Each QR frame carries one chunk as text:

        PB1|<seq>|<total>|<chunk>

    with 1-based <seq>. Frames loop forever on the sender; the receiver collects
    them in any order until all <total> chunks are present. No fountain codes —
    missed frames are simply picked up on a later pass of the loop.

    This module is pure logic (no camera, no UI) so it's unit-testable and can
    serve as the reference implementation for the web-based generator.
"""
import base64
import json
import zlib

PREFIX = "PB1"
PAYLOAD_TYPES = ("game", "message", "image")


class QRProtocolError(Exception):
    pass


def encode_payload(manifest: dict, chunk_size: int = 300) -> list[str]:
    """Reference encoder (the webapp reimplements this in JS). Returns frame strings."""
    blob = base64.b64encode(zlib.compress(json.dumps(manifest).encode())).decode()
    chunks = [blob[i:i + chunk_size] for i in range(0, len(blob), chunk_size)] or [""]
    total = len(chunks)
    return [f"{PREFIX}|{i + 1}|{total}|{chunk}" for i, chunk in enumerate(chunks)]


def decode_payload(blob_b64: str) -> dict:
    """base64 zlib JSON -> validated manifest dict."""
    try:
        manifest = json.loads(zlib.decompress(base64.b64decode(blob_b64)))
    except Exception as e:
        raise QRProtocolError(f"Could not decode payload: {e}")

    if not isinstance(manifest, dict) or manifest.get("v") != 1:
        raise QRProtocolError("Unsupported payload version")
    if manifest.get("type") not in PAYLOAD_TYPES:
        raise QRProtocolError(f"Unknown payload type: {manifest.get('type')}")
    if not isinstance(manifest.get("data"), str):
        raise QRProtocolError("Payload has no data")
    manifest.setdefault("name", "Untitled")
    return manifest


class QRAssembler:
    """
        Collects PB1 frames (any order, duplicates fine) until complete.

        Usage:
            asm = QRAssembler()
            for qr_text in scanned_codes:
                asm.add_frame(qr_text)
                if asm.is_complete:
                    manifest = asm.assemble()
    """

    def __init__(self):
        self.total: int = None
        self.chunks: dict[int, str] = {}

    def add_frame(self, text: str) -> bool:
        """Returns True if this frame belonged to a PB1 transfer."""
        if not isinstance(text, str) or not text.startswith(PREFIX + "|"):
            return False
        try:
            _prefix, seq_s, total_s, chunk = text.split("|", 3)
            seq = int(seq_s)
            total = int(total_s)
        except ValueError:
            return False
        if total < 1 or not (1 <= seq <= total):
            return False

        if self.total is not None and total != self.total:
            # A different transfer started; reset and follow the new one
            self.reset()
        self.total = total
        self.chunks[seq] = chunk
        return True

    def reset(self):
        self.total = None
        self.chunks = {}

    @property
    def num_collected(self) -> int:
        return len(self.chunks)

    @property
    def is_complete(self) -> bool:
        return self.total is not None and len(self.chunks) == self.total

    def assemble(self) -> dict:
        if not self.is_complete:
            raise QRProtocolError("Transfer not complete")
        blob = "".join(self.chunks[i] for i in range(1, self.total + 1))
        return decode_payload(blob)
