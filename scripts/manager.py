import os
import yaml
import requests
import shutil
import subprocess
import threading
from tkinter import messagebox, filedialog

class RuleManager:
    def __init__(self, rules_dir, log_func):
        self.rules_dir = rules_dir
        self.log_func = log_func
        self.env_name, self.space_id = self._detect_environment()
        self.log_func(f"[*] Rule Manager Active: {self.env_name} (Space: {self.space_id})")
        self.trash_dir = "trash"
        os.makedirs(self.trash_dir, exist_ok=True)
        self.all_rules = []

    def _detect_environment(self):
        try:
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.STDOUT).decode().strip()
        except Exception: branch = "dev"
        if branch == "main": return "main", "default"
        else: return branch, "detection-dev"

    def on_mode_change(self, search_var, drop_frame):
        search_var.set("")
        drop_frame.pack_forget()

    def filter_logic(self, term, mode, tree, drop_frame):
        term = term.lower().strip()
        if not term:
            drop_frame.pack_forget()
            return
        tree.delete(*tree.get_children())
        if mode == "Folder Mode":
            seen = set()
            for r in self.all_rules:
                folder = os.path.dirname(r['path'])
                fname = os.path.basename(folder)
                if term in fname.lower() and folder not in seen:
                    tree.insert("", "end", values=("DIR", f"Folder: {fname}"), tags=(folder,))
                    seen.add(folder)
        else:
            for r in self.all_rules:
                if term in r['file'].lower() or term in r['title'].lower():
                    tree.insert("", "end", values=(r['status'], r['title']), tags=(r['path'],))
        if tree.get_children(): drop_frame.pack(fill="x", pady=(5, 0))

    def delete(self, tree, mode, refresh_callback):
        sel = tree.selection()
        if not sel: return
        path = tree.item(sel[0], "tags")[0]
        name = os.path.basename(path)
        if not messagebox.askyesno("Confirm", f"Delete {mode}: {name}?"): return
        self.log_func(f"[*] Bulk Deleting {mode}: {name}...")

        def _delete_task():
            current_branch, space_id = self._detect_environment()
            host = os.getenv('KIBANA_HOST', '').rstrip('/')
            api_endpoint = f"{host}/api/detection_engine/rules/_bulk_delete" if space_id == "default" else f"{host}/s/{space_id}/api/detection_engine/rules/_bulk_delete"
            try:
                targets = []
                if mode == "Folder Mode":
                    for r, _, fs in os.walk(path):
                        for f in fs:
                            if f.endswith(('.yml', '.yaml')): targets.append(os.path.join(r, f))
                else: targets = [path]
                payload_full = []
                for p in targets:
                    try:
                        with open(p, encoding='utf-8') as f:
                            rid = yaml.safe_load(f).get('id')
                            if rid: payload_full.append({"rule_id": rid})
                    except: continue
                if not payload_full: return self.log_func("[-] No valid Rule IDs found.")
                chunk_size = 100
                chunks = [payload_full[i:i + chunk_size] for i in range(0, len(payload_full), chunk_size)]
                success_on_siem = True
                for chunk in chunks:
                    res = requests.post(api_endpoint, auth=(os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASS')), headers={"kbn-xsrf": "true", "Content-Type": "application/json"}, json=chunk, verify=False, timeout=60)
                    if res.status_code != 200: success_on_siem = False; break
                if success_on_siem:
                    dest = os.path.join(self.trash_dir, f"{name}_dir" if mode == "Folder Mode" else name)
                    if os.path.exists(dest): shutil.rmtree(dest) if os.path.isdir(dest) else os.remove(dest)
                    shutil.move(path, dest)
                    subprocess.run(["git", "add", "."], check=True)
                    subprocess.run(["git", "commit", "-m", f"SOC-GUI: Deleted {name}"], check=True)
                    subprocess.run(["git", "push", "origin", current_branch], check=True)
                    self.log_func(f"SUCCESS: Removed and Git synced.")
            except Exception as e: self.log_func(f"[-] Critical Error: {e}")
            finally: refresh_callback()
        threading.Thread(target=_delete_task, daemon=True).start()

    def sync_audit(self):
        def _task():
            _, space_id = self._detect_environment()
            host = os.getenv('KIBANA_HOST', '').rstrip('/')
            api = f"{host}{'' if space_id == 'default' else f'/s/{space_id}'}/api/detection_engine/rules/_find"
            try:
                self.log_func("[*] Đang đối soát dữ liệu Repo và Kibana...")
                res = requests.get(
                    api, 
                    auth=(os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASS')),
                    headers={"kbn-xsrf": "true"}, 
                    params={"per_page": 1000}, 
                    verify=False, 
                    timeout=20
                )
                kibana_data = res.json().get('data', [])
                kibana_ids = {r['rule_id'] for r in kibana_data}
                repo_map = {}
                for r in self.all_rules:
                    try:
                        with open(r['path'], encoding='utf-8') as f:
                            rid = yaml.safe_load(f).get('id')
                            if rid:
                                repo_map[rid] = r['file']
                    except:
                        continue
                repo_ids = set(repo_map.keys())
                only_in_repo = repo_ids - kibana_ids
                only_in_kibana = kibana_ids - repo_ids
                self.log_func(f"[!] Thống kê: Repo({len(repo_ids)}) | Kibana({len(kibana_ids)})")
                if not only_in_repo and not only_in_kibana:
                    self.log_func("[+] Đồng bộ hoàn toàn 100%")
                else:
                    self.log_func(f"--- CHI TIẾT SAI LỆCH ({len(only_in_repo) + len(only_in_kibana)}) ---")
                    if only_in_repo:
                        self.log_func(f"[*] Có ở Repo nhưng chưa có trên Kibana ({len(only_in_repo)}):")
                        for rid in only_in_repo:
                            self.log_func(f"  + {repo_map[rid]}")
                    if only_in_kibana:
                        self.log_func(f"[*] Có trên Kibana nhưng đã mất trong Repo ({len(only_in_kibana)}):")
                        for rid in only_in_kibana:
                            self.log_func(f"  - ID: {rid}")
            except Exception as e:
                self.log_func(f"[-] Lỗi đối soát: {str(e)}")
        threading.Thread(target=_task, daemon=True).start()

    def restore(self, mode, refresh_callback):
        p = filedialog.askdirectory(initialdir=self.trash_dir) if mode == "Folder Mode" else filedialog.askopenfilename(initialdir=self.trash_dir, filetypes=[("Sigma", "*.yml *.yaml")])
        if not p: return
        self.log_func(f"[*] Restoring {os.path.basename(p)}...")
        try:
            dest = os.path.join(self.rules_dir, os.path.basename(p).replace("_dir", ""))
            shutil.move(p, dest); self.log_func(f"[+] Restored."); refresh_callback()
        except Exception as e: self.log_func(f"[-] Restore error: {e}")

    def load_rules_data(self):
        self.all_rules.clear()
        for root, _, files in os.walk(self.rules_dir):
            for f in files:
                if f.lower().endswith(('.yml', '.yaml')):
                    p = os.path.join(root, f)
                    try:
                        with open(p, encoding='utf-8') as file:
                            d = yaml.safe_load(file)
                            if d: self.all_rules.append({"path": p, "file": f, "title": d.get('title', 'N/A'), "status": 'OFF' if str(d.get('status', '')).lower() == 'deprecated' else 'ON'})
                    except: pass

    def set_status(self, status, tree, refresh_callback):
        for item in tree.selection():
            path = tree.item(item, "tags")[0]
            if os.path.isdir(path): continue
            try:
                with open(path, encoding='utf-8') as f: data = yaml.safe_load(f)
                data['status'] = status
                with open(path, 'w', encoding='utf-8') as f: yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                self.log_func(f"Updated: {os.path.basename(path)} → {status.upper()}")
            except: pass
        refresh_callback()