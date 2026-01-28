import subprocess
import requests
import sys
import os
from pathlib import Path

# --- CẤU HÌNH HỆ THỐNG (Lấy từ Secrets của GitHub) ---
URL = os.getenv('ELASTIC_URL')
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')

# Định nghĩa đường dẫn cố định trên GitHub Runner
RULES_INPUT = Path('rules/')
NDJSON_OUTPUT = Path('rules/windows_rules.ndjson')

def fast_deploy():
    # Kiểm tra biến môi trường quan trọng
    if not all([URL, USER, PASS]):
        print("[-] Thiếu biến môi trường (URL/USER/PASS). Kiểm tra GitHub Secrets!")
        sys.exit(1)

    print(f"[*] Khởi động Pipeline Automation...")
    print(f"[*] Đích đến SIEM: {URL}")
    
    # BƯỚC 1: CONVERT RULES SIGMA SANG NDJSON
    cmd = [
        "sigma", "convert",
        "-t", "lucene",
        "-p", "ecs_windows",
        "-f", "siem_rule_ndjson",
        str(RULES_INPUT),
        "--skip-unsupported",
        "-o", str(NDJSON_OUTPUT)
    ]
    
    print("[*] Đang chuyển đổi luật Sigma sang định dạng Elastic SIEM (NDJSON)...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"[+] Chuyển đổi hoàn tất: {NDJSON_OUTPUT}")
    except subprocess.CalledProcessError as e:
        print(f"[-] Lỗi Sigma CLI (Exit Code {e.returncode}):\n{e.stderr}")
        sys.exit(1)

    # BƯỚC 2: NẠP FILE LÊN KIBANA SIEM QUA API
    if not NDJSON_OUTPUT.exists():
        print("[-] Lỗi: File NDJSON không tồn tại sau khi convert.")
        sys.exit(1)

    print("[*] Đang đẩy luật lên SIEM qua API...")
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            response = requests.post(
                f"{URL.rstrip('/')}/api/detection_engine/rules/_import",
                headers={"kbn-xsrf": "true"},
                auth=(USER, PASS),
                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                params={"overwrite": "true"},
                timeout=30
            )

        if response.status_code == 200:
            result_data = response.json()
            success_count = result_data.get('success_count', 0)
            print(f"[+++] THÀNH CÔNG! Đã nạp {success_count} luật vào hệ thống SIEM.")
        else:
            print(f"[-] Lỗi API SIEM (Status: {response.status_code})")
            print(f"[-] Chi tiết: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"[-] Lỗi kết nối mạng: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fast_deploy()