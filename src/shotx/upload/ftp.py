"""FTP and SFTP Uploader Implementations."""

from __future__ import annotations

import ftplib
import logging
from pathlib import Path

import paramiko

from .base import UploaderBackend, UploadError

logger = logging.getLogger(__name__)


class FtpUploader(UploaderBackend):
    """Uploads files to a standard FTP server."""

    def __init__(self, config):
        """Initialize with FTP config object."""
        self.host = config.host
        self.port = config.port or 21
        self.username = config.username
        self.password = config.password
        self.remote_dir = config.remote_dir.rstrip("/")
        self.public_url_format = config.public_url_format
        
        if not self.host:
            raise UploadError("FTP uploader requires a host in settings.")
        if not self.public_url_format:
            raise UploadError("FTP uploader requires a public_url_format in settings (e.g. https://my-site.com/images/{key})")

    def upload(self, file_path: Path) -> str:
        if not file_path.exists():
            raise UploadError(f"File not found: {file_path}")

        file_name = file_path.name
        remote_path = f"{self.remote_dir}/{file_name}" if self.remote_dir else file_name

        logger.info("Uploading %s to ftp://%s ...", file_name, self.host)

        try:
            with ftplib.FTP() as ftp:
                ftp.connect(self.host, self.port)
                if self.username:
                    ftp.login(self.username, self.password)
                else:
                    ftp.login() # Anonymous

                if self.remote_dir:
                    try:
                        ftp.cwd(self.remote_dir)
                    except ftplib.error_perm:
                        # Attempt to create directory if it doesn't exist
                        try:
                            ftp.mkd(self.remote_dir)
                            ftp.cwd(self.remote_dir)
                        except ftplib.all_errors as e:
                            logger.warning("Failed to change to or create remote directory: %s", e)

                with open(file_path, "rb") as f:
                    ftp.storbinary(f"STOR {file_name}", f)
                    
        except ftplib.all_errors as e:
            raise UploadError(f"FTP upload failed: {e}")

        link = self.public_url_format.format(key=file_name, filename=file_name)
        logger.info("FTP upload successful: %s", link)
        return link


class SftpUploader(UploaderBackend):
    """Uploads files to a server via SFTP (SSH)."""

    def __init__(self, config):
        """Initialize with SFTP config object."""
        self.host = config.host
        self.port = config.port or 22
        self.username = config.username
        self.password = config.password
        self.key_file = config.key_file
        self.remote_dir = config.remote_dir.rstrip("/")
        self.public_url_format = config.public_url_format
        
        if not self.host or not self.username:
            raise UploadError("SFTP uploader requires a host and username in settings.")
        if not self.public_url_format:
            raise UploadError("SFTP uploader requires a public_url_format in settings (e.g. https://my-site.com/images/{key})")

    def upload(self, file_path: Path) -> str:
        if not file_path.exists():
            raise UploadError(f"File not found: {file_path}")

        file_name = file_path.name
        
        # Ensure remote_dir is absolute or relative as specified, default to empty
        remote_path = f"{self.remote_dir}/{file_name}" if self.remote_dir else file_name

        logger.info("Uploading %s to sftp://%s@%s ...", file_name, self.username, self.host)

        try:
            transport = paramiko.Transport((self.host, self.port))
            
            # Auth
            if self.key_file:
                # Basic RSA or Ed25519 key loading
                try:
                    pkey = paramiko.Ed25519Key.from_private_key_file(self.key_file, password=self.password)
                except paramiko.SSHException:
                    try:
                        pkey = paramiko.RSAKey.from_private_key_file(self.key_file, password=self.password)
                    except paramiko.SSHException as e:
                         raise UploadError(f"Failed to load SSH key: {e}")
                transport.connect(username=self.username, pkey=pkey)
            else:
                transport.connect(username=self.username, password=self.password)

            sftp = paramiko.SFTPClient.from_transport(transport)
            
            try:
                # If a remote_dir is specified, make sure it exists (rudimentary check/create)
                if self.remote_dir:
                    try:
                        sftp.stat(self.remote_dir)
                    except IOError:
                        try:
                            sftp.mkdir(self.remote_dir)
                        except IOError as e:
                            logger.warning("Failed to create remote directory %s: %s", self.remote_dir, e)

                sftp.put(str(file_path), remote_path)
            finally:
                sftp.close()
                transport.close()
                
        except (paramiko.SSHException, IOError, Exception) as e:
            raise UploadError(f"SFTP upload failed: {e}")

        link = self.public_url_format.format(key=file_name, filename=file_name)
        logger.info("SFTP upload successful: %s", link)
        return link
