# Mobile Verification Toolkit (MVT)
# Copyright (c) 2021 MVT Project Developers.
# See the file 'LICENSE' for usage and copying permissions, or find a copy at
#   https://github.com/mvt-project/mvt/blob/main/LICENSE

import binascii
import logging
import os
import shutil
import sqlite3

from iOSbackup import iOSbackup

log = logging.getLogger(__name__)

class DecryptBackup:
    """This class provides functions to decrypt an encrypted iTunes backup
    using either a password or a key file.
    """

    def __init__(self, backup_path, dest_path=None):
        """Decrypts an encrypted iOS backup.
        :param backup_path: Path to the encrypted backup folder
        :param dest_path: Path to the folder where to store the decrypted backup
        """
        self.backup_path = backup_path
        self.dest_path = dest_path
        self._backup = None
        self._decryption_key = None

    def process_backup(self):
        if not os.path.exists(self.dest_path):
            os.makedirs(self.dest_path)

        manifest_path = os.path.join(self.dest_path, "Manifest.db")
        # We extract a decrypted Manifest.db.
        self._backup.getManifestDB()
        # We store it to the destination folder.
        shutil.copy(self._backup.manifestDB, manifest_path)

        for item in self._backup.getBackupFilesList():
            try:
                file_id = item["backupFile"]
                relative_path = item["relativePath"]
                domain = item["domain"]

                # This may be a partial backup. Skip files from the manifest which do not exist locally.
                source_file_path = os.path.join(self.backup_path, file_id[0:2], file_id)
                if not os.path.exists(source_file_path):
                    log.debug("Skipping file %s. File not found in encrypted backup directory.",
                              source_file_path)
                    continue

                item_folder = os.path.join(self.dest_path, file_id[0:2])
                if not os.path.exists(item_folder):
                    os.makedirs(item_folder)

                # iOSBackup getFileDecryptedCopy() claims to read a "file" parameter
                # but the code actually is reading the "manifest" key.
                # Add manifest plist to both keys to handle this.
                item["manifest"] = item["file"]

                self._backup.getFileDecryptedCopy(manifestEntry=item,
                                                  targetName=file_id,
                                                  targetFolder=item_folder)
                log.info("Decrypted file %s [%s] to %s/%s", relative_path, domain, item_folder, file_id)
            except Exception as e:
                log.error("Failed to decrypt file %s: %s", relative_path, e)

    def decrypt_with_password(self, password):
        """Decrypts an encrypted iOS backup.
        :param password: Password to use to decrypt the original backup
        """
        log.info("Decrypting iOS backup at path %s with password", self.backup_path)

        try:
            self._backup = iOSbackup(udid=os.path.basename(self.backup_path),
                                     cleartextpassword=password,
                                     backuproot=os.path.dirname(self.backup_path))
        except Exception as e:
            log.exception(e)
            log.critical("Failed to decrypt backup. Did you provide the correct password?")

    def decrypt_with_key_file(self, key_file):
        """Decrypts an encrypted iOS backup using a key file.
        :param key_file: File to read the key bytes to decrypt the backup
        """
        log.info("Decrypting iOS backup at path %s with key file %s",
                 self.backup_path, key_file)

        with open(key_file, "rb") as handle:
            key_bytes = handle.read()

        # Key should be 64 hex encoded characters (32 raw bytes)
        if len(key_bytes) != 64:
            log.critical("Invalid key from key file. Did you provide the correct key file?")
            return

        try:
            key_bytes_raw = binascii.unhexlify(key_bytes)
            self._backup = iOSbackup(udid=os.path.basename(self.backup_path),
                                     derivedkey=key_bytes_raw,
                                     backuproot=os.path.dirname(self.backup_path))
        except Exception as e:
            log.exception(e)
            log.critical("Failed to decrypt backup. Did you provide the correct key file?")

    def get_key(self):
        """Retrieve and prints the encryption key.
        """
        if not self._backup:
            return

        self._decryption_key = self._backup.getDecryptionKey()
        log.info("Derived decryption key for backup at path %s is: \"%s\"",
                 self.backup_path, self._decryption_key)

    def write_key(self, key_path):
        """Save extracted key to file.
        :param key_path: Path to the file where to write the derived decryption key.
        """
        if not self._decryption_key:
            return

        try:
            with open(key_path, 'w') as handle:
                handle.write(self._decryption_key)
        except Exception as e:
            log.exception(e)
            log.critical("Failed to write key to file: %s", key_path)
            return
        else:
            log.info("Wrote decryption key to file: %s. This file is equivalent to a plaintext password. Keep it safe!",
                     key_path)
