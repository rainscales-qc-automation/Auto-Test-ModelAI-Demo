import smbclient
import requests


a = smbclient.register_session("192.168.1.57", username='163019-viettq2', password="VietTran@102025")

file = smbclient.open_file(r"\\192.168.1.57\qc_ai_testing\viet_test\test_01.mp4", mode="rb")
# # # with smbclient.open_file(r"//192.168.1.57/qc_ai_testing/viet_test/video_01.mp4", mode="rb") as f:
# # #     files = {"video": f}
# #     # response = requests.post(api_url, files=files)
# #
# # # files = {"video": open(video_url, "rb")}
b = 1

# list_smb_files.py
import smbclient
import sys
from smbprotocol.exceptions import SMBOSError

# --- Cấu hình: sửa lại ---
HOST = "192.168.1.57"
SHARE = "qc_ai_testing"
USERNAME = "163019-viettq2"   # hoặc "guest"
PASSWORD = "VietTran@102025"   # hoặc "" nếu guest
# --------------------------

BASE = rf"\\{HOST}\{SHARE}"

def register():
    # đăng ký session (bắt buộc)
    smbclient.register_session(HOST, username=USERNAME, password=PASSWORD)

def listdir_safe(path):
    try:
        return smbclient.listdir(path)
    except SMBOSError as e:
        # trả None khi không thể list (thường là không phải folder hoặc không có quyền)

        return None


def walk_smb(path):
    """
    yield đường dẫn file đầy đủ (SMB path) cho từng file tìm được
    path: bắt đầu là BASE hoặc subfolder path
    """
    entries = listdir_safe(path)
    if entries is None:
        # không thể list => có thể đây là file hoặc không có quyền
        return

    for name in entries:
        # tránh các entry '.' hoặc '..' (nếu có)
        if name in (".", ".."):
            continue
        item_path = path + "\\" + name
        # thử list chính item để kiểm tra có phải folder không
        sub = listdir_safe(item_path)
        if sub is None:
            # không list được => coi là file (hoặc item không thể truy cập)
            yield item_path
        else:
            # là thư mục => lặp tiếp
            yield from walk_smb(item_path)

def save_list(output_file="smb_files.txt"):
    with open(output_file, "w", encoding="utf-8") as f:
        count = 0
        for file_path in walk_smb(BASE):
            smbclient.open_file(file_path, mode="rb")
            count += 1
            f.write(file_path + "\n")
            count += 1
        print(f"Đã ghi {count} file vào {output_file}")

if __name__ == "__main__":
    try:
        register()
    except Exception as e:
        print("Không thể register session:", e)
        sys.exit(1)

    # kiểm tra share tồn tại bằng cách list gốc
    root = listdir_safe(BASE)
    if root is None:
        print("Không thể truy cập share gốc:", BASE)
        sys.exit(1)

    save_list("smb_files.txt")
