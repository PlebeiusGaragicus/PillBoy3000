"""
    Album storage with three backends, resolved automatically:

    - Release image: a FAT32 partition labeled PILLBOY-SD (/dev/mmcblk0p2),
      normally UNMOUNTED. Every operation mounts it (ro for reads, rw for
      writes), does its work, syncs, and unmounts — the card stays a
      read-only medium except for sub-second explicit-save windows, and the
      album is plain files any computer can read.
    - Dev image: /mnt/data (always-mounted ext4) -> /mnt/data/album.
    - Desktop emulator: ~/.pillboy/album.

    A board/card with none of these simply reports available() == False and
    the UI hides everything album-related (same pattern as the wifi icon).

    Writes are temp-file-then-rename so a power cut mid-save can never leave
    a half-written file under a real name.
"""
import logging
import os
import re
import subprocess
import time

from contextlib import contextmanager

from pillboy.hardware.platform import is_raspberry_pi

logger = logging.getLogger(__name__)

SD_DEVICE = "/dev/mmcblk0p2"
SD_MOUNTPOINT = "/mnt/sd"
DEV_DATA_DIR = "/mnt/data"
DESKTOP_DIR = os.path.expanduser("~/.pillboy/album")

_IMG_RE = re.compile(r"^IMG_(\d{4})\.jpg$")


class Storage:
    """Album file access. Get one via Storage.get_instance()."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    MAX_PENDING = 20   # RAM-staged photos (~2.6MB each at 960px) before refusing

    def __init__(self):
        self.backend = self._resolve_backend()
        # RAM staging: photos taken while the card is out live here (ordered
        # [(virtual_name, PIL image), ...]) and flush to the card at the next
        # successful write. They are lost at power-off — the UI says so.
        self._pending = []
        self._pending_counter = 0
        logger.info(f"Storage backend: {self.backend}")

    @staticmethod
    def _sd_partition_present() -> bool:
        """True when SD_DEVICE carries the PILLBOY-SD FAT filesystem (label
        sniffed from the boot sector at the FAT16 and FAT32 offsets)."""
        try:
            with open(SD_DEVICE, "rb") as f:
                sector = f.read(512)
            return (sector[43:54] == b"PILLBOY-SD " or
                    sector[71:82] == b"PILLBOY-SD ")
        except OSError:
            return False

    def _resolve_backend(self) -> str:
        if not is_raspberry_pi():
            return "desktop"
        # Prefer the PILLBOY-SD partition: both release and (three-partition)
        # dev cards carry it at mmcblk0p2, and it's the code path release
        # uses. Old two-partition dev cards (ext4 at p2) fail the label sniff
        # and fall back to the always-mounted dev-data directory.
        if self._sd_partition_present():
            return "ondemand"
        if os.path.ismount(DEV_DATA_DIR):
            return "devdata"
        if os.path.exists(SD_DEVICE):
            return "ondemand"
        return "none"

    def available(self) -> bool:
        # RAM staging means saving is always possible; "none" only shapes
        # where the bytes end up. Kept for callers that want to phrase UI.
        return True

    def _reprobe(self):
        """A card can appear/disappear at runtime; re-resolve lazily."""
        if self.backend in ("none", "ondemand"):
            self.backend = self._resolve_backend()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    # --- mounting -----------------------------------------------------------

    @contextmanager
    def _album_dir(self, write: bool):
        """Yields the album directory path, mounted/created as needed."""
        if self.backend == "desktop":
            os.makedirs(DESKTOP_DIR, exist_ok=True)
            yield DESKTOP_DIR

        elif self.backend == "devdata":
            path = os.path.join(DEV_DATA_DIR, "album")
            os.makedirs(path, exist_ok=True)
            yield path

        elif self.backend == "ondemand":
            os.makedirs(SD_MOUNTPOINT, exist_ok=True)
            opts = "rw" if write else "ro"
            subprocess.run(["mount", "-t", "vfat", "-o", opts,
                            SD_DEVICE, SD_MOUNTPOINT], check=True)
            try:
                path = os.path.join(SD_MOUNTPOINT, "album")
                if write:
                    os.makedirs(path, exist_ok=True)
                yield path
            finally:
                if write:
                    os.sync()
                # Lazy-retry once; nothing else should ever hold this mount.
                for attempt in (1, 2):
                    ret = subprocess.run(["umount", SD_MOUNTPOINT]).returncode
                    if ret == 0:
                        break
                    time.sleep(0.5)
                else:
                    logger.error("Could not unmount %s", SD_MOUNTPOINT)
        else:
            raise RuntimeError("No storage backend available")

    # --- album API ----------------------------------------------------------

    def _write_jpeg(self, d: str, img, quality: int) -> str:
        """Write img into dir d as the next IMG_NNNN.jpg (temp+rename)."""
        nums = [int(m.group(1)) for f in os.listdir(d)
                if (m := _IMG_RE.match(f))]
        name = f"IMG_{(max(nums) + 1 if nums else 1):04d}.jpg"
        tmp = os.path.join(d, ".tmp_save.jpg")
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(tmp, "JPEG", quality=quality)
        with open(tmp, "rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp, os.path.join(d, name))
        return name

    def save_image(self, img, quality: int = 90):
        """
            Save a PIL image. Returns (name, staged): staged=False means it's
            on the card as IMG_NNNN.jpg (any RAM-pending photos were flushed
            first); staged=True means no card was writable and the photo is
            held in RAM as RAM_NNNN (flushed automatically later, lost at
            power-off). Raises only when RAM staging is full.
        """
        self._reprobe()
        try:
            with self._album_dir(write=True) as d:
                for _, pending_img in self._pending:
                    self._write_jpeg(d, pending_img, quality)
                self._pending = []
                return self._write_jpeg(d, img, quality), False
        except Exception:
            if len(self._pending) >= self.MAX_PENDING:
                raise RuntimeError("RAM staging full — insert the card")
            self._pending_counter += 1
            name = f"RAM_{self._pending_counter:04d}"
            self._pending.append((name, img.copy()))
            logger.info(f"No writable card; staged {name} in RAM "
                        f"({len(self._pending)} pending)")
            return name, True

    def flush_pending(self) -> int:
        """Try to write RAM-staged photos to the card. Returns count flushed."""
        if not self._pending:
            return 0
        self._reprobe()
        try:
            with self._album_dir(write=True) as d:
                n = len(self._pending)
                for _, img in self._pending:
                    self._write_jpeg(d, img, 90)
                self._pending = []
                logger.info(f"Flushed {n} RAM-staged photo(s) to the card")
                return n
        except Exception:
            return 0

    def list_images(self) -> list:
        """Album names, oldest first; RAM-staged photos (newest) last."""
        self.flush_pending()
        names = []
        try:
            with self._album_dir(write=False) as d:
                names = sorted(f for f in os.listdir(d) if _IMG_RE.match(f))
        except Exception:
            pass
        return names + [name for name, _ in self._pending]

    def load_image(self, name: str):
        """Load one album image as PIL. Raises on failure."""
        from PIL import Image
        for pending_name, img in self._pending:
            if pending_name == name:
                return img
        with self._album_dir(write=False) as d:
            img = Image.open(os.path.join(d, name))
            img.load()  # fully read before the partition unmounts
            return img

    def delete_image(self, name: str):
        if any(n == name for n, _ in self._pending):
            self._pending = [(n, i) for n, i in self._pending if n != name]
            return
        with self._album_dir(write=True) as d:
            os.remove(os.path.join(d, name))
