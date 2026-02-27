import subprocess, requests, sys, io, os, shutil, yaml, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

URL = os.getenv('ELASTIC_URL') 
USER = os.getenv('ELASTIC_USERNAME')
PASS = os.getenv('ELASTIC_PASSWORD')
SPACE_ID = os.getenv('KIBANA_SPACE', 'default')

RULES_INPUT = 'rules/'
NDJSON_OUTPUT = 'rules/windows_rules.ndjson'

def get_sigma_path():
    sigma_path = shutil.which("sigma")
    if sigma_path:
        return f'"{sigma_path}"'
    print("Error: Sigma CLI tool not found in PATH.")
    sys.exit(1)

def process_rules():
    print("Processing rules and metadata...")
    deprecated_ids = []
    for root, _, files in os.walk(RULES_INPUT):
        for file in files:
            if not file.endswith(('.yml', '.yaml')): continue   
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if not data or not isinstance(data, dict): continue
                if str(data.get('status', '')).lower() == 'deprecated':
                    deprecated_ids.append(data.get('id'))
                    print(f"Target OFF (deprecated): {file}")
            except Exception as e:
                print(f"YAML syntax error in {file}: {e}")
                print("Aborting pipeline due to invalid rule format.")
                sys.exit(1)
    return deprecated_ids

def patch_ndjson(deprecated_ids):
    print("Patching NDJSON for real-time monitoring (interval: 1m)...")
    if not os.path.exists(NDJSON_OUTPUT):
        print("Error: NDJSON file not found. Conversion may have failed silently.")
        sys.exit(1)

    patched_lines = []
    try:
        with open(NDJSON_OUTPUT, 'r', encoding='utf-8') as f:
            lines = [json.loads(line) for line in f if line.strip()]
        for rule in lines:
            rule['interval'] = "1m"
            rule['from'] = "now-120s"
            if rule.get('rule_id') in deprecated_ids:
                rule['enabled'] = False
            patched_lines.append(json.dumps(rule))
        with open(NDJSON_OUTPUT, 'w', encoding='utf-8') as f:
            f.write('\n'.join(patched_lines) + '\n')
        print("Patching completed successfully.")
    except Exception as e:
        print(f"Error processing JSON file: {e}")
        sys.exit(1)

def deploy():
    dep_ids = process_rules()
    
    os.makedirs(os.path.dirname(NDJSON_OUTPUT), exist_ok=True)

    cmd = f'{get_sigma_path()} convert -t lucene -p ecs_windows -f siem_rule_ndjson "{RULES_INPUT}" --skip-unsupported -o "{NDJSON_OUTPUT}"'
    print("Converting Sigma rules...")
    
    process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if process.returncode != 0:
        print("Conversion failed. Sigma standard error output:")
        print(process.stderr)
        sys.exit(1)
        
    patch_ndjson(dep_ids)
    
    api = f"{URL}{'' if SPACE_ID == 'default' else f'/s/{SPACE_ID}'}/api/detection_engine/rules/_import"
    print(f"Deploying to Kibana Space: {SPACE_ID}...")
    
    try:
        with open(NDJSON_OUTPUT, 'rb') as f:
            res = requests.post(api, headers={"kbn-xsrf": "true"}, auth=(USER, PASS),
                                files={'file': ('rules.ndjson', f, 'application/x-ndjson')},
                                params={"overwrite": "true"})
        
        res.raise_for_status() 
        print("Success: All rules deployed and optimized.")
        
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error during Kibana deployment: {err}")
        print(f"Server response: {res.text}")
        sys.exit(1)
    except Exception as e:
        print(f"Connection error to Kibana/Cloudflare: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if not all([URL, USER, PASS]):
        print("CRITICAL ERROR: Missing required environment variables (ELASTIC_URL, ELASTIC_USERNAME, ELASTIC_PASSWORD).")
        sys.exit(1)
        
    deploy()