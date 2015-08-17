#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime
from PasswordSetting import PasswordSetting
from Crypter import Crypter
from Packer import Packer
from base64 import b64decode, b64encode

PASSWORD_SETTINGS_FILE = os.path.expanduser('~/.ctSESAM.pws')


class PasswordSettingsManager(object):
    """
    Use this class to manage password settings. It can save the settings locally to the settings file and it can
    export them to be sent to a sync server.
    """
    def __init__(self, settings_file=PASSWORD_SETTINGS_FILE):
        self.settings_file = settings_file
        self.remote_data = None
        self.settings = []

    def load_settings_from_file(self, password):
        """
        This loads the saved settings. It is a good idea to call this method the minute you have a password.
        :param password:
        :return:
        """
        if os.path.isfile(self.settings_file):
            crypter = Crypter(password)
            file = open(self.settings_file, 'br')
            saved_settings = json.loads(str(Packer.decompress(crypter.decrypt(file.read())), encoding='utf-8'))
            for data_set in saved_settings['settings']:
                found = False
                i = 0
                while i < len(self.settings):
                    setting = self.settings[i]
                    if setting.get_domain() == data_set['domain']:
                        found = True
                        if datetime.strptime(data_set['mDate'], "%Y-%m-%dT%H:%M:%S") > setting.get_m_date():
                            setting.load_from_dict(data_set)
                            setting.set_synced(setting.get_domain() in saved_settings['synced'])
                    i += 1
                if not found:
                    new_setting = PasswordSetting(data_set['domain'])
                    new_setting.load_from_dict(data_set)
                    new_setting.set_synced(new_setting.get_domain() in saved_settings['synced'])
                    self.settings.append(new_setting)
            file.close()

    # noinspection PyUnresolvedReferences
    def save_settings_to_file(self, password):
        """
        This actually saves the settings to a file on the disk. The file is encrypted so you need to supply the
        password.
        :param password:
        :return:
        """
        crypter = Crypter(password)
        file = open(self.settings_file, 'bw')
        file.write(crypter.encrypt(Packer.compress(json.dumps(self.get_settings_as_list()))))
        file.close()
        try:
            import win32con
            import win32api
            win32api.SetFileAttributes(self.settings_file, win32con.FILE_ATTRIBUTE_HIDDEN)
        except ImportError:
            pass

    def get_setting(self, domain):
        """
        This function always returns a setting. If no setting was stored for the given domain a new PasswordSetting
        object is created.
        :param domain:
        :return:
        """
        for setting in self.settings:
            if setting.get_domain() == domain:
                return setting
        setting = PasswordSetting(domain)
        self.settings.append(setting)
        return setting

    def save_setting(self, setting):
        """
        This saves the supplied setting only in memory. Call save_settings_to_file if you want to have it saved to
        disk.
        :param setting:
        :return:
        """
        for i, existing_setting in enumerate(self.settings):
            if existing_setting.get_domain() == setting.get_domain():
                self.settings.pop(i)
        self.settings.append(setting)

    def delete_setting(self, setting):
        """
        This removes the setting from the internal list. Call save_settings_to_file if you want to have the change
        saved to disk.
        :param setting:
        :return:
        """
        i = 0
        while i < len(self.settings):
            existing_setting = self.settings[i]
            if existing_setting.get_domain() == setting.get_domain():
                self.settings.pop(i)
            else:
                i += 1

    def get_domain_list(self):
        """
        This gives you a list of saved domains.
        :return:
        """
        return [setting.get_domain() for setting in self.settings]

    def get_settings_as_list(self):
        """
        Constructs a dictionary with a list of settings (no PasswordSetting objects but dicts) and a list of
        domain names of synced domains.
        :return:
        """
        settings_list = {'settings': [], 'synced': []}
        for setting in self.settings:
            settings_list['settings'].append(setting.to_dict())
            if setting.is_synced():
                settings_list['synced'].append(setting.get_domain())
        return settings_list

    def get_export_data(self, password):
        """
        This gives you a base64 encoded string of encrypted settings data (the blob).
        :param password:
        :return:
        """
        settings_list = self.get_settings_as_list()['settings']
        if self.remote_data:
            for data_set in self.remote_data:
                if 'deleted' in data_set and data_set['deleted']:
                    for i, setting_dict in enumerate(settings_list):
                        if setting_dict['domain'] == setting_dict['domain'] and datetime.strptime(
                                data_set['mDate'], "%Y-%m-%dT%H:%M:%S") > datetime.strptime(
                                setting_dict['mDate'], "%Y-%m-%dT%H:%M:%S"):
                            settings_list[i] = data_set
                if not data_set['domain'] in [sd['domain'] for sd in settings_list]:
                    settings_list.append({
                        'domain': data_set['domain'],
                        'mDate': datetime.now(),
                        'deleted': True
                    })
        crypter = Crypter(password)
        return b64encode(crypter.encrypt(Packer.compress(json.dumps(settings_list))))

    def update_from_export_data(self, password, data):
        """
        This takes a base64 encoded string of encrypted settings (a blob) and updates the internal list of settings.
        :param password:
        :param data:
        :return:
        """
        crypter = Crypter(password)
        self.remote_data = json.loads(str(Packer.decompress(crypter.decrypt(b64decode(data))), encoding='utf-8'))
        update_remote = False
        for data_set in self.remote_data:
            found = False
            i = 0
            while i < len(self.settings):
                setting = self.settings[i]
                if setting.get_domain() == data_set['domain']:
                    found = True
                    if datetime.strptime(data_set['mDate'], "%Y-%m-%dT%H:%M:%S") > setting.get_m_date():
                        if 'deleted' in data_set and data_set['deleted']:
                            self.settings.pop(i)
                        else:
                            setting.load_from_dict(data_set)
                            setting.set_synced(True)
                            i += 1
                    else:
                        i += 1
                        update_remote = True
                else:
                    i += 1
            if not found:
                new_setting = PasswordSetting(data_set['domain'])
                new_setting.load_from_dict(data_set)
                new_setting.set_synced(True)
                self.settings.append(new_setting)
        for setting in self.settings:
            found = False
            for data_set in self.remote_data:
                if setting.get_domain() == data_set['domain']:
                    found = True
                    if setting.get_m_date() >= datetime.strptime(data_set['mDate'], "%Y-%m-%dT%H:%M:%S"):
                        update_remote = True
            if not found:
                update_remote = True
        return update_remote

    def set_all_settings_to_synced(self):
        """
        Convenience function for marking all saved settings as synced. Call this after a successful update at the
        sync server.
        :return:
        """
        for setting in self.settings:
            setting.set_synced(True)
