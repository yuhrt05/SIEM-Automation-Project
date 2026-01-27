import customtkinter as ctk
from tkinter import filedialog, messagebox
import os, shutil, subprocess, threading, winsound
from datetime import datetime
from PIL import Image

# --- CYBERPUNK THEME CONFIG ---
ctk.set_appearance_mode("dark")

class SOCWarRoom(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ SOC WAR ROOM - PROTOCOL: ZERO ⚡")
        self.geometry("1200x800")
        
        # Cấu hình màu sắc Neon
        self.neon_blue = "#00F0FF"
        self.neon_green = "#00FF41"
        self.neon_red = "#FF003C"
        self.bg_black = "#050505"

        self.RULES_DIR = "rules/"
        self.selected_file = None

        self._build_interface()

    def _build_interface(self):
        self.configure(fg_color=self.bg_black)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT NAVIGATION BAR (NEON SIDEBAR) ---
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color="#0A0A0A", border_width=1, border_color="#1A1A1A")
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Header Logo với hiệu ứng Glow
        self.logo_label = ctk.CTkLabel(self.sidebar, text="SYSTEM-X", font=ctk.CTkFont(size=28, weight="bold", family="Orbitron"))
        self.logo_label.pack(pady=(50, 0))
        self.status_sub = ctk.CTkLabel(self.sidebar, text="AUTOMATION PROTOCOL ACTIVE", text_color=self.neon_blue, font=("Consolas", 10))
        self.status_sub.pack(pady=(0, 40))

        # Phân đoạn điều khiển
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=20)

        self.btn_deploy = self._create_nav_btn("🚀 DEPLOY UNIT", self.neon_blue, self.run_deploy)
        self.btn_push = self._create_nav_btn("☁️ SYNC CLOUD", self.neon_green, self.run_git_push)

        # Monitor Switch với hiệu ứng cảnh báo
        self.monitor_frame = ctk.CTkFrame(self.sidebar, fg_color="#111", corner_radius=15, border_width=1, border_color=self.neon_red)
        self.monitor_frame.pack(side="bottom", fill="x", padx=20, pady=30)
        
        self.monitor_switch = ctk.CTkSwitch(self.monitor_frame, text="THREAT SCANNER", progress_color=self.neon_red, font=("Consolas", 12, "bold"), command=self.toggle_monitor)
        self.monitor_switch.pack(pady=20, padx=20)

        # --- MAIN COMMAND CENTER ---
        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)

        # Top Bar Stats
        self.stats_bar = ctk.CTkFrame(self.main_view, height=80, fg_color="#0F0F0F", border_width=1, border_color="#222")
        self.stats_bar.pack(fill="x", pady=(0, 25))
        
        self._add_stat("RULES LOADED", "1,266", self.neon_blue) #
        self._add_stat("GH ACTIONS", "ONLINE", self.neon_green) #
        self._add_stat("THREAT LEVEL", "STABLE", self.neon_green)

        # File Operations Card
        self.op_card = ctk.CTkFrame(self.main_view, fg_color="#0A0A0A", border_width=1, border_color="#333", corner_radius=20)
        self.op_card.pack(fill="x", pady=10)

        ctk.CTkLabel(self.op_card, text="❱❱ SIGMA INGESTION INTERFACE", font=("Consolas", 14, "bold"), text_color="#555").pack(anchor="w", padx=30, pady=(20, 10))
        
        input_f = ctk.CTkFrame(self.op_card, fg_color="transparent")
        input_f.pack(fill="x", padx=30, pady=(0, 20))

        self.btn_browse = ctk.CTkButton(input_f, text="BROWSE DATA", width=140, fg_color="#1A1A1A", border_width=1, border_color=self.neon_blue, command=self.browse_file)
        self.btn_browse.pack(side="left", padx=5)

        self.lbl_file = ctk.CTkLabel(input_f, text="WAITING FOR UPLOAD...", text_color="#444", font=("Consolas", 12))
        self.lbl_file.pack(side="left", padx=20)

        self.commit_entry = ctk.CTkEntry(input_f, placeholder_text="ENCRYPTED COMMIT MESSAGE...", width=350, fg_color="#000", border_color="#222")
        self.commit_entry.pack(side="right", padx=10)

        # Terminal Console (Hacker Style)
        self.terminal_f = ctk.CTkFrame(self.main_view, fg_color="#000", border_width=1, border_color=self.neon_blue)
        self.terminal_f.pack(fill="both", expand=True, pady=20)
        
        self.console = ctk.CTkTextbox(self.terminal_f, fg_color="transparent", text_color=self.neon_green, font=("Consolas", 14))
        self.console.pack(fill="both", expand=True, padx=15, pady=15)
        self.log("CORE SYSTEM LOADED. STANDING BY.")

    def _create_nav_btn(self, text, color, cmd):
        btn = ctk.CTkButton(self.nav_frame, text=text, fg_color="#111", border_width=1, border_color=color, hover_color=color, font=("Consolas", 13, "bold"), height=50, command=cmd)
        btn.pack(fill="x", pady=10)
        return btn

    def _add_stat(self, label, value, color):
        f = ctk.CTkFrame(self.stats_bar, fg_color="transparent")
        f.pack(side="left", expand=True)
        ctk.CTkLabel(f, text=label, font=("Consolas", 10), text_color="#666").pack()
        ctk.CTkLabel(f, text=value, font=("Consolas", 18, "bold"), text_color=color).pack()

    # --- LOGIC HANDLING (NGẦU HƠN) ---

    def log(self, msg):
        self.console.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] > {msg}\n")
        self.console.see("end")

    def play_fx(self, freq):
        winsound.Beep(freq, 100) #

    def browse_file(self):
        file = filedialog.askopenfilename()
        if file:
            self.selected_file = file
            self.lbl_file.configure(text=os.path.basename(file).upper(), text_color=self.neon_blue)
            self.play_fx(1500)

    def run_deploy(self):
        if not self.selected_file: return
        self.log(f"INITIATING RULE INGESTION: {os.path.basename(self.selected_file)}")
        dest = os.path.join(self.RULES_DIR, os.path.basename(self.selected_file))
        shutil.copy(self.selected_file, dest)
        self.play_fx(2000)
        self.log("LOCAL STAGING COMPLETE. READY FOR CLOUD SYNC.")

    def run_git_push(self):
        msg = self.commit_entry.get()
        if not msg: return
        self.log("COMMENCING CLOUD SYNCHRONIZATION...")
        threading.Thread(target=self.git_task, args=(msg,), daemon=True).start()

    def git_task(self, msg):
        try:
            for cmd in [["git", "add", "."], ["git", "commit", "-m", msg], ["git", "push", "origin", "main"]]:
                subprocess.run(cmd, check=True, capture_output=True)
                self.log(f"EXECUTING: {' '.join(cmd)}")
            self.log("✅ PROTOCOL ZERO COMPLETE. REMOTE SIEM UPDATED.")
            self.play_fx(2500)
        except:
            self.log("❌ CRITICAL ERROR IN CLOUD UPLOAD.")

    def toggle_monitor(self):
        state = "ACTIVE" if self.monitor_switch.get() else "IDLE"
        self.log(f"THREAT SCANNER: {state}")
        self.play_fx(800 if state == "ACTIVE" else 400)

if __name__ == "__main__":
    app = SOCWarRoom()
    app.mainloop()