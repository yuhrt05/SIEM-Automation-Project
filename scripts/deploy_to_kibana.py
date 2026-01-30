import subprocess
import requests
import sys
import io
import os
import shutil
import yaml # Cần đảm bảo pip install pyyaml trong GitHub Actions

# Đảm bảo in tiếng Việt không lỗi
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH HỆ THỐNG ---
URL = os.getenv('ELASTIC_URL') 
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')
SPACE_ID = os.getenv('KIBANA_SPACE', 'default')

RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def get_sigma_path():
    """Tìm lệnh sigma phù hợp cho cả Windows và Linux"""
    sigma_path = shutil.which("sigma")
    if sigma_path:
        return f'"{sigma_path}"'
    python_scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    sigma_exe = os.path.join(python_scripts_dir, "sigma.exe")
    if os.path.exists(sigma_exe):
        return f'"{sigma_exe}"'
    return "sigma"

def inject_metadata():
    """Tự động chèn đường dẫn file vào description của từng Rule Sigma"""
    print("[*] Đang kiểm tra và nhúng Metadata đường dẫn file...")
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if file.endswith(('.yml', '.yaml')):
                file_path = os.path.join(root, file)
                # Tạo tag đường dẫn (Ví dụ: [Source: rules/powershell/powershell_script/abc.yml])
                rel_path = os.path.relpath(file_path, start='.').replace(os.sep, '/')
                file_tag = f"[Source: {rel_path}]"
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    
                    if not data: continue
                    
                    original_desc = data.get('description', '')
                    
                    # Kiểm tra nếu chưa có tag thì mới chèn
                    if file_tag not in original_desc:
                        data['description'] = f"{file_tag} {original_desc}".strip()
                        with open(file_path, 'w', encoding='utf-8') as f:
                            # sort_keys=False để giữ nguyên thứ tự các trường trong file Sigma
                            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                        print(f"  [+] Đã cập nhật: {file}")
                except Exception as e:
                    print(f"  [-] Lỗi xử lý file {file}: {e}")

def fast_deploy():
    # Bước 0: Tự động cập nhật Metadata trước khi convert
    inject_metadata()
    
    sigma_cmd = get_sigma_path()
    print(f"[*] Đang sử dụng Sigma CLI: {sigma_cmd}")
    print(f"[*] Mục tiêu: Space [{SPACE_ID}]")
    
    # Bước 1: Convert rules Sigma sang NDJSON
    cmd = f'{sigma_cmd} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    print("[*] Đang convert rules Sigma...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode != 0:
        print(f"[-] Lỗi Sigma CLI: {result.stderr}")
        return

    # Bước 2: Xây dựng URL API dựa trên Space
    if SPACE_ID == 'default':
        api_url = f"{URL}/api/detection_engine/rules/_import"
    else:
        api_url = f"{URL}/s/{SPACE_ID}/api/detection_engine/rules/_import"

    # Bước 3: Nạp file lên Kibana SIEM qua API với ghi đè (overwrite)
    print(f"[*] Đang đẩy luật lên SIEM qua API: {api_url}...")
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            res = requests.post(
                api_url,
                headers={"kbn-xsrf": "true"},
                auth=(USER, PASS),
                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                params={"overwrite": "true"}
            )
        if res.status_code == 200:
            print(f"✅ THÀNH CÔNG! Luật đã được cập nhật vào Space [{SPACE_ID}].")
        else:
            print(f"❌ Lỗi API SIEM ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[-] Lỗi kết nối: {e}")

if __name__ == "__main__":
    fast_deploy()