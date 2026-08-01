from dataclasses import dataclass
from typing import Any, List

from pillboy.helpers.l10n import mark_for_translation as _mft


class SettingsConstants:
    # Basic defaults
    OPTION__ENABLED = "E"
    OPTION__DISABLED = "D"
    OPTION__PROMPT = "P"
    OPTION__REQUIRED = "R"
    OPTIONS__ENABLED_DISABLED = [
        (OPTION__ENABLED, _mft("Enabled")),
        (OPTION__DISABLED, _mft("Disabled")),
    ]
    OPTIONS__ONLY_DISABLED = [
        (OPTION__DISABLED, _mft("Disabled")),
    ]
    OPTIONS__ENABLED_DISABLED_PROMPT = OPTIONS__ENABLED_DISABLED + [
        (OPTION__PROMPT, _mft("Prompt")),
    ]
    ALL_OPTIONS = OPTIONS__ENABLED_DISABLED_PROMPT + [
        (OPTION__REQUIRED, _mft("Required")),
    ]

    # Locales: English-only for now; these extra constants remain because the GUI's
    # font-selection tables in components.py key off them.
    LOCALE__ARABIC = "ar"
    LOCALE__CHINESE_SIMPLIFIED = "zh_Hans_CN"
    LOCALE__CHINESE_TRADITIONAL = "zh_Hant_TW"
    LOCALE__ENGLISH = "en"
    LOCALE__HINDI = "hi"
    LOCALE__JAPANESE = "ja"
    LOCALE__KOREAN = "ko"
    LOCALE__PERSIAN = "fa"
    LOCALE__THAI = "th"

    ALL_LOCALES = [
        (LOCALE__ENGLISH, "English"),
    ]

    CAMERA_ROTATION__0 = 0
    CAMERA_ROTATION__90 = 90
    CAMERA_ROTATION__180 = 180
    CAMERA_ROTATION__270 = 270
    ALL_CAMERA_ROTATIONS = [
        (CAMERA_ROTATION__0, _mft("0°")),
        (CAMERA_ROTATION__90, _mft("90°")),
        (CAMERA_ROTATION__180, _mft("180°")),
        (CAMERA_ROTATION__270, _mft("270°")),
    ]

    # Individual SettingsEntry attr_names
    SETTING__LOCALE = "locale"
    SETTING__PERSISTENT_SETTINGS = "persistent_settings"
    SETTING__CAMERA_ROTATION = "camera_rotation"
    SETTING__DEBUG = "debug"

    SETTING__DISPLAY_CONFIGURATION = "display_config"
    SETTING__DISPLAY_COLOR_INVERTED = "color_inverted"

    # Hardware config
    DISPLAY_CONFIGURATION__ST7789__240x240 = "st7789_240x240"  # Waveshare 1.3" display hat
    DISPLAY_CONFIGURATION__ST7789__320x240 = "st7789_320x240"
    DISPLAY_CONFIGURATION__ILI9341__320x240 = "ili9341_320x240"
    DISPLAY_CONFIGURATION__ILI9486__480x320 = "ili9486_480x320"
    ALL_DISPLAY_CONFIGURATIONS = [
        (DISPLAY_CONFIGURATION__ST7789__240x240, "st7789 240x240"),
        (DISPLAY_CONFIGURATION__ST7789__320x240, "st7789 320x240"),
        (DISPLAY_CONFIGURATION__ILI9341__320x240, "ili9341 320x240 (beta)"),
    ]

    # Structural constants
    CATEGORY__SYSTEM = "system"
    CATEGORY__DISPLAY = "display"
    CATEGORY__FEATURES = "features"

    VISIBILITY__GENERAL = "general"
    VISIBILITY__ADVANCED = "advanced"
    VISIBILITY__HARDWARE = "hardware"
    VISIBILITY__DEVELOPER = "developer"
    VISIBILITY__HIDDEN = "hidden"

    TYPE__ENABLED_DISABLED = "enabled_disabled"
    TYPE__ENABLED_DISABLED_PROMPT = "enabled_disabled_prompt"
    TYPE__ENABLED_DISABLED_PROMPT_REQUIRED = "enabled_disabled_prompt_required"
    TYPE__SELECT_1 = "select_1"
    TYPE__MULTISELECT = "multiselect"
    TYPE__FREE_ENTRY = "free_entry"

    ALL_ENABLED_DISABLED_TYPES = [
        TYPE__ENABLED_DISABLED,
        TYPE__ENABLED_DISABLED_PROMPT,
        TYPE__ENABLED_DISABLED_PROMPT_REQUIRED,
    ]



