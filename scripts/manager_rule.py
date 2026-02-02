import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import os, yaml, requests, shutil, subprocess, threading

class RuleManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, rules_dir, log_func):
        super().__init__(parent, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB", corner_radius=12)
        self.rules_dir = rules_dir
        self.log_func = log_func
        self.env_name, self.space_id = self._detect_environment()
        self.log_func(f"[*] Rule Manager Active: {self.env_name} (Space: {self.space_id})") 
        self.trash_dir = "trash"
        os.makedirs(self.trash_dir, exist_ok=True)
        self.all_rules = []
        self._build_ui()
        self.load_rules()

    def _detect_environment(self):
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                stderr=subprocess.STDOUT
            ).decode().strip()
        except Exception:
                branch = "dev"
            
        if branch == "main":
                return "main", "default"
        else:
                return branch, "detection-dev"
                
    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=10, pady=10)

        # Search & Mode
        top = ctk.CTkFrame(container, fg_color="transparent")
        top.pack(fill="x", pady=(0, 5))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter)
        ctk.CTkEntry(top, placeholder_text="Search rules...", textvariable=self.search_var, width=320, height=35).pack(side="left", padx=(0, 10))
        self.mode_var = ctk.StringVar(value="File Mode")
        ctk.CTkOptionMenu(top, values=["File Mode", "Folder Mode"], variable=self.mode_var, width=120, height=35, command=self._on_mode_change).pack(side="left")

        # Buttons
        bot = ctk.CTkFrame(container, fg_color="transparent")
        bot.pack(fill="x", pady=5)
        for text, color, status in [("ENABLE", "#28A745", "test"), ("DISABLE", "#FF3B30", "deprecated")]:
            ctk.CTkButton(bot, text=text, width=80, height=35, fg_color=color, font=("Segoe UI", 11, "bold"),
                          command=lambda s=status: self.set_status(s)).pack(side="left", padx=2)
        ctk.CTkButton(bot, text="DELETE", width=80, height=35, fg_color="#6C757D", font=("Segoe UI", 11, "bold"), command=self.delete).pack(side="left", padx=(10, 5))
        ctk.CTkButton(bot, text="RESTORE", width=80, height=35, fg_color="transparent", border_width=1, text_color="#65676B", font=("Segoe UI", 11, "bold"), command=self.restore).pack(side="left")

        # Treeview
        self.drop = ctk.CTkFrame(container, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB")
        self.tree = ttk.Treeview(self.drop, columns=("Status", "Title"), show="headings", height=8)
        self.tree.heading("Status", text="STATUS"); self.tree.column("Status", width=80, anchor="center")
        self.tree.heading("Title", text="TITLE"); self.tree.column("Title", width=420, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def _on_mode_change(self, _):
        self.search_var.set("")
        self.drop.pack_forget()

    def _filter(self, *_):
        term = self.search_var.get().lower().strip()
        if not term:
            self.drop.pack_forget()
            return
        self.tree.delete(*self.tree.get_children())
        mode = self.mode_var.get()
        if mode == "Folder Mode":
            seen = set()
            for r in self.all_rules:
                folder = os.path.dirname(r['path'])
                fname = os.path.basename(folder)
                if term in fname.lower() and folder not in seen:
                    self.tree.insert("", "end", values=("DIR", f"Folder: {fname}"), tags=(folder,))
                    seen.add(folder)
        else:
            for r in self.all_rules:
                if term in r['file'].lower() or term in r['title'].lower():
                    self.tree.insert("", "end", values=(r['status'], r['title']), tags=(r['path'],))
        if self.tree.get_children(): self.drop.pack(fill="x", pady=(5, 0))

    def delete(self):
        sel = self.tree.selection()
        if not sel: return
        mode, path = self.mode_var.get(), self.tree.item(sel[0], "tags")[0]
        name = os.path.basename(path)

        if not messagebox.askyesno("Confirm", f"Delete {mode}: {name}?"): return
        self.log_func(f"[*] Bulk Deleting {mode}: {name}...")

        def _delete_task():
            current_branch, space_id = self._detect_environment()
            self.log_func(f"[*] Detected Branch: {current_branch.upper()} -> Target Space: {space_id}")
            try:
                # 1. Thu thập tất cả Rule IDs trong mục tiêu (File hoặc Folder)
                host = os.getenv('ELASTIC_HOST2').rstrip('/')
                api_url = f"{host}/api/detection_engine/rules/_bulk_delete" if space_id == "default" \
                        else f"{host}/s/{space_id}/api/detection_engine/rules/_bulk_delete"
                targets = []
                if mode == "Folder Mode":
                    for r, _, fs in os.walk(path):
                        for f in fs:
                            if f.endswith(('.yml', '.yaml')):
                                targets.append(os.path.join(r, f))
                else:
                    targets = [path]

                payload_full = []
                for p in targets:
                    try:
                        with open(p, encoding='utf-8') as f:
                            rid = yaml.safe_load(f).get('id')
                            if rid: payload_full.append({"rule_id": rid})
                    except: continue

                if not payload_full: 
                    return self.log_func("[-] No valid Rule IDs found.")

                # 2. CHUNKING: Chia nhỏ payload để tránh Timeout SIEM (100 rules mỗi batch)
                chunk_size = 100
                chunks = [payload_full[i:i + chunk_size] for i in range(0, len(payload_full), chunk_size)]
                
                env = {k: os.getenv(k) for k in ['ELASTIC_HOST2', 'ELASTIC_USER', 'ELASTIC_PASS']}
                self.log_func(f"[*] Processing {len(payload_full)} rules in {len(chunks)} batches...")

                success_on_siem = True
                for idx, chunk in enumerate(chunks):
                    # Tăng timeout lên 60s cho mỗi đợt gửi
                    res = requests.post(f"{env['ELASTIC_HOST2']}/api/detection_engine/rules/_bulk_delete",
                                        auth=(env['ELASTIC_USER'], env['ELASTIC_PASS']),
                                        headers={"kbn-xsrf": "true", "Content-Type": "application/json"}, 
                                        json=chunk, verify=False, timeout=60)
                    
                    if res.status_code != 200:
                        self.log_func(f"[-] Batch {idx+1} failed (HTTP {res.status_code}). Aborting.")
                        success_on_siem = False
                        break
                    else:
                        self.log_func(f"[+] Batch {idx+1}/{len(chunks)} cleared on SIEM.")

                # 3. Xử lý Local & Git (Chỉ chạy khi SIEM đã xóa xong các batches)
                if success_on_siem:
                    dest = os.path.join(self.trash_dir, f"{name}_dir" if mode == "Folder Mode" else name)
                    if os.path.exists(dest):
                        if os.path.isdir(dest): shutil.rmtree(dest)
                        else: os.remove(dest)
                    shutil.move(path, dest)
                    
                    # Đồng bộ Git
                    try:
                        subprocess.run(["git", "add", "."], check=True)
                        msg = f"SOC-GUI: Bulk Deleted {mode} {name} (Env: {current_branch})"
                        subprocess.run(["git", "commit", "-m", msg], check=True)
                        subprocess.run(["git", "push", "origin", current_branch], check=True)
                        self.log_func(f"SUCCESS: {len(payload_full)} rules removed and Git synced.")
                    except subprocess.CalledProcessError as ge:
                        self.log_func(f"[!] SIEM OK, but Git Error: {ge}")
                else:
                    self.log_func("[-] Process aborted. Local files remain unchanged to prevent desync.")

            except Exception as e: 
                self.log_func(f"[-] Critical Error: {e}")
            finally: 
                self.after(0, self.load_rules)

        threading.Thread(target=_delete_task, daemon=True).start()

    def restore(self):
        mode = self.mode_var.get()
        p = filedialog.askdirectory(initialdir=self.trash_dir) if mode == "Folder Mode" else \
            filedialog.askopenfilename(initialdir=self.trash_dir, filetypes=[("Sigma", "*.yml *.yaml")])
        if not p: return
        self.log_func(f"[*] Restoring {os.path.basename(p)}...")
        def _restore_task():
            try:
                dest = os.path.join(self.rules_dir, os.path.basename(p).replace("_dir", ""))
                shutil.move(p, dest)
                self.after(0, lambda: (self.log_func(f"[+] Restored: {os.path.basename(dest)}"), self.load_rules()))
            except Exception as e: self.log_func(f"[-] Restore error: {e}")
        threading.Thread(target=_restore_task, daemon=True).start()

    def load_rules(self):
        self.all_rules.clear()
        for root, _, files in os.walk(self.rules_dir):
            for f in files:
                if f.lower().endswith(('.yml', '.yaml')):
                    p = os.path.join(root, f)
                    try:
                        with open(p, encoding='utf-8') as file:
                            d = yaml.safe_load(file)
                            if d: self.all_rules.append({
                                "path": p, "file": f, "title": d.get('title', 'N/A'),
                                "status": 'OFF' if str(d.get('status', '')).lower() == 'deprecated' else 'ON'
                            })
                    except: pass
        self._filter()

    def set_status(self, status):
        for item in self.tree.selection():
            path = self.tree.item(item, "tags")[0]
            if os.path.isdir(path): continue
            try:
                with open(path, encoding='utf-8') as f: data = yaml.safe_load(f)
                data['status'] = status
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                self.log_func(f"Updated: {os.path.basename(path)} → {status.upper()}")
            except: pass
        self.load_rules()