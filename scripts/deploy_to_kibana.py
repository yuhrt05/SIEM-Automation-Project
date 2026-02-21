import subprocess, requests, sys, io, os, shutil, yaml, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CONFIGURATION ---
URL = os.getenv('ELASTIC_URL') 
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')
SPACE_ID = os.getenv('KIBANA_SPACE')

RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def get_sigma_path():
    """Find Sigma CLI path for Windows/Linux"""
    sigma_path = shutil.which("sigma")
    if sigma_path: return f'"{sigma_path}"'
    sigma_exe = os.path.join(os.path.dirname(sys.executable), "Scripts", "sigma.exe")
    return f'"{sigma_exe}"' if os.path.exists(sigma_exe) else "sigma"

def process_rules():
    print("[*] Processing rules and metadata...")
    deprecated_ids = []
    
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if not file.endswith(('.yml', '.yaml')): continue   
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if not data: continue
                
                # Identify rules to be disabled on SIEM
                if str(data.get('status', '')).lower() == 'deprecated':
                    deprecated_ids.append(data.get('id'))
                    print(f"  [-] Target OFF (deprecated): {file}")
                        
            except Exception as e:
                print(f"  [-] Error {file}: {e}")
    return deprecated_ids

def patch_ndjson(deprecated_ids):
    print(f"[*] Patching NDJSON for real-time monitoring (interval: 1m)...")
    
    if not os.path.exists(NDJSON_OUTPUT):
        print("[-] NDJSON file not found to patch.")
        return
    patched_lines = []

    with open(NDJSON_OUTPUT, 'r', encoding='utf-8') as f:
        lines = [json.loads(line) for line in f if line.strip()]
    for rule in lines:
        # 1. Vá: Giảm độ trễ từ 5m xuống 1m
        rule['interval'] = "1m"
        rule['from'] = "now-120s"
        
        # 2. Xử lý deprecated rules
        if rule.get('rule_id') in deprecated_ids:
            rule['enabled'] = False
        
        patched_lines.append(json.dumps(rule))
    with open(NDJSON_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(patched_lines) + '\n')
    print("[+] Patching completed successfully.")

def deploy():
    # 1. Prepare Rules & Metadata (Lấy danh sách deprecated IDs)
    dep_ids = process_rules()
    
    # 2. Sigma Convert
    # Chuyển đổi từ Sigma YAML sang Elastic NDJSON
    cmd = f'{get_sigma_path()} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    print("[*] Converting Sigma rules...")
    if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:
        print("[-] Conversion failed.")
        return

    # 3. Patch Status & Performance 
    patch_ndjson(dep_ids)
    # 4. API Upload (Import vào Kibana)
    api = f"{URL}{'' if SPACE_ID == 'default' else f'/s/{SPACE_ID}'}/api/detection_engine/rules/_import"
    print(f"[*] Deploying to Space [{SPACE_ID}]...")
    
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            res = requests.post(api, headers={"kbn-xsrf": "true"}, auth=(USER, PASS),
                                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                                params={"overwrite": "true"})
        if res.status_code == 200:
            print("SUCCESS! All rules deployed and optimized.")
        else:
            print(f"ERROR ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[-] Connection failed: {e}")

if __name__ == "__main__":
    deploy()
