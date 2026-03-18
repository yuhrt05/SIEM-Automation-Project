import os, yaml, requests, shutil, subprocess, threading
from tkinter import messagebox, filedialog

class RuleManager:
    def __init__(self, rules_dir, log_func):
        self.rules_dir = rules_dir
        self.log_func = log_func
        self.trash_dir = "trash"
        os.makedirs(self.trash_dir, exist_ok=True)
        self.all_rules = []
        self.env_name, self.space_id = self._detect_environment()

    def _detect_environment(self):
        try:
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.STDOUT).decode().strip()
        except: branch = "dev"
        return (branch, "default") if branch == "main" else (branch, "detection-dev")

    def load_rules_data(self):
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
        
        if tree.get_children(): 
            drop_frame.pack(fill="x", padx=20, pady=(5, 15))

    def set_status(self, status, tree, refresh_callback):
        sel = tree.selection()
        if not sel: return
        for item in sel:
            path = tree.item(item, "tags")[0]
            if os.path.isdir(path): continue
            try:
                with open(path, encoding='utf-8') as f: data = yaml.safe_load(f)
                data['status'] = status
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                self.log_func(f"Updated: {os.path.basename(path)} -> {status.upper()}")
            except: pass
        refresh_callback()

    def delete(self, tree, mode, refresh_callback):
        sel = tree.selection()
        if not sel: return
        path = tree.item(sel[0], "tags")[0]
        name = os.path.basename(path)
        if not messagebox.askyesno("Confirm", f"Delete {mode}: {name}?"): return
        
        def _task():
            # ... (Giữ nguyên logic API Delete và Git Push của ông) ...
            self.log_func(f"[+] Deleted & Synced: {name}")
            refresh_callback()
        
        threading.Thread(target=_task, daemon=True).start()

    def sync_audit(self):
        # ... (Giữ nguyên logic đối soát API của ông) ...
        self.log_func("[*] Audit task started...")

    def restore(self, mode, refresh_callback):
        p = filedialog.askdirectory(initialdir=self.trash_dir) if mode == "Folder Mode" else \
            filedialog.askopenfilename(initialdir=self.trash_dir)
        if p:
            shutil.move(p, os.path.join(self.rules_dir, os.path.basename(p).replace("_dir", "")))
            refresh_callback()

    def on_mode_change(self, search_var, drop_frame):
        search_var.set("")
        drop_frame.pack_forget()