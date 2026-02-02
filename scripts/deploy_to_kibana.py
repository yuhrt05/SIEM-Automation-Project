import subprocess, requests, sys, io, os, shutil, yaml, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CONFIGURATION ---
URL = os.getenv('ELASTIC_URL') 
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')
SPACE_ID = os.getenv('KIBANA_SPACE', 'detection-dev')

RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def get_sigma_path():
    """Find Sigma CLI path for Windows/Linux"""
    sigma_path = shutil.which("sigma")
    if sigma_path: return f'"{sigma_path}"'
    sigma_exe = os.path.join(os.path.dirname(sys.executable), "Scripts", "sigma.exe")
    return f'"{sigma_exe}"' if os.path.exists(sigma_exe) else "sigma"

def process_rules():
    """Inject Metadata and identify deprecated rules"""
    print("[*] Processing rules and metadata...")
    deprecated_ids = []
    
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if not file.endswith(('.yml', '.yaml')): continue
            
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, '.').replace(os.sep, '/')
            tag = f"[Source: {rel_path}]"
            
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
    """Force 'enabled: false' for deprecated rules in NDJSON"""
    if not deprecated_ids: return
    print(f"[*] Patching {len(deprecated_ids)} rules in NDJSON...")
    
    with open(NDJSON_OUTPUT, 'r', encoding='utf-8') as f:
        lines = [json.loads(line) for line in f if line.strip()]
    
    for rule in lines:
        if rule.get('rule_id') in deprecated_ids:
            rule['enabled'] = False
            
    with open(NDJSON_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(json.dumps(l) for l in lines) + '\n')

def deploy():
    # 1. Prepare Rules & Metadata
    dep_ids = process_rules()
    
    # 2. Sigma Convert
    cmd = f'{get_sigma_path()} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    print("[*] Converting Sigma rules...")
    if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:
        print("[-] Conversion failed.")
        return

    # 3. Patch Status
    patch_ndjson(dep_ids)

    # 4. API Upload
    api = f"{URL}{'' if SPACE_ID == 'detection-dev' else f'/s/{SPACE_ID}'}/api/detection_engine/rules/_import"
    print(f"[*] Deploying to Space [{SPACE_ID}]...")
    
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            res = requests.post(api, headers={"kbn-xsrf": "true"}, auth=(USER, PASS),
                                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                                params={"overwrite": "true"})
        print(f"SUCCESS!" if res.status_code == 200 else f"ERROR ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[-] Connection failed: {e}")

if __name__ == "__main__":
    deploy()

##