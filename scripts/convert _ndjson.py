import subprocess
import sys
import io
import os
import shutil
import yaml # Cần cài đặt: pip install pyyaml

# Đảm bảo in tiếng Việt không lỗi
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH ---
RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def get_sigma_path():
    sigma_path = shutil.which("sigma")
    if sigma_path:
        return f'"{sigma_path}"'
    python_scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    sigma_exe = os.path.join(python_scripts_dir, "sigma.exe")
    if os.path.exists(sigma_exe):
        return f'"{sigma_exe}"'
    return "sigma"

def inject_metadata():
    """Đọc từng file yaml và chèn tên file vào description để truy vết"""
    print("[*] Đang thực hiện mapping tên file vào Metadata...")
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if file.endswith(('.yml', '.yaml')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    
                    # Chèn tên file vào đầu phần description
                    original_desc = data.get('description', '')
                    file_tag = f"[Source File: {file}]"
                    
                    if file_tag not in original_desc:
                        data['description'] = f"{file_tag} {original_desc}"
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                except Exception as e:
                    print(f"[-] Bỏ qua file {file} do lỗi: {e}")

def fast_deploy():
    sigma_cmd = get_sigma_path()
    
    # Bước 0: Inject tên file vào nội dung Rule trước khi convert
    inject_metadata()
    
    # Bước 1: Convert rules Sigma sang NDJSON
    # Sử dụng siem_rule_ndjson để tạo định dạng chuẩn cho Kibana
    cmd = f'{sigma_cmd} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    
    print(f"[*] Đang sử dụng Sigma CLI: {sigma_cmd}")
    print("[*] Đang convert rules Sigma sang NDJSON...")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode == 0:
        print(f"✅ THÀNH CÔNG! File định danh đã được tạo tại: {NDJSON_OUTPUT}")
        print(f"[*] Giờ đây mỗi Rule trong NDJSON đều đã chứa thông tin 'Source File' bên trong mô tả.")
    else:
        print(f"[-] Lỗi Sigma CLI: {result.stderr}")

if __name__ == "__main__":
    # Script này giờ chỉ tạo file, không đẩy lên SIEM
    fast_deploy()