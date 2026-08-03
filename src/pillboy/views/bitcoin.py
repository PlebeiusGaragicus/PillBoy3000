"""
    Bitcoin stats app: current block height + USD price via mempool.space.

    Doubles as the "am I actually online?" check: it reports connection
    state explicitly when the fetch fails. Data comes from two tiny public
    endpoints; both must respond within a few seconds or we show offline.
"""
import time

from gettext import gettext as _

from pillboy.gui.components import Fonts, FontAwesomeIconConstants, GUIConstants
from pillboy.hardware.buttons import HardwareButtons, HardwareButtonsConstants
from pillboy.helpers import network
from pillboy.views.view import BackStackView, Destination, View

TIP_HEIGHT_URL = "https://mempool.space/api/blocks/tip/height"
PRICES_URL = "https://mempool.space/api/v1/prices"


class BitcoinView(View):
    """Block height + price. KEY2 refreshes, any other button exits."""

    def _fetch(self):
        height = network.fetch_json(TIP_HEIGHT_URL)      # bare int
        price = network.fetch_json(PRICES_URL)["USD"]    # {"USD": 118000, ...}
        return int(height), int(price)

    def _draw_frame(self, headline, rows, footer):
        title_font = Fonts.get_font(GUIConstants.get_top_nav_title_font_name(), 20)
        body_font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        big_font = Fonts.get_font(GUIConstants.get_top_nav_title_font_name(), 28)
        draw = self.renderer.draw

        with self.renderer.lock:
            draw.rectangle((0, 0, self.canvas_width, self.canvas_height), fill="black")
            draw.text((self.canvas_width // 2, 10), headline,
                      font=title_font, fill=GUIConstants.ACCENT_COLOR, anchor="mt")
            y = 56
            for label, value in rows:
                draw.text((self.canvas_width // 2, y), label,
                          font=body_font, fill="#999999", anchor="mt")
                draw.text((self.canvas_width // 2, y + 20), value,
                          font=big_font, fill="white", anchor="mt")
                y += 68
            draw.text((self.canvas_width // 2, self.canvas_height - 6), footer,
                      font=Fonts.get_font(GUIConstants.get_body_font_name(), 12),
                      fill=GUIConstants.ACCENT_COLOR, anchor="ms")
            self.renderer.show_image()

    def run(self):
        buttons = HardwareButtons.get_instance()

        while True:
            self._draw_frame(_("Bitcoin"), [], _("fetching..."))
            try:
                height, price = self._fetch()
                wifi = " (wifi)" if network.wlan_connected() else ""
                self._draw_frame(
                    _("Bitcoin"),
                    [(_("Block height"), f"{height:,}"),
                     (_("Price"), f"${price:,}")],
                    _("KEY2 refresh · any other button exits") + wifi,
                )
            except Exception:
                hint = (_("fetch failed — try again") if network.wlan_connected()
                        else _("no WiFi connection"))
                self._draw_frame(_("Bitcoin"), [(_("Status"), _("offline"))],
                                 hint + _(" · KEY2 retries"))

            # Wait for input: KEY2 loops back around to refresh, rest exits
            key = buttons.wait_for(HardwareButtonsConstants.ALL_KEYS)
            while buttons.has_any_input():
                time.sleep(0.01)
            if key != HardwareButtonsConstants.KEY2:
                return Destination(BackStackView)
