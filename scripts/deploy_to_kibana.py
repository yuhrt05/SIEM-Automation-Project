import subprocess
import requests
import sys
import io
import os
import shutil
# Đảm bảo in tiếng Việt không lỗi trên mọi môi trường
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# --- CẤU HÌNH HỆ THỐNG ---
# Ưu tiên lấy từ biến môi trường (GitHub Secrets), nếu không có mới dùng giá trị mặc định
URL = os.getenv('ELASTIC_URL')
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')

if os.getenv('GITHUB_ACTIONS'):
    RULES_INPUT = 'rules/'
    NDJSON_OUTPUT = 'rules/windows_rules.ndjson'
else:
    # Đường dẫn trên máy Windows của Phanh
    RULES_INPUT = 'd:/SIEM-Automation-Project/rules/' 
    NDJSON_OUTPUT = 'd:/SIEM-Automation-Project/rules/windows_rules.ndjson'

def get_sigma_path():
    """Tìm lệnh sigma phù hợp cho cả Windows và Linux (GitHub Actions)"""
    sigma_path = shutil.which("sigma")
    if sigma_path:
        return f'"{sigma_path}"'
    
    # Check riêng cho môi trường Windows
    python_scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    sigma_exe = os.path.join(python_scripts_dir, "sigma.exe")
    if os.path.exists(sigma_exe):
        return f'"{sigma_exe}"'
    
    return "sigma"

def fast_deploy():
    sigma_cmd = get_sigma_path()
    print(f"[*] Đang sử dụng Sigma CLI: {sigma_cmd}")
    print(f"[*] Kết nối đến SIEM qua URL: {URL}") # Sẽ dùng link Cloudflare nếu chạy trên GitHub
    
    # Bước 1: Convert rules Sigma sang NDJSON
    cmd = f'{sigma_cmd} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    
    print("[*] Đang convert rules Sigma...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode != 0:
        print(f"[-] Lỗi Sigma CLI: {result.stderr}")
        return

    if not os.path.exists(NDJSON_OUTPUT):
        print("[-] Lỗi: Không tạo được file NDJSON.")
        return

    print(f"[+] Convert thành công: {NDJSON_OUTPUT}")

    # Bước 2: Nạp file lên Kibana SIEM qua API
    print("[*] Đang đẩy luật lên SIEM...")
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            res = requests.post(
                f"{URL}/api/detection_engine/rules/_import",
                headers={"kbn-xsrf": "true"},
                auth=(USER, PASS),
                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                params={"overwrite": "true"}
            )

        if res.status_code == 200:
            print("🔥 THÀNH CÔNG! Luật đã được nạp vào SIEM.")
        else:
            print(f"❌ Lỗi API SIEM ({res.status_code}): {res.text}")
            
    except Exception as e:
        print(f"[-] Lỗi kết nối: {e}")

if __name__ == "__main__":
    fast_deploy()