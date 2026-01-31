import customtkinter as ctk
from tkinter import ttk, messagebox
import os, yaml, requests, shutil, subprocess

class RuleManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, rules_dir, log_func):
        super().__init__(parent, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB", corner_radius=12)
        self.rules_dir, self.log_func = rules_dir, log_func
        self.trash_dir = "trash"
        self.all_rules = []
        
        if not os.path.exists(self.trash_dir): os.makedirs(self.trash_dir)
        self._init_ui()
        self.load_rules()

    def _init_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=10, pady=10)

        ctrl = ctk.CTkFrame(container, fg_color="transparent")
        ctrl.pack(fill="x")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_logic)
        
        ctk.CTkEntry(ctrl, placeholder_text="🔍 Search rules...", width=350, height=35, 
                     textvariable=self.search_var).pack(side="left", padx=(0, 10))

        # Nút bấm: ON ghi 'test', OFF ghi 'deprecated'
        for txt, color, stat in [("ON", "#28A745", "test"), ("OFF", "#FF3B30", "deprecated")]:
            ctk.CTkButton(ctrl, text=txt, width=50, height=35, fg_color=color, font=("Segoe UI", 11, "bold"),
                          command=lambda s=stat: self.set_status(s)).pack(side="left", padx=2)

        ctk.CTkButton(ctrl, text="DELETE", width=70, height=35, fg_color="#6C757D", font=("Segoe UI", 11, "bold"),
                      command=self.delete_rule_fully).pack(side="left", padx=(10, 0))

        self.drop_frame = ctk.CTkFrame(container, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB")
        self.tree = ttk.Treeview(self.drop_frame, columns=("Status", "Title"), show="headings", height=5)
        for col, w in [("Status", 70), ("Title", 430)]:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=w, anchor="center" if col=="Status" else "w")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def delete_rule_fully(self):
        selected = self.tree.selection()
        if not selected or not messagebox.askyesno("Trash Sync", "Gỡ SIEM và chuyển vào Trash trên GitHub?"): return

        host, user, pwd = os.getenv('ELASTIC_HOST'), os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASS')
        changed, deleted_list = False, []

        for item in selected:
            path = self.tree.item(item, "tags")[0]
            fname = os.path.basename(path)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    rule_id = yaml.safe_load(f).get('id')

                res = requests.delete(f"{host}/api/detection_engine/rules?rule_id={rule_id}", 
                                      auth=(user, pwd), headers={"kbn-xsrf": "true"}, verify=False, timeout=10)
                
                if res.status_code in [200, 404]:
                    shutil.move(path, os.path.join(self.trash_dir, fname))
                    self.tree.delete(item)
                    deleted_list.append(fname)
                    changed = True
                    self.log_func(f"[+] CLEANED: {fname}")
                else:
                    self.log_func(f"[-] SIEM ERR {res.status_code}: {fname} preserved.")
            except Exception as e: self.log_func(f"[-] FAILED {fname}: {e}")

        if changed:
            self.log_func("🚀 SYNCING TRASH TO CLOUD...")
            try:
                msg = f"SOC-GUI: Move {', '.join(deleted_list)} to trash"
                for cmd in [["git", "add", "."], ["git", "commit", "-m", msg], ["git", "push"]]:
                    subprocess.run(cmd, check=True, capture_output=True)
                self.log_func("[⭐] SUCCESS: CLOUD & SIEM IN SYNC.")
            except Exception as ge: self.log_func(f"[!] Git Error: {ge}")
        self.load_rules()

    def load_rules(self):
        self.all_rules = []
        if not os.path.exists(self.rules_dir): return
        for root, _, files in os.walk(self.rules_dir):
            for f in files:
                if f.endswith(('.yml', '.yaml')):
                    p = os.path.join(root, f)
                    try:
                        with open(p, 'r', encoding='utf-8') as file:
                            data = yaml.safe_load(file)
                            # Hiển thị OFF nếu status là deprecated
                            st = 'OFF' if str(data.get('status')).lower() == 'deprecated' else 'ON'
                            self.all_rules.append({"path": p, "file": f, "status": st, "title": data.get('title', 'N/A')})
                    except: pass

    def _filter_logic(self, *args):
        term = self.search_var.get().lower().strip()
        if not term: return self.drop_frame.pack_forget()
        self.tree.delete(*self.tree.get_children())
        res = [r for r in self.all_rules if term in r['file'].lower() or term in r['title'].lower()]
        if res:
            for r in res: self.tree.insert("", "end", values=(r['status'], r['title']), tags=(r['path'],))
            self.drop_frame.pack(fill="x", pady=(5, 0))
        else: self.drop_frame.pack_forget()

    def set_status(self, new_status):
        """Ghi trạng thái Sigma chuẩn: test (ON) hoặc deprecated (OFF)"""
        for item in self.tree.selection():
            path = self.tree.item(item, "tags")[0]
            try:
                with open(path, 'r', encoding='utf-8') as f: data = yaml.safe_load(f)
                
                data['status'] = new_status
                
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                
                disp = 'OFF' if new_status == 'deprecated' else 'ON'
                self.tree.set(item, column="Status", value=disp)
                for r in self.all_rules:
                    if r['path'] == path: r['status'] = disp
                self.log_func(f"DONE: {os.path.basename(path)} -> {new_status.upper()}")
            except Exception as e: self.log_func(f"ERR: {e}")