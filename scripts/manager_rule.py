import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import os
import yaml
import requests
import shutil
import subprocess
import threading

class RuleManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, rules_dir, log_func):
        super().__init__(parent, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB", corner_radius=12)
        self.rules_dir = rules_dir
        self.log_func = log_func
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
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=w, anchor="center" if col == "Status" else "w")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def _on_mode_change(self, mode):
        self.search_entry.configure(placeholder_text=f"Search by {mode.split()[0]} name...")
        self.search_var.set("")
        self.drop_frame.pack_forget()

    def _filter_logic(self, *args):
        term = self.search_var.get().lower().strip()
        if not term:
            self.drop_frame.pack_forget()
            return

        self.tree.delete(*self.tree.get_children())
        
        mode = self.delete_mode.get()
        results = []

        if mode == "Folder Mode":
            seen = set()
            for r in self.all_rules:
                f_path = os.path.dirname(r['path'])
                f_name = os.path.basename(f_path)
                if term in f_name.lower() and f_path not in seen:
                    self.tree.insert("", "end", values=("DIR", f"Folder: {f_name}"), tags=(f_path,))
                    seen.add(f_path)
                    results.append(f_path)
        else:
            res = [r for r in self.all_rules if term in r['file'].lower() or term in r['title'].lower()]
            for r in res:
                self.tree.insert("", "end", values=(r['status'], r['title']), tags=(r['path'],))
                results.append(r)

        if results:
            self.drop_frame.pack(fill="x", pady=(5, 0))
        else:
            self.drop_frame.pack_forget()

    def delete_rule_fully(self):
        selected = self.tree.selection()
        if not selected:
            return
        
        mode = self.delete_mode.get()
        path = self.tree.item(selected[0], "tags")[0]
        name = os.path.basename(path)

        if not messagebox.askyesno("Confirm Delete", f"Delete {mode}: {name}?\nThis action cannot be undone."):
            return

        self.log_func(f"[*] Starting delete for {mode}: {name} (background thread)...")

        def _delete_thread():
            try:
                # Thu thập tất cả file .yml/.yaml cần xử lý
                targets = []
                if mode == "Folder Mode":
                    for root, _, files in os.walk(path):
                        for f in files:
                            if f.endswith(('.yml', '.yaml')):
                                targets.append(os.path.join(root, f))
                else:
                    targets = [path]

                host = os.getenv('ELASTIC_HOST2')
                user = os.getenv('ELASTIC_USER')
                pwd = os.getenv('ELASTIC_PASS')
                changed = False

                for p in targets:
                    try:
                        with open(p, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                            rid = data.get('id')
                        if rid:
                            res = requests.delete(
                                f"{host}/api/detection_engine/rules?rule_id={rid}",
                                auth=(user, pwd),
                                headers={"kbn-xsrf": "true"},
                                verify=False,
                                timeout=10
                            )
                            if res.status_code in (200, 404):
                                self.log_func(f"[+] SIEM: Cleaned rule from {os.path.basename(p)}")
                                changed = True
                            else:
                                self.log_func(f"[-] SIEM delete failed ({res.status_code}): {os.path.basename(p)}")
                    except Exception as e:
                        self.log_func(f"[-] Error processing {os.path.basename(p)}: {e}")

                if changed:
                    try:
                        dest_name = f"{name}_dir" if mode == "Folder Mode" else name
                        shutil.move(path, os.path.join(self.trash_dir, dest_name))
                        self.log_func(f"[+] Moved to trash: {dest_name}")

                        # Git sync
                        for cmd in [
                            ["git", "add", "."],
                            ["git", "commit", "-m", f"SOC-GUI: Deleted {mode} - {name}"],
                            ["git", "push"]
                        ]:
                            subprocess.run(cmd, capture_output=True, check=True)
                            self.log_func(f"GIT: {' '.join(cmd)} - SUCCESS")
                        self.log_func(f"SUCCESS: {mode} fully deleted and synced.")
                    except subprocess.CalledProcessError as e:
                        self.log_func(f"[!] Git sync failed: {e}")
                    except Exception as e:
                        self.log_func(f"[!] Move to trash / Git error: {e}")

                # Cập nhật GUI trên main thread
                self.after(0, self.load_rules)
                self.after(0, lambda: self.log_func("DELETE operation completed."))

            except Exception as e:
                self.after(0, lambda: self.log_func(f"[-] DELETE THREAD CRITICAL ERROR: {e}"))
            finally:
                pass  # Không cần thêm logic ở đây, nhưng phải có block để tránh IndentationError

        threading.Thread(target=_delete_thread, daemon=True).start()

    def restore_logic(self):
        mode = self.delete_mode.get()
        if mode == "Folder Mode":
            p = filedialog.askdirectory(title="Select folder to restore", initialdir=self.trash_dir)
        else:
            p = filedialog.askopenfilename(title="Select file to restore", 
                                           initialdir=self.trash_dir,
                                           filetypes=[("Sigma Rules", "*.yml *.yaml")])
        
        if not p:
            return

        self.log_func(f"[*] Starting restore: {os.path.basename(p)} (background thread)...")

        def _restore_thread():
            try:
                base_name = os.path.basename(p)
                dest_name = base_name.replace("_dir", "")  # Xóa hậu tố _dir nếu có
                dest = os.path.join(self.rules_dir, dest_name)

                # Nếu đích đã tồn tại → cảnh báo hoặc overwrite (tùy bạn muốn)
                if os.path.exists(dest):
                    self.after(0, lambda: messagebox.showwarning("Warning", f"Destination {dest_name} already exists. Overwriting."))
                
                shutil.move(p, dest)
                self.after(0, lambda: self.log_func(f"[+] RESTORED: {dest_name}"))
                self.after(0, self.load_rules)
                self.after(0, lambda: self.log_func("RESTORE operation completed."))

            except Exception as e:
                self.after(0, lambda: self.log_func(f"[-] RESTORE ERROR: {e}"))
            finally:
                pass  # Giữ block trống hợp lệ

        threading.Thread(target=_restore_thread, daemon=True).start()

    def load_rules(self):
        self.all_rules = []
        for root, _, files in os.walk(self.rules_dir):
            for f in files:
                if f.lower().endswith(('.yml', '.yaml')):
                    p = os.path.join(root, f)
                    try:
                        with open(p, 'r', encoding='utf-8') as file:
                            d = yaml.safe_load(file)
                            if d:
                                status = 'OFF' if str(d.get('status', '')).lower() == 'deprecated' else 'ON'
                                title = d.get('title', 'N/A')
                                self.all_rules.append({
                                    "path": p,
                                    "file": f,
                                    "status": status,
                                    "title": title
                                })
                    except Exception as e:
                        self.log_func(f"[-] Load error {f}: {e}")
        # Refresh filter nếu đang search
        self._filter_logic()

    def set_status(self, new_status):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        updated = 0
        for item in selected_items:
            path = self.tree.item(item, "tags")[0]
            if os.path.isdir(path):
                continue  # Bỏ qua folder
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if data:
                    data['status'] = new_status
                    with open(path, 'w', encoding='utf-8') as f:
                        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                    self.log_func(f"DONE: {os.path.basename(path)} → {new_status.upper()}")
                    updated += 1
            except Exception as e:
                self.log_func(f"[-] Set status error {os.path.basename(path)}: {e}")

        if updated > 0:
            self.load_rules()
            self._filter_logic()