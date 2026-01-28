import customtkinter as ctk
from tkinter import filedialog, messagebox
import os, shutil, subprocess, threading, winsound
from datetime import datetime

# --- CẤU HÌNH GIAO DIỆN ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SOCXCommand(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ SOC TACTICAL COMMAND - X PROTOCOL ⚡")
        self.geometry("1100x750")

        # Cấu hình màu sắc Cyberpunk
        self.neon_cyan = "#00F0FF"
        self.neon_green = "#00FF41"
        self.neon_red = "#FF003C"
        
        self.RULES_DIR = "rules/"
        self.selected_path = None
        self.is_folder = False

        self._init_ui()

    def _init_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#0A0A0A", border_width=1, border_color="#1A1A1A")
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(self.sidebar, text="SIEM", font=ctk.CTkFont(size=26, weight="bold", family="Orbitron"), text_color=self.neon_cyan).pack(pady=(50, 5))
        ctk.CTkLabel(self.sidebar, text="AUTOMATION CENTER", font=("Consolas", 10), text_color="gray").pack(pady=(0, 40))

        self.btn_deploy = self._side_btn("LOAD RULE", self.neon_cyan, self.start_deploy_thread)
        self.btn_push = self._side_btn("GIT PUSH", self.neon_green, self.run_git_push)

        # --- MAIN WORKSPACE ---
        self.workspace = ctk.CTkFrame(self, fg_color="#050505", corner_radius=0)
        self.workspace.grid(row=0, column=1, sticky="nsew")

        self.header = ctk.CTkFrame(self.workspace, height=100, fg_color="transparent")
        self.header.pack(fill="x", padx=40, pady=(40, 20))
        
        self._add_stat("TOTAL RULES", "1,266", self.neon_cyan)
        self._add_stat("CLOUD STATUS", "ACTIVE", self.neon_green)
        self._add_stat("SOC OPERATOR", "yuhrt05", self.neon_cyan)

        # Ingestion Console
        self.console_card = ctk.CTkFrame(self.workspace, fg_color="#0F0F0F", border_width=1, border_color="#222", corner_radius=20)
        self.console_card.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(self.console_card, text="❱❱ SIGMA DATA INGESTION", font=("Consolas", 14, "bold"), text_color="#555").pack(anchor="w", padx=30, pady=(20, 10))
        
        ctrl_f = ctk.CTkFrame(self.console_card, fg_color="transparent")
        ctrl_f.pack(fill="x", padx=30, pady=(0, 20))

        self.btn_browse = ctk.CTkButton(ctrl_f, text="BROWSE DATA", width=160, height=45, fg_color="#1A1A1A", border_width=1, border_color=self.neon_cyan, command=self.browse_data)
        self.btn_browse.pack(side="left", padx=5)

        self.lbl_path = ctk.CTkLabel(ctrl_f, text="WAITING FOR DATA INPUT...", text_color="#444", font=("Consolas", 12))
        self.lbl_path.pack(side="left", padx=20)

        self.commit_input = ctk.CTkEntry(ctrl_f, placeholder_text="ENCRYPTED COMMIT MSG...", width=320, height=45, fg_color="#000", border_color="#222")
        self.commit_input.pack(side="right", padx=10)

        # Terminal Output
        self.term_frame = ctk.CTkFrame(self.workspace, fg_color="#000", border_width=1, border_color=self.neon_cyan, corner_radius=10)
        self.term_frame.pack(fill="both", expand=True, padx=40, pady=(20, 40))
        
        self.log_box = ctk.CTkTextbox(self.term_frame, fg_color="transparent", text_color=self.neon_green, font=("Consolas", 14))
        self.log_box.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.write_log("WAR ROOM PROTOCOL INITIALIZED. STANDING BY.")

    def write_log(self, msg):
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] > {msg}\n")
        self.log_box.see("end")

    def browse_data(self):
        choice = messagebox.askyesno("Data Type", "FOLDER (Yes) / FILE (No)?")
        if choice:
            path = filedialog.askdirectory()
            self.is_folder = True
        else:
            path = filedialog.askopenfilename(filetypes=[("Sigma Rules", "*.yml *.yaml")])
            self.is_folder = False
        
        if path:
            self.selected_path = path
            type_str = "DIR" if self.is_folder else "FILE"
            self.lbl_path.configure(text=f"{type_str}: {os.path.basename(path).upper()}", text_color=self.neon_cyan)
            self.write_log(f"PATH STAGED: {path}")
            winsound.Beep(1200, 150)

    def start_deploy_thread(self):
        if not self.selected_path:
            messagebox.showwarning("System", "No data selected!")
            return
        threading.Thread(target=self.run_deploy, daemon=True).start()

    def run_deploy(self):
        """Logic Ingestion: Giữ nguyên cấu trúc thư mục lồng nhau"""
        self.write_log(f"INJECTING DATA...")
        self.btn_deploy.configure(state="disabled", text="PROCESSING...")
        
        try:
            # Tên thư mục gốc mà người dùng đã chọn
            base_folder_name = os.path.basename(self.selected_path)
            # Thư mục đích cuối cùng: rules/ten_thu_muc_chon
            target_base_dir = os.path.join(self.RULES_DIR, base_folder_name)

            count = 0
            if self.is_folder:
                for root, dirs, files in os.walk(self.selected_path):
                    for file in files:
                        if file.endswith(('.yml', '.yaml')):
                            # 1. Lấy đường dẫn tương đối của file so với thư mục gốc được chọn
                            relative_path = os.path.relpath(root, self.selected_path)
                            
                            # 2. Tạo đường dẫn đích tương ứng trong thư mục rules/
                            dest_dir = os.path.join(target_base_dir, relative_path)
                            
                            if not os.path.exists(dest_dir):
                                os.makedirs(dest_dir)
                            
                            source_file = os.path.join(root, file)
                            shutil.copy(source_file, dest_dir)
                            count += 1
                
                self.write_log(f"SUCCESS: {count} rules ingested into {target_base_dir}")
            else:
                # Nếu là 1 file đơn lẻ, copy thẳng vào rules/
                if not os.path.exists(self.RULES_DIR): os.makedirs(self.RULES_DIR)
                shutil.copy(self.selected_path, self.RULES_DIR)
                self.write_log(f"UNIT SUCCESS: {os.path.basename(self.selected_path)} ingested.")
            
            winsound.Beep(2000, 200)
        except Exception as e:
            self.write_log(f"CRITICAL ERROR: {str(e)}")
        finally:
            self.btn_deploy.configure(state="normal", text="LOAD RULE")

    def run_git_push(self):
        msg = self.commit_input.get()
        if not msg:
            messagebox.showwarning("System", "Input Commit Message!")
            return
        threading.Thread(target=self._git_task, args=(msg,), daemon=True).start()

    def _git_task(self, msg):
        try:
            for cmd in [["git", "add", "."], ["git", "commit", "-m", msg], ["git", "push", "origin", "main"]]:
                subprocess.run(cmd, check=True, capture_output=True)
                self.write_log(f"GIT: {' '.join(cmd)} - SUCCESS")
            self.write_log("✅ CLOUD SYNC COMPLETE.")
        except Exception as e:
            self.write_log(f"❌ GIT ERROR: {str(e)}")

    def _side_btn(self, text, color, cmd):
        btn = ctk.CTkButton(self.sidebar, text=text, fg_color="#111", border_width=1, border_color=color, hover_color=color, font=("Consolas", 13, "bold"), height=55, command=cmd)
        btn.pack(fill="x", pady=12, padx=25)
        return btn

    def _add_stat(self, title, value, color):
        f = ctk.CTkFrame(self.header, fg_color="#0A0A0A", border_width=1, border_color="#1A1A1A", corner_radius=15, width=200)
        f.pack(side="left", expand=True, padx=10, fill="both")
        ctk.CTkLabel(f, text=title, font=("Consolas", 10), text_color="#666").pack(pady=(15, 0))
        ctk.CTkLabel(f, text=value, font=("Orbitron", 18, "bold"), text_color=color).pack(pady=(0, 15))

if __name__ == "__main__":
    app = SOCXCommand()
    app.mainloop()