import logging
import json
import os
import platform

from typing import List

from pillboy.models.settings_definition import SettingsConstants, SettingsDefinition
from pillboy.models.singleton import Singleton

logger = logging.getLogger(__name__)


class Settings(Singleton):
    HOSTNAME = platform.uname()[1]
    PILLBOY_OS = "pillboy-os"
    SETTINGS_FILENAME = "/mnt/microsd/settings.json" if HOSTNAME == PILLBOY_OS else "settings.json"

    @classmethod
    def get_instance(cls):
        # This is the only way to access the one and only instance
        if cls._instance is None:
            # Instantiate the one and only instance
            settings = cls.__new__(cls)
            cls._instance = settings

            settings._data = SettingsDefinition.get_defaults()

            # Read persistent settings file, if it exists
            if os.path.exists(Settings.SETTINGS_FILENAME):
                with open(Settings.SETTINGS_FILENAME) as settings_file:
                    settings.update(json.load(settings_file))

        return cls._instance


    def __str__(self):
        return json.dumps(self._data, indent=4)


    def save(self):
        if self._data[SettingsConstants.SETTING__PERSISTENT_SETTINGS] == SettingsConstants.OPTION__ENABLED:
            with open(Settings.SETTINGS_FILENAME, 'w') as settings_file:
                json.dump(self._data, settings_file, indent=4)
                settings_file.flush()
                os.fsync(settings_file.fileno())


    def update(self, new_settings: dict):
        """
            Replaces the current settings with the incoming dict.

            If a setting is missing from `new_settings`:
                * Hidden settings that have a value remain as-is.
                * All other missing settings are set to their default value.
        """
        for entry in SettingsDefinition.settings_entries:
            if entry.attr_name not in new_settings:
                if entry.visibility == SettingsConstants.VISIBILITY__HIDDEN and entry.attr_name in self._data:
                    # Preserve existing hidden values
                    new_settings[entry.attr_name] = self._data[entry.attr_name]
                else:
                    # Setting is missing; insert default
                    new_settings[entry.attr_name] = entry.default_value

            else:
                # Clean the incoming data, if necessary
                if entry.type == SettingsConstants.TYPE__MULTISELECT:
                    if type(new_settings[entry.attr_name]) == str:
                        # Break comma-separated multiselect options into List; avoid empty
                        # values.
                        new_settings[entry.attr_name] = [value for value in new_settings[entry.attr_name].split(",") if value.strip()]

                    if not new_settings[entry.attr_name]:
                        # Multiselect cannot be empty; load defaults to avoid issues
                        new_settings[entry.attr_name] = entry.default_value

        for key, value in new_settings.items():
            self.set_value(key, value)


    def set_value(self, attr_name: str, value: any):
        """
            Updates the attr's current value.

            Note that for multiselect, the value must be a List.
        """
        if attr_name not in self._data:
            # Outdated settings
            logger.info(f"Setting {attr_name} not recognized. Ignoring.")
            return

        if SettingsDefinition.get_settings_entry(attr_name).type == SettingsConstants.TYPE__MULTISELECT:
            if type(value) != list:
                raise Exception(f"value must be a List for {attr_name}")

        # Special handling for toggling persistence
        if attr_name == SettingsConstants.SETTING__PERSISTENT_SETTINGS and value == SettingsConstants.OPTION__DISABLED:
            try:
                os.remove(self.SETTINGS_FILENAME)
                logger.info(f"Removed {self.SETTINGS_FILENAME}")
            except:
                logger.info(f"{self.SETTINGS_FILENAME} not found to be removed")

        self._data[attr_name] = value
        self.save()


    def get_value(self, attr_name: str, default_if_none: bool = None):
        """
            Returns the attr's current value.

            Note that for multiselect, the current value is a List.
        """
        if attr_name not in self._data:
            if default_if_none:
                return SettingsDefinition.get_settings_entry(attr_name).default_value

            raise Exception(f"Setting for {attr_name} not found")
        return self._data[attr_name]


    def get_value_display_name(self, attr_name: str) -> str:
        """
            Figures out the mapping from value to display_name for the current value's
            tuple(value, display_name) definition, if it's defined that way.

            If the selection_options are defined as simple strings, we just return the
            string.
        """
        if attr_name not in self._data:
            raise Exception(f"Setting for {attr_name} not found")
        settings_entry = SettingsDefinition.get_settings_entry(attr_name)
        if settings_entry.type in [SettingsConstants.TYPE__FREE_ENTRY, SettingsConstants.TYPE__MULTISELECT]:
            raise Exception(f"Unsupported SettingsEntry.type: {settings_entry.type}")
        return settings_entry.get_selection_option_display_name_by_value(value=self._data[attr_name])
