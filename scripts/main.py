import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import shutil
import subprocess
import threading
import winsound
from datetime import datetime

# --- CONFIG ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SOCCenterTactical(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🛡️ SOC COMMAND CENTER - TACTICAL")
        self.geometry("1000x700")

        # Đường dẫn dựa trên ảnh cấu trúc thư mục của mày
        self.RULES_DIR = "rules/" 
        self.selected_file = None

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#161b22")
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(self.sidebar, text="SOC ENGINE", font=ctk.CTkFont(size=20, weight="bold", family="Consolas")).pack(pady=30)
        
        # Monitor Switch
        self.monitor_switch = ctk.CTkSwitch(self.sidebar, text="LIVE ALERT", progress_color="red", command=self.toggle_monitor)
        self.monitor_switch.pack(pady=20, padx=20)

        self.status_indicator = ctk.CTkLabel(self.sidebar, text="● READY", text_color="#00FF41")
        self.status_indicator.pack(side="bottom", pady=20)

        # --- MAIN CONTENT ---
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # STEP 1: LOCAL STAGING
        self.stage_frame = ctk.CTkFrame(self.main, border_width=1, border_color="#30363d")
        self.stage_frame.pack(fill="x", pady=(0, 15), padx=10)

        ctk.CTkLabel(self.stage_frame, text="PHASE 1: LOCAL RULE INGESTION", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=10)

        self.btn_browse = ctk.CTkButton(self.stage_frame, text="📁 BROWSE SIGMA", command=self.browse_file, fg_color="#21262d")
        self.btn_browse.pack(side="left", padx=20, pady=20)

        self.lbl_file = ctk.CTkLabel(self.stage_frame, text="No file selected", text_color="gray")
        self.lbl_file.pack(side="left", padx=10)

        self.btn_import = ctk.CTkButton(self.stage_frame, text="📥 STAGE TO RULES/", fg_color="#238636", command=self.import_to_local)
        self.btn_import.pack(side="right", padx=20, pady=20)

        # STEP 2: GIT AUTOMATION
        self.git_frame = ctk.CTkFrame(self.main, border_width=1, border_color="#30363d")
        self.git_frame.pack(fill="x", pady=(0, 15), padx=10)

        ctk.CTkLabel(self.git_frame, text="PHASE 2: GITHUB SYNCHRONIZATION", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=10)

        self.entry_commit = ctk.CTkEntry(self.git_frame, placeholder_text="Commit message...", width=450)
        self.entry_commit.pack(side="left", padx=20, pady=20)

        self.btn_push = ctk.CTkButton(self.git_frame, text="☁️ PUSH TO REMOTE", fg_color="#1f6feb", command=self.run_git_push)
        self.btn_push.pack(side="right", padx=20, pady=20)

        # CONSOLE
        self.console = ctk.CTkTextbox(self.main, fg_color="#0d1117", text_color="#00ff41", font=("Consolas", 13))
        self.console.pack(fill="both", expand=True, padx=10, pady=10)

    # --- LOGIC XỬ LÝ (A & B) ---

    def play_sound(self, sound_type="success"):
        if sound_type == "success":
            winsound.Beep(1000, 200) # Tiếng "Ting" ngắn
        elif sound_type == "error":
            winsound.Beep(440, 500)

    def log(self, msg):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.console.insert("end", f"[{time_str}] > {msg}\n")
        self.console.see("end")

    def browse_file(self):
        file = filedialog.askopenfilename(filetypes=[("Sigma", "*.yml *.yaml")])
        if file:
            self.selected_file = file
            self.lbl_file.configure(text=os.path.basename(file), text_color="#58a6ff")

    def import_to_local(self):
        if not self.selected_file:
            self.play_sound("error")
            return
        
        dest = os.path.join(self.RULES_DIR, os.path.basename(self.selected_file))
        shutil.copy(self.selected_file, dest)
        self.log(f"Staged: {os.path.basename(self.selected_file)} -> {self.RULES_DIR}")
        self.play_sound("success")

    def run_git_push(self):
        commit_msg = self.entry_commit.get()
        if not commit_msg:
            messagebox.showwarning("Git Ops", "Vui lòng nhập Commit Message!")
            return
        
        self.btn_push.configure(state="disabled", text="PUSHING...")
        threading.Thread(target=self.execute_git_commands, args=(commit_msg,), daemon=True).start()

    def execute_git_commands(self, msg):
        try:
            # Chuỗi lệnh Git chuẩn
            commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", msg],
                ["git", "push", "origin", "main"]
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                self.log(f"Git: {' '.join(cmd)} - Done")
            
            self.log("✅ CLOUD SYNC COMPLETE. GitHub Actions will handle deployment.")
            self.play_sound("success")
        except Exception as e:
            self.log(f"❌ GIT ERROR: {str(e)}")
            self.play_sound("error")
        finally:
            self.btn_push.configure(state="normal", text="☁️ PUSH TO REMOTE")

    def toggle_monitor(self):
        # Placeholder cho hàm alert.py của mày
        if self.monitor_switch.get():
            self.log("Alert Monitoring: STARTED")
            self.status_indicator.configure(text="● MONITORING", text_color="red")
        else:
            self.log("Alert Monitoring: STOPPED")
            self.status_indicator.configure(text="● READY", text_color="#00FF41")

if __name__ == "__main__":
    app = SOCCenterTactical()
    app.mainloop()