@dataclass
class SettingsEntry:
    """
        Defines all the parameters for a single settings entry.

        * selection_options: May be specified as a List(Any) or List(tuple(Any, str)).
            The tuple form is to provide a human-readable display_name.
    """
    category: str
    attr_name: str
    display_name: str
    abbreviated_name: str = None
    visibility: str = SettingsConstants.VISIBILITY__GENERAL
    type: str = SettingsConstants.TYPE__ENABLED_DISABLED
    help_text: str = None
    selection_options: list[tuple[str | int], str] = None
    default_value: Any = None

    def __post_init__(self):
        if self.type == SettingsConstants.TYPE__ENABLED_DISABLED:
            self.selection_options = SettingsConstants.OPTIONS__ENABLED_DISABLED

        elif self.type == SettingsConstants.TYPE__ENABLED_DISABLED_PROMPT:
            self.selection_options = SettingsConstants.OPTIONS__ENABLED_DISABLED_PROMPT

        elif self.type == SettingsConstants.TYPE__ENABLED_DISABLED_PROMPT_REQUIRED:
            self.selection_options = SettingsConstants.ALL_OPTIONS

        # Account for List[tuple] and tuple formats as default_value
        if type(self.default_value) == list and type(self.default_value[0]) == tuple:
            self.default_value = [v[0] for v in self.default_value]
        elif type(self.default_value) == tuple:
            self.default_value = self.default_value[0]

        if not self.abbreviated_name:
            self.abbreviated_name = self.attr_name


    @property
    def selection_options_display_names(self) -> List[str]:
        if type(self.selection_options[0]) == tuple:
            return [v[1] for v in self.selection_options]
        else:
            # Always return a copy so the original can't be altered
            return list(self.selection_options)


    def get_selection_option_value(self, i: int):
        """ Returns the value of the selection option at index `i` """
        value = self.selection_options[i]
        if type(value) == tuple:
            value = value[0]
        return value


    def get_selection_option_display_name_by_value(self, value) -> str:
        for option in self.selection_options:
            if type(option) == tuple:
                option_value = option[0]
                display_name = option[1]
            else:
                option_value = option
                display_name = option
            if option_value == value:
                return _mft(display_name)


    def get_selection_option_value_by_display_name(self, display_name: str):
        for option in self.selection_options:
            if type(option) == tuple:
                option_value = option[0]
                option_display_name = option[1]
            else:
                option_value = option
                option_display_name = option
            if option_display_name == display_name:
                return option_value



class SettingsDefinition:
    """
        Master list of all settings, their possible options, their defaults, and
        on-device display strings.
    """
    # Increment if there are any breaking changes; write migrations to bridge from
    # incompatible prior versions.
    version: int = 1

    settings_entries: List[SettingsEntry] = [
        SettingsEntry(category=SettingsConstants.CATEGORY__SYSTEM,
                      attr_name=SettingsConstants.SETTING__LOCALE,
                      abbreviated_name="lang",
                      display_name=_mft("Language"),
                      type=SettingsConstants.TYPE__SELECT_1,
                      selection_options=SettingsConstants.ALL_LOCALES,
                      default_value=SettingsConstants.LOCALE__ENGLISH),

        SettingsEntry(category=SettingsConstants.CATEGORY__SYSTEM,
                      attr_name=SettingsConstants.SETTING__PERSISTENT_SETTINGS,
                      abbreviated_name="persistent",
                      display_name=_mft("Persistent settings"),
                      visibility=SettingsConstants.VISIBILITY__ADVANCED,
                      default_value=SettingsConstants.OPTION__DISABLED),

        SettingsEntry(category=SettingsConstants.CATEGORY__FEATURES,
                      attr_name=SettingsConstants.SETTING__CAMERA_ROTATION,
                      abbreviated_name="camera",
                      display_name=_mft("Camera rotation"),
                      type=SettingsConstants.TYPE__SELECT_1,
                      visibility=SettingsConstants.VISIBILITY__ADVANCED,
                      selection_options=SettingsConstants.ALL_CAMERA_ROTATIONS,
                      default_value=SettingsConstants.CAMERA_ROTATION__180),

        # Hardware config
        SettingsEntry(category=SettingsConstants.CATEGORY__SYSTEM,
                      attr_name=SettingsConstants.SETTING__DISPLAY_CONFIGURATION,
                      abbreviated_name="disp_conf",
                      display_name=_mft("Display type"),
                      type=SettingsConstants.TYPE__SELECT_1,
                      visibility=SettingsConstants.VISIBILITY__HARDWARE,
                      selection_options=SettingsConstants.ALL_DISPLAY_CONFIGURATIONS,
                      default_value=SettingsConstants.DISPLAY_CONFIGURATION__ST7789__240x240),

        SettingsEntry(category=SettingsConstants.CATEGORY__SYSTEM,
                      attr_name=SettingsConstants.SETTING__DISPLAY_COLOR_INVERTED,
                      abbreviated_name="rgb_inv",
                      display_name=_mft("Invert colors"),
                      type=SettingsConstants.TYPE__ENABLED_DISABLED,
                      visibility=SettingsConstants.VISIBILITY__HARDWARE,
                      default_value=SettingsConstants.OPTION__DISABLED),
    ]


    @classmethod
    def get_settings_entries(cls, visibility: str = SettingsConstants.VISIBILITY__GENERAL) -> List[SettingsEntry]:
        entries = []
        for entry in cls.settings_entries:
            if entry.visibility == visibility:
                entries.append(entry)
        return entries


    @classmethod
    def get_settings_entry(cls, attr_name) -> SettingsEntry:
        for entry in cls.settings_entries:
            if entry.attr_name == attr_name:
                return entry


    @classmethod
    def get_settings_entry_by_abbreviated_name(cls, abbreviated_name: str) -> SettingsEntry:
        for entry in cls.settings_entries:
            if abbreviated_name in [entry.abbreviated_name, entry.attr_name]:
                return entry


    @classmethod
    def get_defaults(cls) -> dict:
        as_dict = {}
        for entry in SettingsDefinition.settings_entries:
            if type(entry.default_value) == list:
                # Must copy the default_value list, otherwise we'll inadvertently change
                # defaults when updating these attrs
                as_dict[entry.attr_name] = list(entry.default_value)
            else:
                as_dict[entry.attr_name] = entry.default_value
        return as_dict
