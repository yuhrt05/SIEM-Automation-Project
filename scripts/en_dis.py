import customtkinter as ctk
from tkinter import ttk, messagebox
import os, yaml

class RuleManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, rules_dir, log_func):
        # Thiết kế siêu mỏng (Single Row)
        super().__init__(parent, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB", corner_radius=12)
        self.rules_dir = rules_dir
        self.log_func = log_func
        self.all_rules = []
        
        # UI Components
        self._init_ui()
        self.load_rules()

    def _init_ui(self):
        # Container chính bọc toàn bộ
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=10, pady=10)

        # --- DÒNG TÌM KIẾM & NÚT ---
        self.ctrl_row = ctk.CTkFrame(self.container, fg_color="transparent")
        self.ctrl_row.pack(fill="x")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_logic)
        
        self.entry = ctk.CTkEntry(self.ctrl_row, placeholder_text="🔍 Type to search rule...", 
                                  width=350, height=35, textvariable=self.search_var, border_width=1)
        self.entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(self.ctrl_row, text="ON", width=50, height=35, fg_color="#28A745", 
                      font=("Segoe UI", 11, "bold"), command=lambda: self.set_status("test")).pack(side="left", padx=2)
        
        ctk.CTkButton(self.ctrl_row, text="OFF", width=50, height=35, fg_color="#FF3B30", 
                      font=("Segoe UI", 11, "bold"), command=lambda: self.set_status("disabled")).pack(side="left", padx=2)

        # --- MENU TRỔ XUỐNG (Mặc định ẩn) ---
        self.drop_frame = ctk.CTkFrame(self.container, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB")
        
        style = ttk.Style()
        style.configure("Small.Treeview", font=("Segoe UI", 10), rowheight=28)
        self.tree = ttk.Treeview(self.drop_frame, columns=("Status", "Title"), show="headings", height=5, style="Small.Treeview")
        self.tree.heading("Status", text="STATUS")
        self.tree.heading("Title", text="RULE TITLE")
        self.tree.column("Status", width=70, anchor="center")
        self.tree.column("Title", width=430)
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def _filter_logic(self, *args):
        term = self.search_var.get().lower().strip()
        if not term:
            self.drop_frame.pack_forget()
            return

        results = [r for r in self.all_rules if term in r['file'].lower() or term in r['title'].lower()]
        
        if results:
            for item in self.tree.get_children(): self.tree.delete(item)
            for r in results:
                self.tree.insert("", "end", values=(r['status'], r['title']), tags=(r['path'],))
            self.drop_frame.pack(fill="x", pady=(5, 0))
        else:
            self.drop_frame.pack_forget()

    def load_rules(self):
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
                            status = str(data.get('status', 'test')).lower()
                            disp = 'OFF' if status in ['disabled', 'deprecated'] else 'ON'
                            self.all_rules.append({"path": path, "file": file, "status": disp, "title": data.get('title', 'N/A')})
                    except: pass

    def set_status(self, new_status):
        selected = self.tree.selection()
        if not selected: return

        for item in selected:
            path = self.tree.item(item, "tags")[0]
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                # Ánh xạ status cho Sigma CLI
                target = 'deprecated' if new_status == 'disabled' else new_status
                data['status'] = target
                
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                
                # CẬP NHẬT TRẠNG THÁI TẠI CHỖ (Không làm mất dòng)
                new_disp = 'OFF' if target in ['disabled', 'deprecated'] else 'ON'
                self.tree.set(item, column="Status", value=new_disp)
                
                # Cập nhật lại trong bộ nhớ all_rules
                for r in self.all_rules:
                    if r['path'] == path: r['status'] = new_disp

                self.log_func(f"DONE: {os.path.basename(path)} -> {new_disp}")
            except Exception as e: self.log_func(f"ERR: {e}")