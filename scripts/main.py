import subprocess
import requests
import sys
import io
import os
import shutil
import yaml
import json
import threading
import winsound
import psutil
import time
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from alert import AlertMonitor
from manager import RuleManager 

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH MÀU SẮC CLEAN TECH ---
COLOR_BG_LIGHT = "#F0F2F5"     
COLOR_SIDEBAR = "#FFFFFF"      
COLOR_FRAME = "#FFFFFF"        
COLOR_ACCENT = "#0062FF"       
COLOR_TEXT_DARK = "#1C1E21"    
COLOR_TEXT_MUTED = "#65676B"   
COLOR_BORDER = "#E4E6EB"       
COLOR_STATUS_GREEN = "#28A745" 
COLOR_NEON_RED = "#FF3B30"     
COLOR_DARK_RED = "#660000"     

ctk.set_appearance_mode("light") 

class SOCXCommand(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SOC GUI")
        self.geometry("1100x900") 

        # Khai báo các biến cấu hình trước khi nạp Logic
        self.RULES_DIR = "rules/"
        self.monitor_system = AlertMonitor()
        self.logic = RuleManager(self.RULES_DIR, self.write_log)

        self.selected_path = None
        self.is_folder = False
        self.blink_state = False
        
        # Biến quản lý Placeholder
        self.placeholder_msg = "ENTER COMMIT MSG HERE..."

        # Biến cho Progress Bar
        self.progress = None

        self._init_ui()
        
        # Load dữ liệu ban đầu cho bảng
        self.update_ui_list()
        
        # Khởi chạy luồng cập nhật CPU/RAM
        threading.Thread(target=self._update_system_stats, daemon=True).start()

    def _init_ui(self):
        self.configure(fg_color=COLOR_BG_LIGHT)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color=COLOR_SIDEBAR, border_width=1, border_color=COLOR_BORDER)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(self.sidebar, text="SIEM", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_ACCENT).pack(pady=(50, 5))
        ctk.CTkLabel(self.sidebar, text="AUTOMATION CENTER", font=("Segoe UI", 10), text_color=COLOR_TEXT_MUTED).pack(pady=(0, 40))

        self.btn_deploy = self._side_btn("LOAD RULE", COLOR_ACCENT, self.start_deploy_thread)
        self.btn_push = self._side_btn("GIT PUSH", COLOR_STATUS_GREEN, self.run_git_push)

        self.mon_frame = ctk.CTkFrame(self.sidebar, fg_color="#F8F9FA", corner_radius=15, border_width=1, border_color=COLOR_BORDER)
        self.mon_frame.pack(side="bottom", fill="x", padx=20, pady=30)
        
        self.status_indicator = ctk.CTkLabel(self.mon_frame, text="● SYSTEM READY", text_color=COLOR_STATUS_GREEN, font=("Segoe UI", 12, "bold"))
        self.status_indicator.pack(pady=(15, 5))

        self.mon_sw = ctk.CTkSwitch(self.mon_frame, text="THREAT SCAN", progress_color=COLOR_NEON_RED, command=self.toggle_monitor)
        self.mon_sw.pack(pady=(5, 15), padx=20)

        # --- MAIN WORKSPACE ---
        self.workspace = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.workspace.grid(row=0, column=1, sticky="nsew")

        # Header Stats
        self.header = ctk.CTkFrame(self.workspace, height=100, fg_color="transparent")
        self.header.pack(fill="x", padx=40, pady=(40, 20))
        self._add_stat("SOC OPERATOR", "ELK", COLOR_TEXT_DARK)
        self.cpu_val = self._add_stat("CPU LOAD", "0%", COLOR_ACCENT)
        self.ram_val = self._add_stat("RAM USAGE", "0%", COLOR_ACCENT)

        # --- INGESTION CONSOLE ---
        self.console_card = ctk.CTkFrame(self.workspace, fg_color=COLOR_FRAME, border_width=1, border_color=COLOR_BORDER, corner_radius=20)
        self.console_card.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(self.console_card, text="❱❱ SIGMA DATA INGESTION", font=("Segoe UI", 14, "bold"), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=30, pady=(20, 10))
        
        row1 = ctk.CTkFrame(self.console_card, fg_color="transparent")
        row1.pack(fill="x", padx=30, pady=(0, 10))
        self.btn_browse = ctk.CTkButton(row1, text="BROWSE DATA", width=160, height=40, fg_color=COLOR_ACCENT, text_color="white", font=("Segoe UI", 12, "bold"), command=self.browse_data)
        self.btn_browse.pack(side="left")
        self.lbl_path = ctk.CTkLabel(row1, text="WAITING FOR DATA INPUT...", text_color=COLOR_TEXT_MUTED, font=("Segoe UI", 12))
        self.lbl_path.pack(side="left", padx=20)

        row2 = ctk.CTkFrame(self.console_card, fg_color="transparent")
        row2.pack(fill="x", padx=30, pady=(0, 20))
        
        self.commit_input = ctk.CTkEntry(row2, height=40, fg_color="#F0F2F5", border_color=COLOR_BORDER, text_color=COLOR_TEXT_MUTED)
        self.commit_input.insert(0, self.placeholder_msg)
        self.commit_input.pack(fill="x")
        
        self.commit_input.bind("<FocusIn>", self._on_focus_in)
        self.commit_input.bind("<FocusOut>", self._on_focus_out)

        # --- TERMINAL ---
        self.term_frame = ctk.CTkFrame(self.workspace, fg_color="#FFFFFF", border_width=1, border_color=COLOR_BORDER, corner_radius=10)
        self.term_frame.pack(fill="x", padx=40, pady=(10, 10))
        
        self.term_header = ctk.CTkFrame(self.term_frame, fg_color="transparent", height=35)
        self.term_header.pack(fill="x", padx=10, pady=(5, 0))
        
        ctk.CTkLabel(self.term_header, text="SYSTEM MONITOR OUTPUT", font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT_MUTED).pack(side="left", padx=5)
        
        self.btn_clear = ctk.CTkButton(self.term_header, text="CLEAR LOG", width=90, height=25, fg_color="transparent", border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT_MUTED, command=self.clear_log)
        self.btn_clear.pack(side="right", padx=5)
        
        self.log_box = ctk.CTkTextbox(self.term_frame, height=200, fg_color="transparent", text_color=COLOR_TEXT_DARK, font=("Consolas", 14))
        self.log_box.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.write_log("SOC Manager System: Ready.")

        # --- BẮT ĐẦU PHẦN UI CỦA RULE MANAGER (DI CHUYỂN TỪ MANAGER.PY) ---
        self.manager_card = ctk.CTkFrame(self.workspace, fg_color=COLOR_FRAME, border_width=1, border_color=COLOR_BORDER, corner_radius=20)
        self.manager_card.pack(fill="x", padx=40, pady=10)

        # Thanh Search và Mode
        search_row = ctk.CTkFrame(self.manager_card, fg_color="transparent")
        search_row.pack(fill="x", padx=20, pady=(15, 5))
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.logic.filter_logic(self.search_var.get(), self.mode_var.get(), self.tree, self.drop))
        
        ctk.CTkEntry(search_row, placeholder_text="Search rules...", textvariable=self.search_var, width=350, height=35).pack(side="left", padx=(0, 10))
        
        self.mode_var = ctk.StringVar(value="File Mode")
        ctk.CTkOptionMenu(search_row, values=["File Mode", "Folder Mode"], variable=self.mode_var, width=130, command=lambda _: self.logic.on_mode_change(self.search_var, self.drop)).pack(side="left")

        # Hàng nút điều khiển
        btn_row = ctk.CTkFrame(self.manager_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(btn_row, text="ENABLE", width=80, height=35, fg_color=COLOR_STATUS_GREEN, font=("Segoe UI", 11, "bold"), 
                      command=lambda: self.logic.set_status("test", self.tree, self.update_ui_list)).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="DISABLE", width=80, height=35, fg_color=COLOR_NEON_RED, font=("Segoe UI", 11, "bold"), 
                      command=lambda: self.logic.set_status("deprecated", self.tree, self.update_ui_list)).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="DELETE", width=80, height=35, fg_color="#6C757D", font=("Segoe UI", 11, "bold"), 
                      command=lambda: self.logic.delete(self.tree, self.mode_var.get(), self.update_ui_list)).pack(side="left", padx=(10, 5))
        ctk.CTkButton(btn_row, text="RESTORE", width=80, height=35, fg_color="transparent", border_width=1, text_color=COLOR_TEXT_MUTED, 
                      command=lambda: self.logic.restore(self.mode_var.get(), self.update_ui_list)).pack(side="left")
        ctk.CTkButton(btn_row, text="SYNC AUDIT", width=100, height=35, fg_color="#007AFF", command=self.logic.sync_audit).pack(side="left", padx=10)

        # Bảng hiển thị (Treeview)
        self.drop = ctk.CTkFrame(self.manager_card, fg_color="#FFFFFF", border_width=1, border_color=COLOR_BORDER)
        self.tree = ttk.Treeview(self.drop, columns=("Status", "Title"), show="headings", height=8)
        self.tree.heading("Status", text="STATUS"); self.tree.column("Status", width=80, anchor="center")
        self.tree.heading("Title", text="TITLE"); self.tree.column("Title", width=450, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)
        # --- KẾT THÚC PHẦN UI RULE MANAGER ---

    def update_ui_list(self):
        """Cập nhật dữ liệu từ disk và render lại Treeview"""
        self.logic.load_rules_data()
        self.logic.filter_logic(self.search_var.get(), self.mode_var.get(), self.tree, self.drop)

    # --- PROGRESS BAR HELPERS ---
    def _show_progress(self):
        if self.progress is None:
            self.progress = ctk.CTkProgressBar(self.sidebar, 
                                               width=200, height=12,
                                               progress_color=COLOR_ACCENT,
                                               fg_color=COLOR_BORDER)
            self.progress.pack(pady=10, padx=25, fill="x")
        self.progress.start() 
        self.progress.pack()

    def _hide_progress(self):
        if self.progress:
            self.progress.stop()
            self.progress.pack_forget()

    # --- PLACEHOLDER LOGIC ---
    def _on_focus_in(self, event):
        if self.commit_input.get() == self.placeholder_msg:
            self.commit_input.delete(0, 'end')
            self.commit_input.configure(text_color=COLOR_TEXT_DARK)

    def _on_focus_out(self, event):
        if not self.commit_input.get():
            self.commit_input.insert(0, self.placeholder_msg)
            self.commit_input.configure(text_color=COLOR_TEXT_MUTED)

    # --- LOGIC HANDLING ---
    def browse_data(self):
        choice = messagebox.askyesnocancel("Data Type", "FOLDER (Yes) / FILE (No)?")
        if choice is None: return
        path = filedialog.askdirectory() if choice else filedialog.askopenfilename(filetypes=[("Sigma Rules", "*.yml *.yaml")])
        if path:
            self.selected_path, self.is_folder = path, choice
            self.lbl_path.configure(text=f"{'DIR' if choice else 'FILE'}: {os.path.basename(path).upper()}", text_color=COLOR_ACCENT)
            self.write_log(f"PATH STAGED: {path}")

    def toggle_monitor(self):
        if self.mon_sw.get():
            if not self.monitor_system.running:
                self.monitor_system.running = True
                self.write_log("📡 SYSTEM: STARTING LIVE THREAT SCANNER...")
                self.status_indicator.configure(text="● MONITORING")
                self._blink_indicator()
                winsound.Beep(1200, 150)
                threading.Thread(target=self.monitor_system.run_logic, args=(self.write_log,), daemon=True).start()
        else:
            self.monitor_system.running = False
            self.write_log("SYSTEM: MONITORING STANDBY. SECURITY STABLE.")
            winsound.Beep(400, 150)

    def _blink_indicator(self):
        if self.mon_sw.get():
            current_color = COLOR_NEON_RED if self.blink_state else COLOR_DARK_RED
            self.status_indicator.configure(text_color=current_color)
            self.blink_state = not self.blink_state
            self.after(500, self._blink_indicator)
        else:
            self.status_indicator.configure(text="● SYSTEM READY", text_color=COLOR_STATUS_GREEN)

    def write_log(self, msg):
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] > {msg}\n")
        self.log_box.see("end")

    def clear_log(self):
        self.log_box.delete("1.0", "end")
        self.write_log("LOG SYSTEM RESET.")

    def _update_system_stats(self):
        while True:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            self.cpu_val.configure(text=f"{cpu}%", text_color=COLOR_NEON_RED if cpu > 80 else COLOR_ACCENT)
            self.ram_val.configure(text=f"{ram}%", text_color=COLOR_NEON_RED if ram > 85 else COLOR_ACCENT)
            time.sleep(1)

    def start_deploy_thread(self):
        if self.selected_path:
            self._show_progress()
            self.btn_deploy.configure(state="disabled", text="LOADING...")
            threading.Thread(target=self.run_deploy, daemon=True).start()

    def run_deploy(self):
        try: 
            target = os.path.join(self.RULES_DIR, os.path.basename(self.selected_path))
            count = 0
            if self.is_folder:
                for root, _, files in os.walk(self.selected_path):
                    for file in files:
                        if file.endswith(('.yml', '.yaml')):
                            rel = os.path.relpath(root, self.selected_path)
                            dest = os.path.join(target, rel)
                            if not os.path.exists(dest): os.makedirs(dest)
                            shutil.copy(os.path.join(root, file), dest)
                            count += 1
                self.write_log(f"SUCCESS: {count} rules ingested.")
                self.update_ui_list()
            else:
                if not os.path.exists(self.RULES_DIR): os.makedirs(self.RULES_DIR)
                shutil.copy(self.selected_path, self.RULES_DIR)
                self.write_log("UNIT SUCCESS: File ingested.")
                self.update_ui_list()
        except Exception as e:
            self.write_log(f"ERROR: {str(e)}")
        finally:
            self.after(0, self._hide_progress)
            self.after(0, lambda: self.btn_deploy.configure(state="normal", text="LOAD RULE"))

    def run_git_push(self):
        msg = self.commit_input.get()
        if msg and msg != self.placeholder_msg:
            self.write_log("INITIATING CLOUD SYNCHRONIZATION...")
            threading.Thread(target=self._git_task, args=(msg,), daemon=True).start()
        else:
            messagebox.showwarning("System", "Please enter a valid commit message!")

    def _git_task(self, msg):
        try:
            self.after(0, self._show_progress)
            self.after(0, lambda: self.btn_push.configure(state="disabled", text="SYNCING..."))
            
            self.write_log("PATCHING METADATA & STATUS MAP...")         
            for cmd in [["git", "add", "."], ["git", "commit", "-m", msg], ["git", "push", "origin", "main"]]:
                subprocess.run(cmd, check=True, capture_output=True)
                self.write_log(f"GIT: {' '.join(cmd)} - SUCCESS")
            self.write_log("CLOUD SYNC COMPLETE.")
            self.after(0, lambda: self.commit_input.delete(0, 'end'))
            self.after(0, lambda: self._on_focus_out(None))
        except Exception as e:
            self.write_log(f"GIT ERR: {str(e)}")
        finally:
            self.after(0, self._hide_progress)
            self.after(0, lambda: self.btn_push.configure(state="normal", text="GIT PUSH"))

    def _side_btn(self, text, color, cmd):
        btn = ctk.CTkButton(self.sidebar, text=text, fg_color="transparent", text_color=COLOR_TEXT_DARK, border_width=1, border_color=COLOR_BORDER, hover_color="#F0F2F5", font=("Segoe UI", 12, "bold"), height=55, command=cmd)
        btn.pack(fill="x", pady=12, padx=25)
        return btn

    def _add_stat(self, title, value, color):
        f = ctk.CTkFrame(self.header, fg_color=COLOR_FRAME, border_width=1, border_color=COLOR_BORDER, corner_radius=15, width=200)
        f.pack(side="left", expand=True, padx=10, fill="both")
        ctk.CTkLabel(f, text=title, font=("Segoe UI", 10, "bold"), text_color=COLOR_TEXT_MUTED).pack(pady=(15, 0))
        val_label = ctk.CTkLabel(f, text=value, font=("Segoe UI", 18, "bold"), text_color=color)
        val_label.pack(pady=(0, 15))
        return val_label 

if __name__ == "__main__":
    app = SOCXCommand()
    app.mainloop()