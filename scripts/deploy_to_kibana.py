import subprocess
import requests
import sys
import io
import os
import shutil
import yaml
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH HỆ THỐNG ---
URL = os.getenv('ELASTIC_URL') 
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')
SPACE_ID = os.getenv('KIBANA_SPACE', 'default')

RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def get_sigma_path():
    sigma_path = shutil.which("sigma")
    if sigma_path: return f'"{sigma_path}"'
    python_scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    sigma_exe = os.path.join(python_scripts_dir, "sigma.exe")
    if os.path.exists(sigma_exe): return f'"{sigma_exe}"'
    return "sigma"

def inject_and_map_status():
    """Vừa nhúng Metadata, vừa thu thập danh sách Rule ID cần Disable"""
    print("[*] Đang phân tích Rule và ánh xạ trạng thái...")
    disabled_ids = []
    
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if file.endswith(('.yml', '.yaml')):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, start='.').replace(os.sep, '/')
                file_tag = f"[Source: {rel_path}]"
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    if not data: continue
                    
                    # 1. Xử lý Metadata Description
                    original_desc = data.get('description', '')
                    if file_tag not in original_desc:
                        data['description'] = f"{file_tag} {original_desc}".strip()
                        # Lưu ý: Không dùng yaml.dump ở đây để tránh thay đổi status tự động
                    
                    # 2. Kiểm tra status để quyết định Disable
                    # Sigma CLI chỉ chấp nhận: stable, test, experimental, deprecated
                    rule_status = str(data.get('status', '')).lower()
                    
                    # Nếu GUI của bạn lỡ ghi 'disabled', chúng ta tự đổi thành 'deprecated' để Sigma CLI không báo lỗi
                    if rule_status == 'disabled':
                        data['status'] = 'deprecated'
                        with open(file_path, 'w', encoding='utf-8') as f:
                            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                        print(f"  [!] Đã chuyển đổi 'disabled' -> 'deprecated' cho file: {file}")
                        rule_status = 'deprecated'

                    if rule_status == 'deprecated':
                        disabled_ids.append(data.get('id'))
                        print(f"  [-] Nhận diện để TẮT (status: deprecated): {file}")
                        
                except Exception as e:
                    print(f"  [-] Lỗi xử lý file {file}: {e}")
    return disabled_ids

def patch_ndjson(disabled_ids):
    """Sửa file NDJSON: chuyển enabled thành false cho các ID được chọn"""
    if not disabled_ids: return
    
    print(f"[*] Đang thực hiện Patch Disable cho {len(disabled_ids)} rules trong NDJSON...")
    patched_lines = []
    
    with open(NDJSON_OUTPUT, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            rule_data = json.loads(line)
            # Kiểm tra nếu ID nằm trong danh sách cần tắt
            if rule_data.get('rule_id') in disabled_ids:
                rule_data['enabled'] = False # Ép trạng thái về False trên SIEM
            patched_lines.append(json.dumps(rule_data))
            
    with open(NDJSON_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(patched_lines) + '\n')

def fast_deploy():
    # Bước 0: Sửa lỗi status 'disabled' thành 'deprecated' trước khi Sigma CLI quét
    disabled_ids = inject_and_map_status()
    
    sigma_cmd = get_sigma_path()
    
    # Bước 1: Convert rules Sigma sang NDJSON
    # Sigma CLI sẽ chạy mượt vì giờ chỉ còn các status hợp lệ
    cmd = f'{sigma_cmd} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    print("[*] Đang convert rules Sigma...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode != 0:
        print(f"[-] Lỗi Sigma CLI: {result.stderr}")
        return

    # Bước 1.5: Patch file NDJSON (Chuyển deprecated thành enabled: False)
    patch_ndjson(disabled_ids)

    # Bước 2 & 3: Upload API
    api_url = f"{URL}/api/detection_engine/rules/_import" if SPACE_ID == 'default' else f"{URL}/s/{SPACE_ID}/api/detection_engine/rules/_import"
    
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
            print(f"✅ THÀNH CÔNG! Đã cập nhật Space [{SPACE_ID}].")
        else:
            print(f"❌ Lỗi API SIEM ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[-] Lỗi kết nối: {e}")

if __name__ == "__main__":
    fast_deploy()