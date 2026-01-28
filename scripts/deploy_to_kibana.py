import subprocess
import requests
import sys
import io
import os
import urllib3

# Tắt cảnh báo InsecureRequest khi dùng verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH HỆ THỐNG ---
URL = os.getenv('ELASTIC_URL')
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')

# Giữ nguyên logic đường dẫn cho GitHub Actions
RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def fast_deploy():
    # Bước 1: Chuyển đổi luật Sigma
    print(f"[*] Đang convert rules Sigma từ: {RULES_INPUT}")
    cmd = f'sigma convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode != 0:
        print(f"[-] Lỗi Sigma CLI: {result.stderr}")
        return

    if not os.path.exists(NDJSON_OUTPUT):
        print("[-] Lỗi: Không tạo được file NDJSON.")
        return

    print(f"[+] Convert thành công: {NDJSON_OUTPUT}")

    # Bước 2: Đẩy lên SIEM qua API
    print("[*] Đang đẩy luật lên SIEM qua URL: {URL}")
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            res = requests.post(
                f"{URL}/api/detection_engine/rules/_import",
                headers={"kbn-xsrf": "true"},
                auth=(USER, PASS),
                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                params={"overwrite": "true"},
                verify=False,
                timeout=60
            )

        if res.status_code == 200:
            print("THÀNH CÔNG! Luật đã được nạp vào SIEM.")
        else:
            print(f"Lỗi API SIEM ({res.status_code}): {res.text}")
            
    except Exception as e:
        print(f"[-] Lỗi kết nối: {e}")

if __name__ == "__main__":
    fast_deploy()