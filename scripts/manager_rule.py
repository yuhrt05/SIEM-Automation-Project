import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import os, yaml, requests, shutil, subprocess

class RuleManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, rules_dir, log_func):
        super().__init__(parent, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB", corner_radius=12)
        self.rules_dir, self.log_func = rules_dir, log_func
        self.trash_dir = "trash"
        self.all_rules = []
        os.makedirs(self.trash_dir, exist_ok=True)
        self._init_ui()
        self.load_rules()

    def _init_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=10, pady=10)

        # Top Bar: Search & Mode
        ctrl_top = ctk.CTkFrame(container, fg_color="transparent")
        ctrl_top.pack(fill="x", pady=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_logic)
        
        self.search_entry = ctk.CTkEntry(ctrl_top, placeholder_text="Search rules...", width=320, height=35, textvariable=self.search_var)
        self.search_entry.pack(side="left", padx=(0, 10))

        self.delete_mode = ctk.StringVar(value="File Mode")
        ctk.CTkOptionMenu(ctrl_top, values=["File Mode", "Folder Mode"], variable=self.delete_mode, 
                          width=120, height=35, command=self._on_mode_change).pack(side="left")

        # Bottom Bar: Actions
        ctrl_bot = ctk.CTkFrame(container, fg_color="transparent")
        ctrl_bot.pack(fill="x", pady=5)

        for t, c, s in [("ENABLE", "#28A745", "test"), ("DISABLE", "#FF3B30", "deprecated")]:
            ctk.CTkButton(ctrl_bot, text=t, width=80, height=35, fg_color=c, font=("Segoe UI", 11, "bold"),
                          command=lambda stat=s: self.set_status(stat)).pack(side="left", padx=2)

        ctk.CTkButton(ctrl_bot, text="DELETE", width=80, height=35, fg_color="#6C757D", font=("Segoe UI", 11, "bold"),
                      command=self.delete_rule_fully).pack(side="left", padx=(10, 5))
        
        ctk.CTkButton(ctrl_bot, text="RESTORE", width=80, height=35, fg_color="transparent", border_width=1, 
                      text_color="#65676B", font=("Segoe UI", 11, "bold"), command=self.restore_logic).pack(side="left")

        # Treeview
        self.drop_frame = ctk.CTkFrame(container, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB")
        self.tree = ttk.Treeview(self.drop_frame, columns=("Status", "Title"), show="headings", height=8)
        for col, w in [("Status", 80), ("Title", 420)]:
            self.tree.heading(col, text=col.upper()); self.tree.column(col, width=w, anchor="center" if col=="Status" else "w")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def _on_mode_change(self, mode):
        self.search_entry.configure(placeholder_text=f"Search by {mode.split()[0]} name...")
        self.search_var.set(""); self.drop_frame.pack_forget()

    def _filter_logic(self, *args):
        term = self.search_var.get().lower().strip()
        if not term: return self.drop_frame.pack_forget()
        self.tree.delete(*self.tree.get_children())
        
        mode, results = self.delete_mode.get(), []
        if mode == "Folder Mode":
            seen = set()
            for r in self.all_rules:
                f_path = os.path.dirname(r['path'])
                f_name = os.path.basename(f_path)
                if term in f_name.lower() and f_path not in seen:
                    self.tree.insert("", "end", values=("DIR", f"Folder: {f_name}"), tags=(f_path,))
                    seen.add(f_path); results.append(f_path)
        else:
            res = [r for r in self.all_rules if term in r['file'].lower() or term in r['title'].lower()]
            for r in res:
                self.tree.insert("", "end", values=(r['status'], r['title']), tags=(r['path'],))
                results.append(r)
        self.drop_frame.pack(fill="x", pady=(5, 0)) if results else self.drop_frame.pack_forget()

    def delete_rule_fully(self):
        selected = self.tree.selection()
        if not selected: return
        
        mode, path = self.delete_mode.get(), self.tree.item(selected[0], "tags")[0]
        name = os.path.basename(path)
        if not messagebox.askyesno("Confirm", f"Delete {mode}: {name}?"): return

        targets = [os.path.join(root, f) for root, _, files in os.walk(path) for f in files if f.endswith(('.yml', '.yaml'))] if mode == "Folder Mode" else [path]
        
        host, user, pwd = os.getenv('ELASTIC_HOST2'), os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASS')
        changed = False
        for p in targets:
            try:
                with open(p, 'r', encoding='utf-8') as f: rid = yaml.safe_load(f).get('id')
                res = requests.delete(f"{host}/api/detection_engine/rules?rule_id={rid}", auth=(user, pwd), headers={"kbn-xsrf": "true"}, verify=False, timeout=10)
                if res.status_code in [200, 404]:
                    self.log_func(f"[+] SIEM: Cleaned {os.path.basename(p)}")
                    changed = True
            except Exception as e: self.log_func(f"[-] Error {p}: {e}")

        if changed:
            try:
                dest_name = f"{name}_dir" if mode == "Folder Mode" else name
                shutil.move(path, os.path.join(self.trash_dir, dest_name))
                for cmd in [["git", "add", "."], ["git", "commit", "-m", f"SOC-GUI: Deleted {mode}"], ["git", "push"]]:
                    subprocess.run(cmd, capture_output=True)
                self.log_func(f"SUCCESS: {mode} Sync complete.")
            except Exception as e: self.log_func(f"[!] Sync Error: {e}")
        self.load_rules()

    def restore_logic(self):
        mode = self.delete_mode.get()
        p = filedialog.askdirectory(initialdir=self.trash_dir) if mode == "Folder Mode" else filedialog.askopenfilename(initialdir=self.trash_dir, filetypes=[("Sigma", "*.yml *.yaml")])
        if p:
            dest = os.path.join(self.rules_dir, os.path.basename(p).replace("_dir", ""))
            shutil.move(p, dest)
            self.log_func(f"[+] RESTORED: {os.path.basename(dest)}")
            self.load_rules()

    def load_rules(self):
        self.all_rules = []
        for root, _, files in os.walk(self.rules_dir):
            for f in files:
                if f.endswith(('.yml', '.yaml')):
                    p = os.path.join(root, f)
                    try:
                        with open(p, 'r', encoding='utf-8') as file:
                            d = yaml.safe_load(file)
                            self.all_rules.append({"path": p, "file": f, "status": 'OFF' if str(d.get('status')).lower() == 'deprecated' else 'ON', "title": d.get('title', 'N/A')})
                    except: pass

    def set_status(self, new_status):
        for item in self.tree.selection():
            path = self.tree.item(item, "tags")[0]
            if os.path.isdir(path): continue
            try:
                with open(path, 'r', encoding='utf-8') as f: data = yaml.safe_load(f)
                data['status'] = new_status
                with open(path, 'w', encoding='utf-8') as f: yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                self.log_func(f"DONE: {os.path.basename(path)} -> {new_status.upper()}")
                self.load_rules(); self._filter_logic()
            except: pass