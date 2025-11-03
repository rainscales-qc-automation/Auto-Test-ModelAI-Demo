import os
import logging
from typing import Optional, List
from smbclient import register_session, open_file, listdir, stat
from smbclient.path import exists

logger = logging.getLogger(__name__)


class SMBConnector:
    """The class handles connecting and loading video from SMB storage"""

    def __init__(self, server: str, username: str, password: str, root_dir: str = "qc_ai_testing"):
        self.server = server
        self.username = username
        self.password = password
        self.root_dir = root_dir
        self._connected = False

    def connect(self) -> bool:
        """Connect SMB server"""
        try:
            register_session(self.server, username=self.username, password=self.password)
            self._connected = True
            logger.info(f"Connected to {self.server}")
            return True
        except Exception as e:
            logger.error(f"SMB connect error: {e}")
            return False

    def _build_path(self, _dir: str, filename: str = "") -> str:
        """Build UNC path: \\server\share\root\tenant\file"""
        path = f"\\\\{self.server}\\{self.root_dir}\\{_dir}"
        if filename:
            path = os.path.join(path, filename)
        return path

    def get_video(self, _dir: str, video_name: str) -> Optional[bytes]:
        """ Get Video from SMB """
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first")

        try:
            path = self._build_path(_dir, video_name)
            with open_file(path, mode="rb") as f:
                data = f.read()
            logger.info(f"Downloaded {video_name}: {len(data)} bytes")
            return data
        except Exception as e:
            logger.error(f"Download error {video_name}: {e}")
            return None

    def get_video_by_list(self, _dir, list_video_names: List[str]) -> list:
        """ Get multiple videos from SMB by a list of video names. """
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first")
        results = []
        for video_name in list_video_names:
            try:
                path = self._build_path(_dir, video_name)
                with open_file(path, mode="rb") as f:
                    data = f.read()
                logger.info(f"Downloaded {video_name}: {len(data)} bytes")
                results.append((video_name, data))
            except Exception as e:
                logger.error(f"Download error {video_name}: {e}")
                results.append((video_name, None))
        return results

    def video_exists(self, _dir: str, video_name: str) -> bool:
        """Check if video exists"""
        try:
            path = self._build_path(_dir, video_name)
            return exists(path)
        except Exception as e:
            logger.error(f"Check exists error: {e}")
            return False

    def list_files(self, _dir: str) -> List[str]:
        """List files in tenant directory"""
        try:
            path = self._build_path(_dir)
            files = listdir(path)
            return [f for f in files if not f.startswith('.')]
        except Exception as e:
            logger.error(f"List files error: {e}")
            return []

    def get_file_size(self, _dir: str, video_name: str) -> Optional[int]:
        """Get file size (bytes)"""
        try:
            path = self._build_path(_dir, video_name)
            return stat(path).st_size
        except Exception as e:
            logger.error(f"Get size error: {e}")
            return None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        pass  # smbclient auto cleanup


# Usage
if __name__ == "__main__":
    from config.settings import Config
    cf = Config()
    # Example 1: Basic usage
    smb = SMBConnector(cf.SMB_SERVER, cf.SMB_USER, cf.SMB_PASSWORD)

    if smb.connect():
        # Check exists
        if smb.video_exists(r"viet_test", r"test_01.mp4"):
            # Get file size
            size = smb.get_file_size(r"viet_test", r"test_01.mp4")
            print(f"File size: {size / 1024 / 1024:.2f} MB")

            # Download
            video = smb.get_video(r"viet_test", r"test_01.mp4")
            print(f"Downloaded: {len(video)} bytes")

        # List files
        files = smb.list_files("viet_test")
        print(f"Files: {files[:5]}")

    # Example 2: Context manager
    with SMBConnector(Config.SMB_SERVER, Config.SMB_USER, Config.SMB_PASSWORD) as smb:
        video = smb.get_video(r"viet_test", r"test_01.mp4")