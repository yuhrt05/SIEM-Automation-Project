import customtkinter as ctk
from tkinter import ttk, messagebox
import os, yaml, requests

class RuleManagerFrame(ctk.CTkFrame):
    def __init__(self, parent, rules_dir, log_func):
        super().__init__(parent, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB", corner_radius=12)
        self.rules_dir = rules_dir
        self.log_func = log_func
        self.all_rules = []
        
        self._init_ui()
        self.load_rules()

    def _init_ui(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=10, pady=10)

        # --- DÒNG ĐIỀU KHIỂN ---
        self.ctrl_row = ctk.CTkFrame(self.container, fg_color="transparent")
        self.ctrl_row.pack(fill="x")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_logic)
        
        self.entry = ctk.CTkEntry(self.ctrl_row, placeholder_text="🔍 Type to search rule...", 
                                  width=350, height=35, textvariable=self.search_var, border_width=1)
        self.entry.pack(side="left", padx=(0, 10))

        # Nút Bật/Tắt trạng thái
        ctk.CTkButton(self.ctrl_row, text="ON", width=50, height=35, fg_color="#28A745", 
                      font=("Segoe UI", 11, "bold"), command=lambda: self.set_status("test")).pack(side="left", padx=2)
        
        ctk.CTkButton(self.ctrl_row, text="OFF", width=50, height=35, fg_color="#FF3B30", 
                      font=("Segoe UI", 11, "bold"), command=lambda: self.set_status("disabled")).pack(side="left", padx=2)

        # NÚT DELETE TRIỆT ĐỂ (Xoá SIEM + Local)
        self.btn_delete = ctk.CTkButton(self.ctrl_row, text="DELETE", width=70, height=35, 
                                        fg_color="#6C757D", hover_color="#5A6268",
                                        font=("Segoe UI", 11, "bold"), command=self.delete_rule_fully)
        self.btn_delete.pack(side="left", padx=(10, 0))

        # --- DANH SÁCH RULE (TREEVIEW) ---
        self.drop_frame = ctk.CTkFrame(self.container, fg_color="#FFFFFF", border_width=1, border_color="#E4E6EB")
        
        style = ttk.Style()
        style.configure("Small.Treeview", font=("Segoe UI", 10), rowheight=28)
        self.tree = ttk.Treeview(self.drop_frame, columns=("Status", "Title"), show="headings", height=5, style="Small.Treeview")
        self.tree.heading("Status", text="STATUS")
        self.tree.heading("Title", text="RULE TITLE")
        self.tree.column("Status", width=70, anchor="center")
        self.tree.column("Title", width=430)
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def delete_rule_fully(self):
        """Xoá sạch dấu vết trên SIEM và Local Repo"""
        selected = self.tree.selection()
        if not selected: return

        if not messagebox.askyesno("Xác nhận", "Xóa vĩnh viễn Rule này trên cả SIEM và Repo?"):
            return

        # Lấy cấu hình từ file .env
        host = os.getenv('ELASTIC_HOST') # Đã khớp với biến trong hình của bạn
        user = os.getenv('ELASTIC_USER')
        password = os.getenv('ELASTIC_PASS')

        for item in selected:
            path = self.tree.item(item, "tags")[0]
            try:
                # 1. Lấy ID Rule để gọi API
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    rule_id = data.get('id')

                # 2. Xóa trên SIEM qua API Kibana
                if rule_id and host:
                    url = f"{host}/api/detection_engine/rules?rule_id={rule_id}"
                    headers = {"kbn-xsrf": "true"}
                    
                    # Gọi lệnh xóa (Verify=False nếu dùng SSL tự ký)
                    res = requests.delete(url, auth=(user, password), headers=headers, verify=False)
                    
                    if res.status_code == 200:
                        self.log_func(f"[+] SIEM: Đã gỡ bỏ Rule ID {rule_id}")
                    else:
                        self.log_func(f"[-] SIEM: Lỗi {res.status_code} (Rule có thể không tồn tại)")

                # 3. Xóa file vật lý ở máy Local
                if os.path.exists(path):
                    os.remove(path)
                    self.log_func(f"[+] REPO: Đã xóa file {os.path.basename(path)}")
                
                # 4. Xóa khỏi giao diện GUI
                self.tree.delete(item)

            except Exception as e:
                self.log_func(f"[-] Lỗi hệ thống khi xóa: {e}")
        
        self.load_rules()
        self.log_func("[!] ĐỒNG BỘ HOÀN TẤT: Nhấn Git Push để cập nhật lên GitHub.")

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
        else: self.drop_frame.pack_forget()

    def set_status(self, new_status):
        selected = self.tree.selection()
        if not selected: return
        for item in selected:
            path = self.tree.item(item, "tags")[0]
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                target = 'deprecated' if new_status == 'disabled' else new_status
                data['status'] = target
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                new_disp = 'OFF' if target in ['disabled', 'deprecated'] else 'ON'
                self.tree.set(item, column="Status", value=new_disp)
                for r in self.all_rules:
                    if r['path'] == path: r['status'] = new_disp
                self.log_func(f"DONE: {os.path.basename(path)} -> {new_disp}")
            except Exception as e: self.log_func(f"ERR: {e}")