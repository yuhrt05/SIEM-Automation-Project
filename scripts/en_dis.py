import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
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

        # --- Dòng 1: Tìm kiếm & Chế độ ---
        ctrl_top = ctk.CTkFrame(container, fg_color="transparent")
        ctrl_top.pack(fill="x", pady=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_logic)
        
        self.search_entry = ctk.CTkEntry(ctrl_top, placeholder_text="🔍 Search rules...", width=320, height=35, 
                                         textvariable=self.search_var)
        self.search_entry.pack(side="left", padx=(0, 10))

        # Dropdown chọn chế độ (Thay đổi Mode sẽ Reset Search)
        self.delete_mode = ctk.StringVar(value="File Mode")
        self.mode_menu = ctk.CTkOptionMenu(ctrl_top, values=["File Mode", "Folder Mode"], 
                                           variable=self.delete_mode, width=120, height=35,
                                           command=self._on_mode_change) # Gọi hàm khi đổi Mode
        self.mode_menu.pack(side="left", padx=5)

        # --- Dòng 2: Thao tác ---
        ctrl_bot = ctk.CTkFrame(container, fg_color="transparent")
        ctrl_bot.pack(fill="x", pady=5)

        for txt, color, stat in [("ENABLE", "#28A745", "test"), ("DISABLE", "#FF3B30", "deprecated")]:
            ctk.CTkButton(ctrl_bot, text=txt, width=80, height=35, fg_color=color, font=("Segoe UI", 11, "bold"),
                          command=lambda s=stat: self.set_status(s)).pack(side="left", padx=2)

        ctk.CTkButton(ctrl_bot, text="DELETE", width=80, height=35, fg_color="#6C757D", 
                      font=("Segoe UI", 11, "bold"), command=self.delete_rule_fully).pack(side="left", padx=(10, 5))
        
        ctk.CTkButton(ctrl_bot, text="RESTORE", width=80, height=35, fg_color="transparent", border_width=1, 
                      text_color="#65676B", font=("Segoe UI", 11, "bold"), command=self.restore_logic).pack(side="left")

        # --- Treeview Area ---
        self.drop_frame = ctk.CTkFrame(container, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB")
        self.tree = ttk.Treeview(self.drop_frame, columns=("Status", "Title"), show="headings", height=8)
        for col, w in [("Status", 80), ("Title", 420)]:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=w, anchor="center" if col=="Status" else "w")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def _on_mode_change(self, mode):
        """Thay đổi placeholder và reset tìm kiếm khi đổi Mode"""
        if mode == "Folder Mode":
            self.search_entry.configure(placeholder_text="📁 Search by Folder name...")
        else:
            self.search_entry.configure(placeholder_text="🔍 Search by Rule title/file...")
        self.search_var.set("") # Clear tìm kiếm cũ
        self.drop_frame.pack_forget()

    def _filter_logic(self, *args):
        term = self.search_var.get().lower().strip()
        if not term: return self.drop_frame.pack_forget()
        
        self.tree.delete(*self.tree.get_children())
        mode = self.delete_mode.get()
        
        results = []
        if mode == "Folder Mode":
            # Logic: Tìm các Folder chứa Rule có tên khớp với từ khóa
            # Chúng ta chỉ hiển thị 1 đại diện cho mỗi Folder để tránh lặp
            seen_folders = set()
            for r in self.all_rules:
                folder_path = os.path.dirname(r['path'])
                folder_name = os.path.basename(folder_path)
                if term in folder_name.lower() and folder_path not in seen_folders:
                    # Hiển thị Folder dưới dạng một dòng đặc biệt
                    self.tree.insert("", "end", values=("DIR", f"📂 Folder: {folder_name}"), tags=(folder_path,))
                    seen_folders.add(folder_path)
                    results.append(folder_path)
        else:
            # Logic cũ: Tìm theo File hoặc Title
            res = [r for r in self.all_rules if term in r['file'].lower() or term in r['title'].lower()]
            for r in res:
                self.tree.insert("", "end", values=(r['status'], r['title']), tags=(r['path'],))
                results.append(r)

        if results: self.drop_frame.pack(fill="x", pady=(5, 0))
        else: self.drop_frame.pack_forget()

    def delete_rule_fully(self):
        selected = self.tree.selection()
        if not selected: return

        mode = self.delete_mode.get()
        target_path = self.tree.item(selected[0], "tags")[0] # Có thể là file path hoặc folder path
        
        targets = []
        if mode == "Folder Mode":
            folder_name = os.path.basename(target_path)
            if not messagebox.askyesno("Confirm", f"Xác nhận xóa TOÀN BỘ rule trong folder '{folder_name}'?"): return
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.endswith(('.yml', '.yaml')): targets.append(os.path.join(root, f))
            parent_dir = target_path
        else:
            filename = os.path.basename(target_path)
            if not messagebox.askyesno("Confirm", f"Xác nhận xóa rule: {filename}?"): return
            targets = [target_path]
            parent_dir = os.path.dirname(target_path)

        # --- Đoạn gọi API & Sync GitHub giữ nguyên như bản trước ---
        host, user, pwd = os.getenv('ELASTIC_HOST'), os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASS')
        changed, deleted_list = False, []

        for p in targets:
            try:
                with open(p, 'r', encoding='utf-8') as f: rule_id = yaml.safe_load(f).get('id')
                res = requests.delete(f"{host}/api/detection_engine/rules?rule_id={rule_id}", 
                                      auth=(user, pwd), headers={"kbn-xsrf": "true"}, verify=False, timeout=10)
                if res.status_code in [200, 404]:
                    deleted_list.append(os.path.basename(p))
                    changed = True
                    self.log_func(f"[+] SIEM: Cleaned {os.path.basename(p)}")
            except Exception as e: self.log_func(f"[-] Error {p}: {e}")

        if changed:
            try:
                if mode == "Folder Mode":
                    shutil.move(parent_dir, os.path.join(self.trash_dir, f"{os.path.basename(parent_dir)}_dir"))
                else:
                    shutil.move(target_path, os.path.join(self.trash_dir, os.path.basename(target_path)))
                
                # Git Push
                subprocess.run(["git", "add", "."], capture_output=True)
                subprocess.run(["git", "commit", "-m", f"SOC-GUI: Deleted {mode}"], capture_output=True)
                subprocess.run(["git", "push"], capture_output=True)
                self.log_func(f"[⭐] SUCCESS: {mode} Sync complete.")
            except Exception as e: self.log_func(f"[!] Disk/Git Error: {e}")

        self.load_rules()

    # --- load_rules, set_status, restore_logic giữ nguyên ---
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
                            st = 'OFF' if str(data.get('status')).lower() == 'deprecated' else 'ON'
                            self.all_rules.append({"path": p, "file": f, "status": st, "title": data.get('title', 'N/A')})
                    except: pass

    def restore_logic(self):
        file_p = filedialog.askopenfilename(initialdir=self.trash_dir, title="Restore", filetypes=[("Sigma Rules", "*.yml *.yaml")])
        if file_p:
            shutil.move(file_p, os.path.join(self.rules_dir, os.path.basename(file_p)))
            self.log_func(f"[+] RESTORED: {os.path.basename(file_p)}")
            self.load_rules()

    def set_status(self, new_status):
        for item in self.tree.selection():
            path = self.tree.item(item, "tags")[0]
            if os.path.isdir(path): continue # Không cho Enable/Disable folder trực tiếp ở đây
            try:
                with open(path, 'r', encoding='utf-8') as f: data = yaml.safe_load(f)
                data['status'] = new_status
                with open(path, 'w', encoding='utf-8') as f: yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                self.tree.set(item, column="Status", value='OFF' if new_status == 'deprecated' else 'ON')
                self.load_rules() # Refresh list
            except: pass