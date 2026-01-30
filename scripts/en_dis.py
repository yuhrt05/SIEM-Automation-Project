import customtkinter as ctk
from tkinter import ttk, messagebox
import os
import yaml
class RuleManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, rules_dir, log_func):
        # Thiết kế Card theo phong cách Clean Tech
        super().__init__(parent, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB", corner_radius=20)
        self.rules_dir = rules_dir
        self.log_func = log_func
        self.all_rules = []

        self._init_manager_ui()
        self.load_rules()

    def _init_manager_ui(self):
        # Tiêu đề Card
        ctk.CTkLabel(self, text="❱❱ RULE STATUS MANAGER", font=("Segoe UI", 14, "bold"), text_color="#1C1E21").pack(anchor="w", padx=30, pady=(20, 10))

        # Thanh tìm kiếm (Search Bar)
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=30, pady=5)
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.update_list)
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search rule name or title...", height=35, textvariable=self.search_var)
        self.search_entry.pack(fill="x", expand=True)

        # Cấu hình Style cho Treeview (Tkinter chuẩn)
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=30)
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        
        self.tree = ttk.Treeview(self, columns=("File", "Status", "Title"), show="headings", height=8)
        self.tree.heading("File", text="FILE NAME")
        self.tree.heading("Status", text="STATUS")
        self.tree.heading("Title", text="TITLE")
        self.tree.column("File", width=150)
        self.tree.column("Status", width=100)
        self.tree.column("Title", width=350)
        self.tree.pack(fill="both", expand=True, padx=30, pady=10)

        # Các nút chức năng điều khiển Status
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))

        ctk.CTkButton(btn_frame, text="ACTIVATE (TEST)", fg_color="#28A745", text_color="white", width=150, height=35, font=("Segoe UI", 11, "bold"), 
                      command=lambda: self.set_status("test")).pack(side="left", padx=5)
        
        ctk.CTkButton(btn_frame, text="DEACTIVATE", fg_color="#FF3B30", text_color="white", width=150, height=35, font=("Segoe UI", 11, "bold"), 
                      command=lambda: self.set_status("disabled")).pack(side="left", padx=5)
        
        ctk.CTkButton(btn_frame, text="REFRESH", fg_color="#65676B", text_color="white", width=100, height=35, 
                      command=self.load_rules).pack(side="right", padx=5)

    def load_rules(self):
        """Quét đệ quy thư mục rules/ để tìm file Sigma"""
        self.all_rules = []
        if not os.path.exists(self.rules_dir): return
        
        for root, _, files in os.walk(self.rules_dir):
            for file in files:
                if file.endswith(('.yml', '.yaml')):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                            if data:
                                self.all_rules.append({
                                    "path": path, "file": file,
                                    "status": str(data.get('status', 'STABLE')).upper(),
                                    "title": data.get('title', 'No Title')
                                })
                    except: pass
        self.update_list()

    def update_list(self, *args):
        """Lọc danh sách theo từ khóa tìm kiếm"""
        term = self.search_var.get().lower()
        for item in self.tree.get_children(): self.tree.delete(item)
        for r in self.all_rules:
            if term in r['file'].lower() or term in r['title'].lower():
                self.tree.insert("", "end", values=(r['file'], r['status'], r['title']), tags=(r['path'],))

    def set_status(self, new_status):
        """Sửa trực tiếp vào file Sigma YAML"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("System", "Please select rules to modify!")
            return

        for item in selected:
            path = self.tree.item(item, "tags")[0]
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                # Cập nhật status để script deploy.py nhận diện
                data['status'] = new_status
                
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                
                self.log_func(f"RULE UPDATED: {os.path.basename(path)} -> {new_status.upper()}")
            except Exception as e:
                self.log_func(f"ERR UPDATING {path}: {e}")
        
        self.load_rules()