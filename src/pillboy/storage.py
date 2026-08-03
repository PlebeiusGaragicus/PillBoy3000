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

    def __init__(self):
        self.backend = self._resolve_backend()
        logger.info(f"Storage backend: {self.backend}")

    def _resolve_backend(self) -> str:
        if not is_raspberry_pi():
            return "desktop"
        if os.path.ismount(DEV_DATA_DIR):
            return "devdata"
        if os.path.exists(SD_DEVICE):
            return "ondemand"
        return "none"

    def available(self) -> bool:
        return self.backend != "none"

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

    def save_image(self, img, quality: int = 90) -> str:
        """Save a PIL image as the next IMG_NNNN.jpg. Returns the filename."""
        with self._album_dir(write=True) as d:
            nums = [int(m.group(1)) for f in os.listdir(d)
                    if (m := _IMG_RE.match(f))]
            name = f"IMG_{(max(nums) + 1 if nums else 1):04d}.jpg"
            tmp = os.path.join(d, ".tmp_save.jpg")
            final = os.path.join(d, name)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(tmp, "JPEG", quality=quality)
            with open(tmp, "rb") as f:
                os.fsync(f.fileno())
            os.replace(tmp, final)
            return name

    def list_images(self) -> list:
        """Album filenames, oldest first. Empty when nothing is saved."""
        try:
            with self._album_dir(write=False) as d:
                return sorted(f for f in os.listdir(d) if _IMG_RE.match(f))
        except Exception:
            return []

    def load_image(self, name: str):
        """Load one album image as PIL. Raises on failure."""
        from PIL import Image
        with self._album_dir(write=False) as d:
            img = Image.open(os.path.join(d, name))
            img.load()  # fully read before the partition unmounts
            return img

    def delete_image(self, name: str):
        with self._album_dir(write=True) as d:
            os.remove(os.path.join(d, name))
