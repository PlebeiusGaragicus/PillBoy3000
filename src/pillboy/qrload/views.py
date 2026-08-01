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
                        status = _("{}/{} chunks").format(
                            assembler.num_collected, assembler.total)
                        pct = assembler.num_collected / assembler.total
                    else:
                        status = _("Point at an animated QR")
                        pct = 0.0
                    draw.rectangle((0, self.canvas_height - 28,
                                    self.canvas_width, self.canvas_height), fill="black")
                    draw.rectangle((0, self.canvas_height - 28,
                                    int(self.canvas_width * pct), self.canvas_height - 24),
                                   fill=ACCENT)
                    draw.text((self.canvas_width // 2, self.canvas_height - 14),
                              status, font=body_font, fill="white", anchor="mm")
                    self.renderer.show_image()

        finally:
            camera.stop_video_stream_mode()


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
    """Displays a received image (base64 PNG), centered. Any button returns."""
    manifest: dict = None

    def run(self):
        from PIL import Image

        try:
            img = Image.open(io.BytesIO(base64.b64decode(self.manifest["data"]))).convert("RGB")
        except Exception:
            return Destination(ErrorView, view_args=dict(
                status_headline=_("Bad image"),
                text=_("Could not decode the received image."),
                button_text=_("Back"),
            ), skip_current_view=True)

        img.thumbnail((self.canvas_width, self.canvas_height))

        with self.renderer.lock:
            self.renderer.draw.rectangle(
                (0, 0, self.canvas_width, self.canvas_height), fill="black")
            self.renderer.canvas.paste(
                img,
                ((self.canvas_width - img.width) // 2,
                 (self.canvas_height - img.height) // 2))
            self.renderer.show_image()

        _wait_any_button_then_release()
        return Destination(BackStackView)
