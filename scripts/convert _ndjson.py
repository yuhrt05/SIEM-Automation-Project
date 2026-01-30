import subprocess
import sys
import io
import os
import shutil
import yaml

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
    """Đọc từng file yaml và chèn đường dẫn đầy đủ vào description"""
    print("[*] Đang thực hiện mapping đường dẫn file vào Metadata...")
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if file.endswith(('.yml', '.yaml')):
                file_path = os.path.join(root, file)
                
                # Tạo đường dẫn tương đối (Ví dụ: rules/powershell_script/posh_ps_...)
                relative_path = os.path.relpath(file_path, start='.')
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    
                    # Chèn Full Path vào đầu phần description để dễ phân biệt ps/pm/classic
                    original_desc = data.get('description', '')
                    # Ghi rõ Source để script AlertMonitor dễ bốc tách
                    file_tag = f"[Source: {relative_path.replace(os.sep, '/')}]"
                    
                    if file_tag not in original_desc:
                        # Ghi đè metadata mới vào description
                        data['description'] = f"{file_tag} {original_desc}"
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                except Exception as e:
                    print(f"[-] Bỏ qua file {file} do lỗi: {e}")

def fast_deploy():
    sigma_cmd = get_sigma_path()
    
    # Bước 0: Inject đường dẫn vào nội dung Rule
    inject_metadata()
    
    # Bước 1: Convert rules Sigma sang NDJSON cho SIEM
    cmd = f'{sigma_cmd} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    
    print(f"[*] Đang sử dụng Sigma CLI: {sigma_cmd}")
    print("[*] Đang convert rules Sigma sang NDJSON...")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode == 0:
        print(f"✅ THÀNH CÔNG! File định danh đã được tạo tại: {NDJSON_OUTPUT}")
        print(f"[*] Metadata đường dẫn đã được nhúng vào từng Rule.")
    else:
        print(f"[-] Lỗi Sigma CLI: {result.stderr}")

if __name__ == "__main__":
    fast_deploy()