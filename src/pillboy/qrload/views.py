import base64
import io
import textwrap
import time

from dataclasses import dataclass
from gettext import gettext as _

from pillboy.gui.components import Fonts, GUIConstants
from pillboy.hardware.buttons import HardwareButtons, HardwareButtonsConstants
from pillboy.qrload.protocol import QRAssembler, QRProtocolError
from pillboy.views.view import BackStackView, Destination, ErrorView, View

ACCENT = GUIConstants.ACCENT_COLOR


def _wait_any_button_then_release():
    buttons = HardwareButtons.get_instance()
    buttons.wait_for(HardwareButtonsConstants.ALL_KEYS)
    while buttons.has_any_input():
        time.sleep(0.01)


class QRScanView(View):
    """
        Scans an animated PB1 QR transfer with the camera, showing a live
        preview + chunk progress. Any button cancels. On completion, routes to
        the right handler for the payload type.
    """
    FPS = 10

    def run(self):
        try:
            from pyzbar import pyzbar
        except Exception:
            return Destination(ErrorView, view_args=dict(
                title=_("Missing library"),
                status_headline=_("QR decoding unavailable"),
                text=_("pyzbar/zbar is not installed on this system."),
                button_text=_("Back"),
            ), skip_current_view=True)

        camera = self.controller.camera
        try:
            camera.start_video_stream_mode(resolution=(480, 480), framerate=self.FPS, format="rgb")
        except Exception:
            return Destination(ErrorView, view_args=dict(
                title=_("Hardware Error"),
                status_headline=_("Cannot access camera"),
                text=_("Check for a loose camera connection."),
                button_text=_("Back"),
            ), skip_current_view=True)

        buttons = HardwareButtons.get_instance()
        assembler = QRAssembler()
        body_font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)

        try:
            while True:
                if buttons.check_for_low(keys=HardwareButtonsConstants.ALL_KEYS):
                    while buttons.has_any_input():
                        time.sleep(0.01)
                    return Destination(BackStackView)

                frame = camera.read_video_stream(as_image=True)
                if frame is None:
                    time.sleep(0.05)
                    continue

                for code in pyzbar.decode(frame.convert("L")):
                    try:
                        assembler.add_frame(code.data.decode("utf-8"))
                    except UnicodeDecodeError:
                        continue

                if assembler.is_complete:
                    try:
                        manifest = assembler.assemble()
                    except QRProtocolError as e:
                        return Destination(ErrorView, view_args=dict(
                            status_headline=_("Bad transfer"),
                            text=str(e),
                            button_text=_("Back"),
                        ))
                    return self._route(manifest)

                # Live preview + progress overlay
                with self.renderer.lock:
                    preview = frame.convert("RGB").resize(
                        (self.canvas_width, self.canvas_height))
                    self.renderer.canvas.paste(preview, (0, 0))
                    draw = self.renderer.draw
                    if assembler.total:
                        self._draw_progress(draw, assembler, body_font)
                    else:
                        draw.rectangle((0, self.canvas_height - 28,
                                        self.canvas_width, self.canvas_height), fill="black")
                        draw.text((self.canvas_width // 2, self.canvas_height - 14),
                                  _("Point at an animated QR"),
                                  font=body_font, fill="white", anchor="mm")
                    self.renderer.show_image()

        finally:
            camera.stop_video_stream_mode()


    # Per-chunk progress: a single-row segmented bar, same small footprint as a
    # plain progress bar, but each segment is one QR frame so on the second
    # pass of the loop you can see exactly which frames are still missing.
    MISSING_COLOR = "#3a3a3a"
    ACTIVE_COLOR = "#ffd60a"   # the frame scanned most recently
    BAR_HEIGHT = 8
    SEGMENT_LIMIT = 200        # ~1px segments; beyond this show a plain bar

    def _draw_progress(self, draw, assembler, font):
        total = assembler.total
        bar_top = self.canvas_height - 28
        draw.rectangle((0, bar_top - 4, self.canvas_width, self.canvas_height),
                       fill="black")
        if total > self.SEGMENT_LIMIT:
            pct = assembler.num_collected / total
            draw.rectangle((0, bar_top, self.canvas_width, bar_top + self.BAR_HEIGHT),
                           fill=self.MISSING_COLOR)
            draw.rectangle((0, bar_top, int(self.canvas_width * pct),
                            bar_top + self.BAR_HEIGHT), fill=ACCENT)
        else:
            # Gaps between segments only when there's room for them
            gap = 1 if self.canvas_width / total >= 3 else 0
            for i in range(total):
                x0 = round(i * self.canvas_width / total)
                x1 = round((i + 1) * self.canvas_width / total) - gap
                seq = i + 1
                if seq == assembler.last_seq:
                    # Taller + yellow so the sweep is visible at 1-4px widths
                    draw.rectangle((x0, bar_top - 3, x1, bar_top + self.BAR_HEIGHT),
                                   fill=self.ACTIVE_COLOR)
                elif seq in assembler.chunks:
                    draw.rectangle((x0, bar_top, x1, bar_top + self.BAR_HEIGHT),
                                   fill=ACCENT)
                else:
                    draw.rectangle((x0, bar_top, x1, bar_top + self.BAR_HEIGHT),
                                   fill=self.MISSING_COLOR)
        draw.text((self.canvas_width // 2, self.canvas_height - 10),
                  _("{}/{} chunks").format(assembler.num_collected, total),
                  font=font, fill="white", anchor="mm")

    def _route(self, manifest: dict) -> Destination:
        payload_type = manifest["type"]

        if payload_type == "message":
            return Destination(MessageView, view_args=dict(manifest=manifest),
                               skip_current_view=True)

        if payload_type == "image":
            return Destination(ImageView, view_args=dict(manifest=manifest),
                               skip_current_view=True)

        # game
        from pillboy.games.base import GameWelcomeView
        from pillboy.qrload.loader import GameLoadError, load_game
        try:
            game_index = load_game(manifest)
        except GameLoadError as e:
            return Destination(ErrorView, view_args=dict(
                status_headline=_("Game failed to load"),
                text=str(e),
                button_text=_("Back"),
            ))
        return Destination(GameWelcomeView,
                           view_args=dict(game_index=game_index),
                           skip_current_view=True, clear_history=True)



class CameraView(QRScanView):
    """
        Unified viewfinder, phone-style: QR codes are auto-detected in the
        live preview (a PB1 animated transfer just starts collecting, with
        the per-chunk progress bar), and photos can be saved to the album.

        Controls: centre = take photo (high-res still, saved to the album),
        KEY3 = exit.
    """
    FPS = 10
    DECODE_EVERY = 2           # pyzbar every Nth frame keeps preview fluid
    # Camera runs at 960x960 (fits the V1 sensor's binned mode); the preview
    # loop gets GPU-downscaled 480x480 frames, and stills capture at full
    # resolution from the live stream — no mode switching.
    CAPTURE_RESOLUTION = (960, 960)

    def run(self):
        try:
            from pyzbar import pyzbar
        except Exception:
            pyzbar = None      # camera still works, QR detection just off

        camera = self.controller.camera
        try:
            camera.start_video_stream_mode(resolution=(480, 480),
                                           framerate=self.FPS, format="rgb",
                                           capture_resolution=self.CAPTURE_RESOLUTION)
        except Exception:
            return Destination(ErrorView, view_args=dict(
                title=_("Hardware Error"),
                status_headline=_("Cannot access camera"),
                text=_("Check for a loose camera connection."),
                button_text=_("Back"),
            ), skip_current_view=True)

        from pillboy.storage import Storage
        storage = Storage.get_instance()
        buttons = HardwareButtons.get_instance()
        hint_font = Fonts.get_font(GUIConstants.get_body_font_name(), 13)
        body_font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        assembler = QRAssembler()
        frame = None
        frame_n = 0
        toast = None           # (text, expiry_time)

        # Debounce entry: the centre press that selected the Camera tile can
        # still be held — without this it immediately "takes a photo".
        while buttons.has_any_input():
            time.sleep(0.01)

        try:
            while True:
                if buttons.check_for_low(HardwareButtonsConstants.KEY_PRESS):
                    while buttons.has_any_input():
                        time.sleep(0.01)
                    if storage.available():
                        with self.renderer.lock:
                            self.renderer.draw.rectangle(
                                (0, self.canvas_height - 22, self.canvas_width,
                                 self.canvas_height), fill="black")
                            self.renderer.draw.text(
                                (self.canvas_width // 2, self.canvas_height - 6),
                                _("Saving…"), font=hint_font, fill="white", anchor="ms")
                            self.renderer.show_image()
                        name = self._save_photo(camera, frame)
                        toast = (_("Saved {}").format(name) if name
                                 else _("Save failed"), time.time() + 2)
                    else:
                        toast = (_("No storage on this card"), time.time() + 2)

                elif buttons.check_for_low(keys=[HardwareButtonsConstants.KEY3]):
                    while buttons.has_any_input():
                        time.sleep(0.01)
                    return Destination(BackStackView)

                frame = camera.read_video_stream(as_image=True)
                if frame is None:
                    time.sleep(0.05)
                    continue

                frame_n += 1
                # Idle: sample every Nth frame to keep the preview fluid.
                # Transfer in progress: decode EVERY frame — a skipped frame
                # is a missed chunk that costs a whole loop pass to recover.
                scanning = assembler.total is not None
                if pyzbar and (scanning or frame_n % self.DECODE_EVERY == 0):
                    for code in pyzbar.decode(frame.convert("L")):
                        try:
                            assembler.add_frame(code.data.decode("utf-8"))
                        except UnicodeDecodeError:
                            continue

                if assembler.is_complete:
                    try:
                        manifest = assembler.assemble()
                    except QRProtocolError as e:
                        return Destination(ErrorView, view_args=dict(
                            status_headline=_("Bad transfer"),
                            text=str(e),
                            button_text=_("Back"),
                        ))
                    return self._route(manifest)

                with self.renderer.lock:
                    preview = frame.convert("RGB").resize(
                        (self.canvas_width, self.canvas_height))
                    self.renderer.canvas.paste(preview, (0, 0))
                    draw = self.renderer.draw
                    if assembler.total:
                        self._draw_progress(draw, assembler, body_font)
                    elif toast and time.time() < toast[1]:
                        draw.text((self.canvas_width // 2, self.canvas_height - 6),
                                  toast[0], font=hint_font, fill="white", anchor="ms")
                    else:
                        draw.text((self.canvas_width // 2, self.canvas_height - 6),
                                  _("press stick to snap · KEY3: exit"),
                                  font=hint_font, fill=ACCENT, anchor="ms")
                    self.renderer.show_image()

        finally:
            camera.stop_video_stream_mode()

    def _save_photo(self, camera, preview_frame):
        """High-res still straight off the running stream (already exposed,
        current scene). Falls back to the preview frame only if the still
        port itself fails. Returns filename or None."""
        import logging
        from pillboy.storage import Storage
        try:
            img = camera.capture_still()
        except Exception:
            logging.getLogger(__name__).exception("capture_still failed; using preview frame")
            img = preview_frame
        if img is None:
            return None
        # Centre-crop square: the viewfinder is square, the screen is square —
        # a square save fills the album view edge to edge and matches what
        # was framed. Still ~3x the screen resolution, so zoom has detail.
        if img.width != img.height:
            side = min(img.width, img.height)
            left = (img.width - side) // 2
            top = (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side))
        try:
            return Storage.get_instance().save_image(img)
        except Exception:
            return None



@dataclass
class MessageView(View):
    """Displays a received text message. Any button returns to the menu."""
    manifest: dict = None

    def run(self):
        title_font = Fonts.get_font(GUIConstants.get_top_nav_title_font_name(), 18)
        body_font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        draw = self.renderer.draw

        with self.renderer.lock:
            draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill="black")
            draw.text((self.canvas_width // 2, 8), self.manifest.get("name", _("Message")),
                      font=title_font, fill=ACCENT, anchor="mt")

            y = 44
            for paragraph in self.manifest["data"].splitlines():
                for line in textwrap.wrap(paragraph, width=28) or [""]:
                    draw.text((8, y), line, font=body_font, fill="white", anchor="lt")
                    y += 20
                    if y > self.canvas_height - 24:
                        break

            draw.text((self.canvas_width // 2, self.canvas_height - 4),
                      _("press any button"),
                      font=Fonts.get_font(GUIConstants.get_body_font_name(), 12),
                      fill=ACCENT, anchor="ms")
            self.renderer.show_image()

        _wait_any_button_then_release()
        return Destination(BackStackView)



@dataclass
class ImageView(View):
    """
        Displays a received image (base64 JPEG/PNG), centered.
        KEY1 saves it to the album (when storage exists); any other button returns.
    """
    manifest: dict = None

    def run(self):
        from PIL import Image
        from pillboy.storage import Storage

        try:
            img = Image.open(io.BytesIO(base64.b64decode(self.manifest["data"]))).convert("RGB")
        except Exception:
            return Destination(ErrorView, view_args=dict(
                status_headline=_("Bad image"),
                text=_("Could not decode the received image."),
                button_text=_("Back"),
            ), skip_current_view=True)

        storage = Storage.get_instance()
        shown = img.copy()
        shown.thumbnail((self.canvas_width, self.canvas_height))
        hint_font = Fonts.get_font(GUIConstants.get_body_font_name(), 12)
        footer = _("KEY1: save · any other button: back") if storage.available() else ""

        def draw_screen(note=None):
            with self.renderer.lock:
                self.renderer.draw.rectangle(
                    (0, 0, self.canvas_width, self.canvas_height), fill="black")
                self.renderer.canvas.paste(
                    shown,
                    ((self.canvas_width - shown.width) // 2,
                     (self.canvas_height - shown.height) // 2))
                if note or footer:
                    self.renderer.draw.text(
                        (self.canvas_width // 2, self.canvas_height - 4),
                        note or footer, font=hint_font, fill=ACCENT, anchor="ms")
                self.renderer.show_image()

        draw_screen()
        buttons = HardwareButtons.get_instance()
        while True:
            key = buttons.wait_for(HardwareButtonsConstants.ALL_KEYS)
            while buttons.has_any_input():
                time.sleep(0.01)
            if key == HardwareButtonsConstants.KEY1 and storage.available():
                try:
                    name = storage.save_image(img)
                    draw_screen(_("Saved {}").format(name))
                except Exception:
                    draw_screen(_("Save failed"))
                continue
            return Destination(BackStackView)
