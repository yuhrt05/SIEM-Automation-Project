import subprocess, requests, sys, os, shutil, yaml, json

# --- CONFIGURATION ---
URL = os.getenv('ELASTIC_URL') 
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')
SPACE_ID = os.getenv('KIBANA_SPACE', 'default')

RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def get_sigma_path():
    sigma_path = shutil.which("sigma")
    if sigma_path: return f'"{sigma_path}"'
    sigma_exe = os.path.join(os.path.dirname(sys.executable), "Scripts", "sigma.exe")
    return f'"{sigma_exe}"' if os.path.exists(sigma_exe) else "sigma"

def collect_metadata():
    print("Collecting metadata")
    meta_map = {}
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if not file.endswith(('.yml', '.yaml')): continue
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, '.').replace(os.sep, '/')
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if not data or 'id' not in data: continue
                meta_map[data['id']] = {
                    'status': str(data.get('status', '')).lower(),
                    'rel_path': rel_path
                }
            except:
                print(f"Error reading {file}")
    return meta_map

def patch_ndjson(meta_map):
    if not os.path.exists(NDJSON_OUTPUT):
        print("NDJSON file not found")
        return False
    print("Patching NDJSON data")
    patched_lines = []
    with open(NDJSON_OUTPUT, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            rule = json.loads(line)
            rule_id = rule.get('rule_id')
            if rule_id in meta_map:
                meta = meta_map[rule_id]
                tag = f"[Source: {meta['rel_path']}]"
                if tag not in rule.get('description', ''):
                    rule['description'] = f"{tag} {rule.get('description', '')}".strip()
                if meta['status'] == 'deprecated':
                    rule['enabled'] = False
                    print(f"Disabled deprecated rule: {rule.get('name')}")
            patched_lines.append(json.dumps(rule))
    with open(NDJSON_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(patched_lines) + '\n')
    return True

def deploy():
    if not URL or not USER or not PASS:
        print("Missing credentials")
        return

    meta_map = collect_metadata()
    sigma_cmd = get_sigma_path()
    cmd = f'{sigma_cmd} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    
    print("Converting Sigma rules")
    if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:
        print("Conversion failed")
        return

    if not patch_ndjson(meta_map): return

    api_path = "/api/detection_engine/rules/_import"
    full_url = f"{URL.rstrip('/')}{'' if SPACE_ID == 'default' else f'/s/{SPACE_ID}'}{api_path}"
    
    print(f"Deploying to Kibana Space: {SPACE_ID}")
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            res = requests.post(
                full_url, 
                headers={"kbn-xsrf": "true"}, 
                auth=(USER, PASS),
                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                params={"overwrite": "true"},
                timeout=60
            )
        if res.status_code == 200:
            print(f"Success: {res.json().get('success_count', 0)} rules imported")
        else:
            print(f"Failed: HTTP {res.status_code}")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    deploy()