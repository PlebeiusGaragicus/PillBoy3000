"""
    Album: browse, zoom and pan saved images.

    The browser IS the viewer -- it opens on the newest photo and the
    joystick moves through the album. Controls:

        fit view:   left/right = previous/next photo
        KEY1        zoom in  (2x steps, up to 8x)
        KEY2        zoomed: zoom out · fit view: delete (centre confirms)
        zoomed:     joystick pans
        centre      reset to fit view
        KEY3        exit

    Images load through Storage, so on release cards the partition is only
    mounted for the moment of the read.
"""
import time

from gettext import gettext as _

from pillboy.gui.components import Fonts, GUIConstants
from pillboy.hardware.buttons import HardwareButtons, HardwareButtonsConstants
from pillboy.storage import Storage
from pillboy.views.view import BackStackView, Destination, View

MAX_ZOOM = 8


class AlbumView(View):

    def run(self):
        storage = Storage.get_instance()
        names = storage.list_images()
        if not names:
            from pillboy.views.view import ErrorView
            return Destination(ErrorView, view_args=dict(
                title=_("Album"),
                status_headline=_("Album is empty"),
                text=_("Save photos from the camera or a QR transfer first."),
                button_text=_("Back"),
            ), skip_current_view=True)

        buttons = HardwareButtons.get_instance()
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 13)
        K = HardwareButtonsConstants

        index = len(names) - 1        # open on the newest photo
        zoom = 1                      # 1 = fit; 2/4/8 = magnification of fit
        cx = cy = 0.5                 # pan centre in source-image fractions
        img = storage.load_image(names[index])
        confirm_delete = False
        dirty = True

        while True:
            if dirty:
                caption = (_("Delete this photo? centre = yes · any other = no")
                           if confirm_delete else
                           f"{index + 1}/{len(names)}  {names[index]}"
                           + (f"  {zoom}x" if zoom > 1 else ""))
                self._render(img, zoom, cx, cy, caption, font,
                             warn=confirm_delete)
                dirty = False

            key = buttons.wait_for(K.ALL_KEYS)

            if confirm_delete:
                while buttons.has_any_input():
                    time.sleep(0.01)
                confirm_delete = False
                if key == K.KEY_PRESS:
                    storage.delete_image(names.pop(index))
                    if not names:
                        return Destination(BackStackView)
                    index = min(index, len(names) - 1)
                    img = storage.load_image(names[index])
                dirty = True
                continue

            if key == K.KEY3:
                while buttons.has_any_input():
                    time.sleep(0.01)
                return Destination(BackStackView)

            if key == K.KEY1 and zoom < MAX_ZOOM:
                zoom *= 2
                dirty = True
            elif key == K.KEY2 and zoom > 1:
                zoom //= 2
                if zoom == 1:
                    cx = cy = 0.5
                dirty = True
            elif key == K.KEY2 and zoom == 1:
                confirm_delete = True
                dirty = True
            elif key == K.KEY_PRESS:
                zoom, cx, cy = 1, 0.5, 0.5
                dirty = True
            elif zoom == 1 and key in (K.KEY_LEFT, K.KEY_RIGHT):
                index = (index + (1 if key == K.KEY_RIGHT else -1)) % len(names)
                img = storage.load_image(names[index])
                cx = cy = 0.5
                dirty = True
            elif zoom > 1 and key in (K.KEY_LEFT, K.KEY_RIGHT, K.KEY_UP, K.KEY_DOWN):
                step = 0.25 / zoom
                if key == K.KEY_LEFT:
                    cx -= step
                elif key == K.KEY_RIGHT:
                    cx += step
                elif key == K.KEY_UP:
                    cy -= step
                else:
                    cy += step
                dirty = True

            # Let a held key repeat-pan without requiring re-press
            time.sleep(0.02)

    def _render(self, img, zoom, cx, cy, caption, font, warn=False):
        from PIL import Image

        cw, ch = self.canvas_width, self.canvas_height
        # fit-scale maps the whole image inside the square screen
        fit = min(cw / img.width, ch / img.height)
        scale = fit * zoom
        # visible source window, clamped inside the image
        vw, vh = cw / scale, ch / scale
        cx = min(max(cx, vw / 2 / img.width), 1 - vw / 2 / img.width) if vw < img.width else 0.5
        cy = min(max(cy, vh / 2 / img.height), 1 - vh / 2 / img.height) if vh < img.height else 0.5
        left = cx * img.width - vw / 2
        top = cy * img.height - vh / 2
        box = (max(0, int(left)), max(0, int(top)),
               min(img.width, int(left + vw)), min(img.height, int(top + vh)))
        view = img.convert("RGB").crop(box)
        ratio = min(cw / view.width, ch / view.height)
        view = view.resize((max(1, int(view.width * ratio)),
                            max(1, int(view.height * ratio))),
                           Image.LANCZOS if zoom == 1 else Image.NEAREST)

        with self.renderer.lock:
            draw = self.renderer.draw
            draw.rectangle((0, 0, cw, ch), fill="black")
            self.renderer.canvas.paste(view, ((cw - view.width) // 2,
                                              (ch - view.height) // 2))
            if warn:
                draw.rectangle((0, ch - 18, cw, ch), fill="black")
            draw.text((cw // 2, ch - 4), caption, font=font,
                      fill="#ff5555" if warn else GUIConstants.ACCENT_COLOR,
                      anchor="ms")
            self.renderer.show_image()
