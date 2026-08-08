import json
import os
import platform
import subprocess
import sys
import getpass
import re
import multiprocessing
import socket
import glob
import threading
import ctypes
import datetime
from ftplib import FTP  # Library bawaan untuk transfer FTP

try:
    import cpuinfo
except ImportError:
    cpuinfo = None

try:
    import psutil
except ImportError:
    psutil = None

# GUI & System Tray Imports (Try/Except graceful fallback)
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

def log_msg(msg):
    """Catat pesan log ke console dan file agent.log."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(base_dir, "agent.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def is_admin():
    """Periksa apakah aplikasi berjalan dengan hak Administrator."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_admin():
    """Minta UAC Windows untuk elevate ke Administrator."""
    if not is_admin() and sys.platform == 'win32':
        try:
            log_msg("Meminta UAC Windows Administrator privilege...")
            params = " ".join([f'"{a}"' for a in sys.argv[1:]])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            sys.exit(0)
        except Exception as e:
            log_msg(f"Gagal elevate admin: {e}")

# ==========================================================================
# KONFIGURASI DINAMIS SERVER & FTP (Dapat Diubah via Form GUI)
# ==========================================================================
DEFAULT_CONFIG = {
    "server_ip": "192.168.33.181",
    "ws_port": 3000,
    "ftp_host": "192.168.33.181",
    "ftp_port": 21,
    "ftp_user": "dpd",
    "ftp_pass": "dpd",
    "ftp_dir": "/maskom",
    "agent_token": "maskom-agent-2024"
}

def get_config_path():
    """Dapatkan path file agent_config.json lokal atau di Program Files."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    local_cfg = os.path.join(base_dir, "agent_config.json")
    if os.path.exists(local_cfg):
        return local_cfg
        
    pf_cfg = os.path.join(r"C:\Program Files\MaskomAgent", "agent_config.json")
    if os.path.exists(pf_cfg):
        return pf_cfg
        
    return local_cfg

def load_config():
    """Muat konfigurasi dari agent_config.json atau default."""
    cfg = DEFAULT_CONFIG.copy()
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception as e:
            print(f"[CONFIG WARN] Gagal membaca {path}: {e}")
    return cfg

def save_config(cfg):
    """Simpan konfigurasi ke agent_config.json dan perbarui global variables."""
    path = get_config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        apply_config(cfg)
        return True, path
    except Exception as e:
        return False, str(e)

# Global variables yang diupdate oleh apply_config()
config = load_config()
FTP_HOST = config.get("ftp_host", "192.168.33.181")
FTP_USER = config.get("ftp_user", "dpd")
FTP_PASS = config.get("ftp_pass", "dpd")
FTP_PORT = int(config.get("ftp_port", 21))
FTP_DIR = config.get("ftp_dir", "/maskom")
SERVER_URL = f"ws://{config.get('server_ip', '192.168.33.181')}:{config.get('ws_port', 3000)}"

def apply_config(cfg):
    global config, FTP_HOST, FTP_USER, FTP_PASS, FTP_PORT, FTP_DIR, SERVER_URL
    config = cfg
    FTP_HOST = cfg.get("ftp_host", "192.168.33.181")
    FTP_USER = cfg.get("ftp_user", "dpd")
    FTP_PASS = cfg.get("ftp_pass", "dpd")
    FTP_PORT = int(cfg.get("ftp_port", 21))
    FTP_DIR = cfg.get("ftp_dir", "/maskom")
    s_ip = cfg.get("server_ip", "192.168.33.181")
    s_port = cfg.get("ws_port", 3000)
    SERVER_URL = f"ws://{s_ip}:{s_port}"

# ==========================================================================
# FORM GUI PENGATURAN SERVER & FTP (Tkinter)
# ==========================================================================
def show_config_gui():
    """Tampilkan jendela GUI Form Pengaturan Server & FTP."""
    if not HAS_TKINTER:
        print("[ERROR] Tkinter tidak tersedia di environment Python ini.")
        return

    cfg = load_config()
    
    root = tk.Tk()
    root.title("Pengaturan Server & FTP - MaskomAgent")
    root.geometry("460x520")
    root.resizable(False, False)
    
    BG_COLOR = "#f7f9fb"
    PRIMARY_COLOR = "#494bd6"
    root.configure(bg=BG_COLOR)

    # Header
    header = tk.Frame(root, bg=PRIMARY_COLOR, height=60)
    header.pack(fill="x")
    header.pack_propagate(False)
    
    lbl_title = tk.Label(header, text="⚙️ Pengaturan Server & FTP MaskomAgent", fg="white", bg=PRIMARY_COLOR, font=("Segoe UI", 12, "bold"))
    lbl_title.pack(pady=15)

    # Container Form
    form_frame = tk.Frame(root, bg=BG_COLOR, padx=25, pady=15)
    form_frame.pack(fill="both", expand=True)

    fields = {}

    def create_field(parent, label_text, key, default_val, show_char=None):
        lbl = tk.Label(parent, text=label_text, bg=BG_COLOR, font=("Segoe UI", 9, "bold"), fg="#333333")
        lbl.pack(anchor="w", pady=(8, 2))
        entry = tk.Entry(parent, font=("Segoe UI", 10), show=show_char, bd=1, relief="solid")
        entry.insert(0, str(default_val))
        entry.pack(fill="x", ipady=4)
        fields[key] = entry

    # Server IP & Port
    row_server = tk.Frame(form_frame, bg=BG_COLOR)
    row_server.pack(fill="x")
    
    lbl_s_ip = tk.Label(row_server, text="IP Server Web / WebSocket:", bg=BG_COLOR, font=("Segoe UI", 9, "bold"), fg="#333333")
    lbl_s_ip.pack(anchor="w", pady=(4, 2))
    entry_s_ip = tk.Entry(row_server, font=("Segoe UI", 10), bd=1, relief="solid")
    entry_s_ip.insert(0, str(cfg.get("server_ip", "192.168.33.181")))
    entry_s_ip.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 5))
    fields["server_ip"] = entry_s_ip

    lbl_ws_port = tk.Label(row_server, text="Port WS:", bg=BG_COLOR, font=("Segoe UI", 9, "bold"), fg="#333333")
    lbl_ws_port.pack(side="left", padx=(5, 0))
    entry_ws_port = tk.Entry(row_server, font=("Segoe UI", 10), width=6, bd=1, relief="solid")
    entry_ws_port.insert(0, str(cfg.get("ws_port", 3000)))
    entry_ws_port.pack(side="left", ipady=4)
    fields["ws_port"] = entry_ws_port

    # FTP Host & Port
    row_ftp = tk.Frame(form_frame, bg=BG_COLOR)
    row_ftp.pack(fill="x", pady=(10, 0))
    
    lbl_f_host = tk.Label(row_ftp, text="FTP Host / IP:", bg=BG_COLOR, font=("Segoe UI", 9, "bold"), fg="#333333")
    lbl_f_host.pack(anchor="w", pady=(4, 2))
    entry_f_host = tk.Entry(row_ftp, font=("Segoe UI", 10), bd=1, relief="solid")
    entry_f_host.insert(0, str(cfg.get("ftp_host", "192.168.33.181")))
    entry_f_host.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 5))
    fields["ftp_host"] = entry_f_host

    lbl_f_port = tk.Label(row_ftp, text="Port FTP:", bg=BG_COLOR, font=("Segoe UI", 9, "bold"), fg="#333333")
    lbl_f_port.pack(side="left", padx=(5, 0))
    entry_f_port = tk.Entry(row_ftp, font=("Segoe UI", 10), width=6, bd=1, relief="solid")
    entry_f_port.insert(0, str(cfg.get("ftp_port", 21)))
    entry_f_port.pack(side="left", ipady=4)
    fields["ftp_port"] = entry_f_port

    create_field(form_frame, "Username FTP:", "ftp_user", cfg.get("ftp_user", "dpd"))
    create_field(form_frame, "Password FTP:", "ftp_pass", cfg.get("ftp_pass", "dpd"), show_char="*")
    create_field(form_frame, "Folder Directory FTP:", "ftp_dir", cfg.get("ftp_dir", "/maskom"))

    def test_connection():
        s_ip = fields["server_ip"].get().strip()
        ws_p = fields["ws_port"].get().strip()
        f_host = fields["ftp_host"].get().strip()
        f_port = fields["ftp_port"].get().strip()

        ws_ok, ftp_ok = False, False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((s_ip, int(ws_p)))
            sock.close()
            ws_ok = True
        except Exception:
            ws_ok = False

        try:
            ftp = FTP()
            ftp.connect(f_host, int(f_port), timeout=3)
            ftp.login(fields["ftp_user"].get().strip(), fields["ftp_pass"].get().strip())
            ftp.quit()
            ftp_ok = True
        except Exception:
            ftp_ok = False

        msg = f"Hasil Uji Koneksi:\n\n• WebSocket ({s_ip}:{ws_p}): {'🟢 TERHUBUNG' if ws_ok else '🔴 GAGAL'}\n• Server FTP ({f_host}:{f_port}): {'🟢 TERHUBUNG' if ftp_ok else '🔴 GAGAL'}"
        messagebox.showinfo("Hasil Uji Koneksi", msg, parent=root)

    def on_save():
        new_cfg = {
            "server_ip": fields["server_ip"].get().strip(),
            "ws_port": int(fields["ws_port"].get().strip() or 3000),
            "ftp_host": fields["ftp_host"].get().strip(),
            "ftp_port": int(fields["ftp_port"].get().strip() or 21),
            "ftp_user": fields["ftp_user"].get().strip(),
            "ftp_pass": fields["ftp_pass"].get().strip(),
            "ftp_dir": fields["ftp_dir"].get().strip(),
            "agent_token": cfg.get("agent_token", "maskom-agent-2024")
        }

        success, res_path = save_config(new_cfg)
        if success:
            messagebox.showinfo("SUKSES", f"Konfigurasi berhasil disimpan ke:\n{res_path}", parent=root)
            root.destroy()
        else:
            messagebox.showerror("ERROR", f"Gagal menyimpan konfigurasi: {res_path}", parent=root)

    # Frame Buttons
    btn_frame = tk.Frame(form_frame, bg=BG_COLOR)
    btn_frame.pack(fill="x", pady=(15, 0))

    btn_test = tk.Button(btn_frame, text="🧪 Uji Koneksi", command=test_connection, bg="#6c757d", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=6)
    btn_test.pack(side="left")

    btn_save = tk.Button(btn_frame, text="💾 Simpan Konfigurasi", command=on_save, bg=PRIMARY_COLOR, fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=15, pady=6)
    btn_save.pack(side="right")

    root.mainloop()

# ==========================================================================
# FITUR AUTO SETUP WOL & INSTALLER ALL-IN-ONE
# ==========================================================================
def setup_wol():
    """Setup Wake-on-LAN (Magic Packet) pada Adapter LAN & Matikan Fast Startup Windows."""
    print("\n[WOL SETUP] Mengonfigurasi adapter jaringan & Power Settings...")
    if sys.platform != 'win32':
        print("[WOL SETUP] Hanya mendukung sistem operasi Windows.")
        return False

    ps_script = """
    $adapters = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.HardwareInterface -eq $true }
    foreach ($adapter in $adapters) {
        try {
            Enable-NetAdapterPowerManagement -Name $adapter.Name -WakeOnMagicPacket -ErrorAction SilentlyContinue
            Write-Host "Magic Packet diaktifkan pada: $($adapter.Name)"
        } catch {}
    }
    Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power' -Name 'HiberbootEnabled' -Value 0 -Force -ErrorAction SilentlyContinue
    powercfg /h off
    """
    try:
        res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True)
        print("[WOL SETUP SUKSES] Fast Startup dimatikan & Magic Packet diaktifkan pada kartu jaringan.")
        return True
    except Exception as e:
        print(f"[WOL SETUP ERROR] Gagal mengonfigurasi WOL: {e}")
        return False

def install_agent(server_ip=None, ws_port=None):
    """Instal agen ke C:\\Program Files\\MaskomAgent, daftarkan Registry Auto-start, Firewall, & WOL."""
    print("\n============================================================")
    print("  INSTALASI ALL-IN-ONE MASKOM AGENT                         ")
    print("============================================================")
    
    cfg = load_config()
    if server_ip:
        cfg["server_ip"] = server_ip
        cfg["ftp_host"] = server_ip
    if ws_port:
        cfg["ws_port"] = int(ws_port)

    install_dir = r"C:\Program Files\MaskomAgent"
    try:
        os.makedirs(install_dir, exist_ok=True)
    except Exception as e:
        print(f"[ERROR] Gagal membuat direktori {install_dir}. Pastikan dijalankan sebagai Administrator: {e}")
        return False

    # Stop proses main.exe yang sedang berjalan (selain PID saat ini)
    subprocess.run('taskkill /f /im main.exe /fi "PID ne %d"' % os.getpid(), shell=True, capture_output=True)

    is_frozen = getattr(sys, 'frozen', False)
    exe_src = sys.executable if is_frozen else os.path.abspath(__file__)
    target_exe = os.path.join(install_dir, "main.exe")

    if is_frozen and exe_src.lower() != target_exe.lower():
        import shutil
        try:
            shutil.copy2(exe_src, target_exe)
            print(f"[1/5] Executable disalin ke: {target_exe}")
            src_internal = os.path.join(os.path.dirname(exe_src), "_internal")
            dst_internal = os.path.join(install_dir, "_internal")
            if os.path.exists(src_internal):
                shutil.copytree(src_internal, dst_internal, dirs_exist_ok=True)
                print(f"      Folder '_internal' disalin ke: {dst_internal}")
        except Exception as e:
            print(f"[WARN] Gagal menyalin file (kemungkinan sedang berjalan): {e}")

    # Simpan config
    target_cfg = os.path.join(install_dir, "agent_config.json")
    save_config(cfg)
    try:
        with open(target_cfg, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        print(f"[2/5] Konfigurasi disimpan ke: {target_cfg}")
    except Exception as e:
        print(f"[WARN] Gagal menyimpan file config di install_dir: {e}")

    # Registry Startup
    startup_cmd = f'"{target_exe}" --daemon' if is_frozen else f'python "{os.path.abspath(__file__)}" --daemon'
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "MaskomAgent", 0, winreg.REG_SZ, startup_cmd)
        winreg.CloseKey(key)
        print(f"[3/5] Registry Auto-start didaftarkan: MaskomAgent")
    except Exception as e:
        print(f"[WARN] Gagal mendaftarkan registry startup (butuh Admin privilege): {e}")

    # Firewall Rule
    try:
        fw_cmd = f'netsh advfirewall firewall add rule name="MaskomAgent-WebSocket" dir=out action=allow protocol=TCP localport=any remoteport={cfg["ws_port"]}'
        subprocess.run(fw_cmd, shell=True, capture_output=True)
        print(f"[4/5] Windows Firewall Outbound Rule (Port {cfg['ws_port']}) ditambahkan.")
    except Exception as e:
        print(f"[WARN] Firewall rule setup: {e}")

    # Setup WOL
    print("[5/5] Mengonfigurasi Wake-on-LAN...")
    setup_wol()

    print("\n============================================================")
    print("  INSTALASI SELESAI & AGENT AKTIF!                          ")
    print("============================================================")
    print(f"  Server WebSocket : ws://{cfg['server_ip']}:{cfg['ws_port']}")
    print(f"  FTP Server       : {cfg['ftp_host']}:{cfg['ftp_port']} (Folder: {cfg['ftp_dir']})")
    print("============================================================")

    # Jalankan daemon sekarang di background
    if is_frozen and os.path.exists(target_exe):
        subprocess.Popen([target_exe, "--daemon"], creationflags=0x08000000) # DETACHED_PROCESS
        print("  Agen telah diluncurkan di background (System Tray Icon).")

    return True


# DATABASE UNTUK COCHOKAN SOCKET SECARA OTOMATIS
DATABASE_SOCKET = {
    "Socket 1700 LGA": ["G7400", "G6900", "I3-12", "I5-12", "I7-12", "I9-12", "I3-13", "I5-13", "I7-13", "I9-13", "I3-14", "I5-14", "I7-14", "I9-14", "ALDER LAKE", "RAPTOR LAKE"],
    "Socket 1200 LGA": ["G5900", "G5920", "G6400", "I3-10", "I5-10", "I7-10", "I9-10", "I3-11", "I5-11", "I7-11", "I9-11", "COMET LAKE", "ROCKET LAKE"],
    "Socket 1151 LGA": ["G4900", "G4920", "G5400", "I3-8", "I5-8", "I7-8", "I9-8", "I3-9", "I5-9", "I7-9", "I9-9", "G3900", "G3930", "G4400", "G4560", "I3-6", "I5-6", "I7-6", "I3-7", "I5-7", "I7-7", "COFFEE LAKE", "KABY LAKE", "SKYLAKE"],
    "Socket 1150 LGA": ["G1820", "G3220", "G3420", "I3-4", "I5-4", "I7-4", "HASWELL"],
    "Socket 1155 LGA": ["G530", "G620", "G2020", "I3-2", "I5-2", "I7-2", "I3-3", "I5-3", "I7-3", "SANDY BRIDGE", "IVY BRIDGE"],
    "Socket AM5": ["RYZEN 5 7", "RYZEN 7 7", "RYZEN 9 7", "RYZEN 5 8", "RYZEN 7 8", "RYZEN 5 9", "RYZEN 7 9", "RYZEN 9 9"],
    "Socket AM4": ["RYZEN 3 1", "RYZEN 5 1", "RYZEN 7 1", "RYZEN 3 2", "RYZEN 5 2", "RYZEN 7 2", "RYZEN 3 3", "RYZEN 5 3", "RYZEN 7 3", "RYZEN 9 3", "RYZEN 3 5", "RYZEN 5 5", "RYZEN 7 5", "RYZEN 9 5", "ATHLON 200", "ATHLON 3000", "ZEN 2", "ZEN 3"]
}

def run_command(cmd):
    try:
        return subprocess.check_output(cmd, shell=True).decode().strip()
    except Exception:
        return ""

def parse_wmic_list(wmic_output):
    result = {}
    for line in wmic_output.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result

def tentukan_tipe_ddr(memory_type, smbios_type):
    mt = int(memory_type) if memory_type.isdigit() else 0
    st = int(smbios_type) if smbios_type.isdigit() else 0
    target = st if st > 0 else mt
    mapping = {20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
    return mapping.get(target, "DDR4") 

def get_cpu_z_style():
    os.environ['PYCPUINFO_INTERNET_CONTROLS'] = 'False'
    info = cpuinfo.get_cpu_info()
    wmic_name = run_command("wmic cpu get name /Format:List").replace("Name=", "").strip()
    specification = wmic_name if wmic_name else info.get("brand_raw", "Unknown")
    name = specification.replace("Intel(R) ", "").replace("AMD ", "").split("@")[0].strip()
    
    arch_string = info.get("arch_string_raw", "").upper()
    brand_raw = info.get("brand_raw", "").upper()
    
    code_name = "Unknown"
    package_socket = "Unknown"
    for socket, keywords in DATABASE_SOCKET.items():
        for kw in keywords:
            if kw in brand_raw or kw in arch_string:
                package_socket = socket
                if "7400" in brand_raw or "ALDER" in arch_string: code_name = "Alder Lake"
                elif "RAPTOR" in arch_string: code_name = "Raptor Lake"
                elif "COMET" in arch_string: code_name = "Comet Lake"
                elif "COFFEE" in arch_string: code_name = "Coffee Lake"
                elif "ZEN 3" in arch_string or "5000" in brand_raw: code_name = "Vermeer / Cezanne"
                break
                
    try:
        current_speed_mhz = psutil.cpu_freq().current
        core_speed = f"{round(current_speed_mhz, 2)} MHz"
    except Exception:
        core_speed = "Unknown"

    return {
        "Name": name,
        "Code Name": code_name,
        "Package": package_socket,
        "Specification": specification,
        "Core Speed": core_speed,
        "Cores": psutil.cpu_count(logical=False),
        "Threads": psutil.cpu_count(logical=True)
    }

def get_mainboard_z_style():
    manufacturer = run_command("wmic baseboard get manufacturer /Format:List").replace("Manufacturer=", "").strip()
    product = run_command("wmic baseboard get product /Format:List").replace("Product=", "").strip()
    version = run_command("wmic baseboard get version /Format:List").replace("Version=", "").strip()
    
    if "default string" in product.lower() or not product:
        sys_model = run_command("wmic computersystem get model /Format:List").replace("Model=", "").strip()
        if sys_model:
            product = f"Default String (System Model: {sys_model})"
            
    bios_vendor = run_command("wmic bios get manufacturer /Format:List").replace("Manufacturer=", "").strip()
    bios_version = run_command("wmic bios get smbiosbiosversion /Format:List").replace("SMBIOSBIOSVersion=", "").strip()
    bios_date = run_command("wmic bios get releasedate /Format:List").replace("ReleaseDate=", "").strip()
    if bios_date and len(bios_date) >= 8:
        bios_date = f"{bios_date[4:6]}/{bios_date[6:8]}/{bios_date[0:4]}"

    return {
        "Motherboard Manufacturer": manufacturer,
        "Model": product,
        "Version": version if version else "Rev 1.0",
        "BIOS Vendor": bios_vendor,
        "BIOS Version": bios_version,
        "BIOS Date": bios_date
    }

def get_memory_z_style():
    virtual_mem = psutil.virtual_memory()
    total_ram_gb = f"{round(virtual_mem.total / (1024**3), 2)} GB"
    
    ram_cmd = "wmic memorychip get Manufacturer, Speed, MemoryType, SMBIOSMemoryType, Capacity, PartNumber /Format:List"
    ram_output = run_command(ram_cmd)
    blocks = ram_output.split("\n\n")
    
    list_keping = []
    tipe_umum = "DDR4"
    speed_umum = "Unknown"
    
    for block in blocks:
        if not block.strip(): continue
        data = parse_wmic_list(block)
        if data:
            cap = data.get("Capacity", "0")
            cap_gb = f"{round(int(cap) / (1024**3))} GB" if cap.isdigit() else "Unknown"
            speed = data.get("Speed", "Unknown")
            if speed != "Unknown": speed_umum = f"{speed} MHz"
            tipe_ddr = tentukan_tipe_ddr(data.get("MemoryType", "0"), data.get("SMBIOSMemoryType", "0"))
            tipe_umum = tipe_ddr
            
            list_keping.append({
                "Slot/Keping": f"Slot #{len(list_keping)+1}",
                "Ukuran (Size)": cap_gb,
                "Merk/Manufaktur": data.get("Manufacturer", "Generic").strip(),
                "Part Number": data.get("PartNumber", "Unknown").strip(),
                "Max Bandwidth/Speed": f"{speed} MHz"
            })
            
    channel = "Single" if len(list_keping) == 1 else "Dual" if len(list_keping) == 2 else "Multi Channel"
    if not list_keping: channel = "Unknown"

    return {
        "General": {
            "Type": tipe_umum,
            "Total Size": total_ram_gb,
            "Channel #": channel,
            "DRAM Frequency": speed_umum
        },
        "SPD (Detail per Slot)": list_keping
    }

def get_storage_detail():
    storage_list = []
    ps_cmd = 'powershell "Get-PhysicalDisk | Select-Object DeviceId, Model, MediaType, Size, BusType | ConvertTo-Json"'
    ps_output = run_command(ps_cmd)
    
    try:
        disks = json.loads(ps_output)
        if isinstance(disks, dict): disks = [disks]
        for d in disks:
            bus_type = d.get("BusType", "")
            media_type = d.get("MediaType", "SSD")
            
            if "NVMe" in bus_type or "NVME" in str(d.get("Model")).upper():
                tipe_spesifik = "SSD NVMe (PCIe High Speed)"
                speed_est = "Up to 3500 - 7500 MB/s"
            elif media_type == "SSD":
                tipe_spesifik = "SSD SATA"
                speed_est = "Up to 550 MB/s"
            else:
                tipe_spesifik = "HDD Mechanical Drive"
                speed_est = "Up to 100 - 150 MB/s"
            
            storage_list.append({
                "Model/Nama Drive": d.get("Model").strip(),
                "Tipe Interfasi": tipe_spesifik,
                "Koneksi Bus": bus_type,
                "Kapasitas": f"{round(d.get('Size', 0) / (1024**3), 2)} GB",
                "Estimasi Batas Speed": speed_est
            })
    except Exception:
        for part in psutil.disk_partitions():
            if 'fixed' in part.opts:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    storage_list.append({"Drive Letter": part.mountpoint, "Kapasitas": f"{round(usage.total / (1024**3), 2)} GB", "Tipe": "Fixed Drive"})
                except: pass
    return storage_list

def get_gpu_detail():
    gpu_cmd = "wmic path win32_VideoController get Name, AdapterRAM, DriverVersion /Format:List"
    gpu_output = run_command(gpu_cmd)
    blocks = gpu_output.split("\n\n")
    gpus = []
    for b in blocks:
        if not b.strip(): continue
        data = parse_wmic_list(b)
        if data:
            vram_raw = data.get("AdapterRAM", "0")
            vram = f"{round(int(vram_raw) / (1024**2))} MB" if vram_raw.isdigit() and int(vram_raw) > 0 else "Shared System Memory"
            gpus.append({
                "Name/Model": data.get("Name"),
                "Dedicated VRAM": vram,
                "Driver Version": data.get("DriverVersion")
            })
    return gpus

def get_lan_card_detail():
    ipconfig_output = run_command("ipconfig /all")
    sections = re.split(r'(Ethernet adapter|Wireless LAN adapter)', ipconfig_output)
    adapters_dict = {}
    
    for i in range(1, len(sections), 2):
        adapter_type = sections[i].strip()
        adapter_body = sections[i+1] if i+1 < len(sections) else ""
        
        match_name = re.search(r'^(.*?):', adapter_body)
        if not match_name: continue
        adapter_display_name = f"{adapter_type} {match_name.group(1).strip()}"
        
        desc = ""
        mac = "Unknown"
        ipv4 = "Disconnected / No IP"
        subnet = "Unknown"
        gateway = "Unknown"
        dns_servers = []
        inside_dns = False
        
        for line in adapter_body.splitlines():
            line_clean = line.strip()
            if not line_clean: continue
            
            if "Description" in line_clean and ":" in line_clean:
                desc = line_clean.split(":", 1)[1].strip()
            elif "Physical Address" in line_clean and ":" in line_clean:
                mac = line_clean.split(":", 1)[1].strip().replace("-", ":").upper()
            elif "IPv4 Address" in line_clean and ":" in line_clean:
                ipv4 = line_clean.split(":", 1)[1].replace("(Preferred)", "").strip()
            elif "Subnet Mask" in line_clean and ":" in line_clean:
                subnet = line_clean.split(":", 1)[1].strip()
            elif "Default Gateway" in line_clean and ":" in line_clean:
                gw_val = line_clean.split(":", 1)[1].strip()
                if gw_val: gateway = gw_val
            elif "DNS Servers" in line_clean and ":" in line_clean:
                dns_val = line_clean.split(":", 1)[1].strip()
                if dns_val: dns_servers.append(dns_val)
                inside_dns = True
                continue
            
            if inside_dns:
                if ":" not in line_clean and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', line_clean):
                    dns_servers.append(line_clean)
                else:
                    inside_dns = False

        if not desc: 
            desc = adapter_display_name

        desc_lower = desc.lower()
        kategori = "Wireless Wi-Fi Adapter" if "wireless" in desc_lower or "wi-fi" in desc_lower or "wlan" in desc_lower else "LAN / Ethernet Card (Kabel)"

        key_unik = mac if mac != "Unknown" else desc
        adapters_dict[key_unik] = {
            "Description (Nama Perangkat)": desc,
            "Merk/Manufaktur": "Intel" if "intel" in desc_lower else "D-Link / Realtek" if "dge" in desc_lower else "Unknown",
            "Kategori Perangkat": kategori,
            "Status Hardware": "Connected (Terhubung)" if ipv4 != "Disconnected / No IP" else "Disabled / Disconnected",
            "Physical Address (MAC)": mac,
            "IPv4 Address": ipv4,
            "Subnet Mask": subnet,
            "Default Gateway": gateway,
            "DNS Servers": ", ".join(dns_servers) if dns_servers else "Unknown"
        }

    cmd_hardware = "wmic nic where \"PhysicalAdapter=true\" get Name, Manufacturer, MACAddress, NetConnectionStatus /Format:List"
    output_hardware = run_command(cmd_hardware)
    
    for b in output_hardware.split("\n\n"):
        if not b.strip(): continue
        data = parse_wmic_list(b)
        name = data.get("Name", "").strip()
        if not name: continue
        if "miniport" in name.lower() or "vpn" in name.lower(): continue
        
        hardware_mac = data.get("MACAddress", "").strip().replace("-", ":").upper()
        status_code = data.get("NetConnectionStatus", "")
        
        if status_code == "2": status_koneksi = "Connected (Terhubung)"
        elif status_code == "7": status_koneksi = "Media Disconnected (Kabel Cabut)"
        else: status_koneksi = "Disabled (Dinonaktifkan)"

        key_check = hardware_mac if hardware_mac else name
        
        if key_check in adapters_dict:
            if adapters_dict[key_check]["IPv4 Address"] == "Disconnected / No IP":
                adapters_dict[key_check]["Status Hardware"] = status_koneksi
            if data.get("Manufacturer"):
                adapters_dict[key_check]["Merk/Manufaktur"] = data.get("Manufacturer").strip()
        else:
            name_lower = name.lower()
            kategori = "Wireless Wi-Fi Adapter" if "wireless" in name_lower or "wi-fi" in name_lower else "LAN / Ethernet Card (Kabel)"
            
            adapters_dict[key_check] = {
                "Description (Nama Perangkat)": name,
                "Merk/Manufaktur": data.get("Manufacturer", "Unknown").strip(),
                "Kategori Perangkat": kategori,
                "Status Hardware": status_koneksi,
                "Physical Address (MAC)": hardware_mac if hardware_mac else "Unknown",
                "IPv4 Address": "Disconnected / No IP",
                "Subnet Mask": "Unknown",
                "Default Gateway": "Unknown",
                "DNS Servers": "Unknown"
            }

    return list(adapters_dict.values())

def upload_to_ftp(file_path):
    print(f"\n[FTP] Mencoba menghubungkan ke FTP Server {FTP_HOST}...")
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)
        
        # Pindah ke direktori target /maskom
        try:
            ftp.cwd(FTP_DIR)
        except Exception:
            # Jika direktori belum ada, coba buat
            ftp.mkd(FTP_DIR)
            ftp.cwd(FTP_DIR)
            
        # Upload file dalam mode binary
        file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            ftp.storbinary(f'STOR {file_name}', f)
            
        ftp.quit()
        print(f"[FTP SUKSES] File {file_name} berhasil dikirim ke folder {FTP_DIR} di FTP Server!")
    except Exception as e:
        print(f"[FTP ERROR] Gagal mengirim file ke FTP Server: {e}")
        print("[INFO] File JSON tetap tersimpan dengan aman di folder lokal komputer ini.")


# ==========================================================================
# FITUR BARU: WAKE ON LAN (WOL) MANAGER
# Memakai data MAC Address yang sudah dikumpulkan oleh fitur spec-checker,
# dan server FTP yang sama (FTP_HOST/FTP_DIR) sebagai sumber data terpusat.
# ==========================================================================

def send_magic_packet(mac_address, broadcast_ip="255.255.255.255", port=9):
    """Kirim 'magic packet' Wake-on-LAN ke satu MAC address."""
    mac_clean = re.sub(r'[^0-9A-Fa-f]', '', mac_address)
    if len(mac_clean) != 12:
        raise ValueError(f"MAC address tidak valid: {mac_address}")

    mac_bytes = bytes.fromhex(mac_clean)
    magic_packet = b'\xff' * 6 + mac_bytes * 16

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.sendto(magic_packet, (broadcast_ip, port))
    finally:
        sock.close()


def download_json_files_from_ftp(local_dir):
    """Unduh semua file .json (hasil spec-checker tiap komputer) dari FTP Server."""
    os.makedirs(local_dir, exist_ok=True)
    downloaded = 0
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_DIR)

        filenames = [f for f in ftp.nlst() if f.lower().endswith(".json")]
        for fname in filenames:
            local_path = os.path.join(local_dir, fname)
            with open(local_path, "wb") as f:
                ftp.retrbinary(f"RETR {fname}", f.write)
            downloaded += 1
        ftp.quit()
        print(f"[FTP] Berhasil mengunduh {downloaded} file data komputer dari server.")
    except Exception as e:
        print(f"[FTP ERROR] Gagal mengunduh data dari server: {e}")
        print("[INFO] Akan mencoba memakai data JSON lokal (jika ada) di folder yang sama.")
    return downloaded


def load_devices_from_json_folder(folder):
    """Baca semua file JSON hasil spec-checker di sebuah folder, ambil hostname + MAC + IP."""
    devices = []
    for filepath in glob.glob(os.path.join(folder, "*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        whoami = data.get("User Session (Whoami)") or {}
        hostname = whoami.get("Hostname", os.path.basename(filepath))
        username = whoami.get("Username", "-")

        lan_cards = data.get("LAN/Network Card") or []
        target_mac, target_ip = None, None

        # Prioritas: kartu LAN/Ethernet kabel yang statusnya Connected, baru Wi-Fi
        for kategori_prior in ["LAN / Ethernet Card (Kabel)", "Wireless Wi-Fi Adapter"]:
            for card in lan_cards:
                mac = card.get("Physical Address (MAC)", "Unknown")
                status = card.get("Status Hardware", "")
                if card.get("Kategori Perangkat") == kategori_prior and status.startswith("Connected") and mac != "Unknown":
                    target_mac = mac
                    target_ip = card.get("IPv4 Address", "Unknown")
                    break
            if target_mac:
                break

        if not target_mac:
            continue  # lewati komputer yang tidak punya MAC valid

        devices.append({
            "file": os.path.basename(filepath),
            "hostname": hostname,
            "username": username,
            "ip": target_ip,
            "mac": target_mac,
        })

    devices.sort(key=lambda d: d["hostname"])
    return devices


def jalankan_mode_wol():
    """Mode Admin: unduh data spesifikasi semua komputer, lalu nyalakan yang dipilih via WOL."""
    print("\n==========================================================")
    print(" MODE ADMIN - WAKE ON LAN MANAGER ")
    print("==========================================================")

    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    data_dir = os.path.join(base_dir, "data_komputer")
    print("Mengunduh data spesifikasi terbaru dari server FTP...")
    download_json_files_from_ftp(data_dir)

    devices = load_devices_from_json_folder(data_dir)
    if not devices:
        # Fallback: pakai file JSON lokal di folder yang sama (mis. saat testing offline)
        devices = load_devices_from_json_folder(base_dir)

    if not devices:
        print("\n[INFO] Tidak ada data komputer (JSON) yang ditemukan / punya MAC Address valid.")
        input("\nTekan ENTER untuk kembali...")
        return

    while True:
        print("\n--- DAFTAR KOMPUTER TERDAFTAR ---")
        for idx, d in enumerate(devices, start=1):
            print(f"{idx}. {d['hostname']} ({d['username']}) | IP: {d['ip']} | MAC: {d['mac']}")

        print("\nPilih nomor komputer yang mau dinyalakan (pisahkan koma untuk banyak),")
        print("ketik 'all' untuk nyalakan semua, atau 'exit' untuk keluar.")
        pilihan = input("Pilihan Anda: ").strip().lower()

        if pilihan == "exit":
            break

        if pilihan == "all":
            target_list = devices
        else:
            try:
                indices = [int(x.strip()) for x in pilihan.split(",") if x.strip()]
                target_list = [devices[i - 1] for i in indices if 1 <= i <= len(devices)]
            except Exception:
                print("[ERROR] Input tidak valid, coba lagi.")
                continue

        if not target_list:
            print("[INFO] Tidak ada komputer yang dipilih.")
            continue

        for d in target_list:
            try:
                send_magic_packet(d["mac"])
                print(f"[WOL SUKSES] Sinyal nyala terkirim ke {d['hostname']} (MAC: {d['mac']})")
            except Exception as e:
                print(f"[WOL GAGAL] {d['hostname']}: {e}")

        lagi = input("\nMau kirim WOL lagi? (y/n): ").strip().lower()
        if lagi != "y":
            break

def main():
    multiprocessing.freeze_support()

    print("==========================================================")
    print(" SPECHECK - Spesifikasi Komputer & Wake on LAN Manager ")
    print("==========================================================")
    print(" 1. Cek & Kirim Spesifikasi Komputer Ini   (Mode Client)")
    print(" 2. Kelola Wake on LAN - Nyalakan Komputer Lain (Mode Admin)")
    print("==========================================================")
    mode = input("Masukkan pilihan (1/2) [default 1]: ").strip()

    if mode == "2":
        jalankan_mode_wol()
        return

    print("\n==========================================================")
    print(" Mengekstrak Spesifikasi Komputer & Jaringan... ")
    print(" Mohon tunggu beberapa saat, jangan tutup jendela ini... ")
    print("==========================================================")
    
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. PENCARIAN DATA SEPERTI WHOAMI (Username dan Hostname)
    current_username = getpass.getuser()
    current_hostname = platform.node()
    whoami_style = f"{current_hostname}\\{current_username}"
    
    cpu_info = get_cpu_z_style()
    lan_cards = get_lan_card_detail()
    
    # 2. STRATEGI GENERATE NAMA FILE BERDASARKAN IP INTEL CONNECTIONS ONBOARD
    ip_onboard = ""
    for card in lan_cards:
        desc = str(card.get("Description (Nama Perangkat)", "")).lower()
        ip_addr = card.get("IPv4 Address", "Disconnected / No IP")
        
        # Cari adapter yang merupakan Intel Ethernet dan sedang mendapatkan IP aktif
        if "intel" in desc and "ethernet" in desc and ip_addr != "Disconnected / No IP":
            ip_onboard = ip_addr
            break
            
    # Fallback 1: Jika Intel Ethernet terpasang tapi kabelnya dicabut (tidak dapat IP),
    # cari IP aktif pertama dari adapter LAN Kabel/WiFi apa saja yang tersedia.
    if not ip_onboard:
        for card in lan_cards:
            ip_addr = card.get("IPv4 Address", "Disconnected / No IP")
            if ip_addr != "Disconnected / No IP":
                ip_onboard = ip_addr
                break
                
    # Fallback 2: Jika komputer benar-benar offline / dicabut total dari jaringan lokal
    if not ip_onboard or ip_onboard == "Disconnected / No IP":
        ip_onboard = "OFFLINE-NO-IP"

    # Pertahankan format IP dengan titik sebagai nama file (tidak diganti strip), misal: 192.168.32.224.json
    format_nama_ip = ip_onboard
    nama_file_json = f"{format_nama_ip}.json"
    
    # Susun semua spesifikasi ke dalam satu dictionary JSON
    full_specs = {
        "User Session (Whoami)": {
            "Username": current_username,
            "Hostname": current_hostname,
            "Full Identity": whoami_style
        },
        "Sistem Operasi": platform.system() + " " + platform.release() + " (" + platform.architecture()[0] + ")",
        "CPU": cpu_info,
        "Mainboard": get_mainboard_z_style(),
        "Memory & SPD": get_memory_z_style(),
        "Graphics": get_gpu_detail(),
        "Penyimpanan": get_storage_detail(),
        "LAN/Network Card": lan_cards
    }
    
    # 3. SIMPAN KE FILE JSON LOKAL
    nama_file_lengkap = os.path.join(base_dir, nama_file_json)
    with open(nama_file_lengkap, "w", encoding="utf-8") as f:
        json.dump(full_specs, f, indent=4, ensure_ascii=False)
        
    print("\n[SUKSES] Semua spesifikasi mendalam telah berhasil diekstrak!")
    print(f"File lokal : {nama_file_json}")
    print(f"Lokasi     : {nama_file_lengkap}")
    print("==========================================================")
    
    # 4. KIRIM OTOMATIS KE SERVER FTP TARGET
    upload_to_ftp(nama_file_lengkap)
    print("==========================================================")
    
    input("\nTekan ENTER untuk keluar...")


# ===========================================================================
# MODE DAEMON — Agen WebSocket Realtime
# Jalankan dengan: python main.py --daemon --server ws://192.168.x.x:3000
# Agen akan terhubung terus ke server dan menunggu instruksi jarak jauh.
# ===========================================================================

def collect_specs():
    """
    Kumpulkan semua spesifikasi komputer lokal.
    Mengembalikan dictionary spek lengkap dan nama file JSON (berdasarkan IP).
    """
    current_username = getpass.getuser()
    current_hostname = platform.node()
    whoami_style      = f"{current_hostname}\\{current_username}"

    cpu_info  = get_cpu_z_style()
    lan_cards = get_lan_card_detail()

    # Tentukan IP untuk nama file
    ip_onboard = ""
    for card in lan_cards:
        desc    = str(card.get("Description (Nama Perangkat)", "")).lower()
        ip_addr = card.get("IPv4 Address", "Disconnected / No IP")
        if "intel" in desc and "ethernet" in desc and ip_addr != "Disconnected / No IP":
            ip_onboard = ip_addr
            break
    if not ip_onboard:
        for card in lan_cards:
            ip_addr = card.get("IPv4 Address", "Disconnected / No IP")
            if ip_addr != "Disconnected / No IP":
                ip_onboard = ip_addr
                break
    if not ip_onboard or ip_onboard == "Disconnected / No IP":
        ip_onboard = "OFFLINE-NO-IP"

    full_specs = {
        "User Session (Whoami)": {
            "Username":     current_username,
            "Hostname":     current_hostname,
            "Full Identity": whoami_style
        },
        "Sistem Operasi": platform.system() + " " + platform.release() + " (" + platform.architecture()[0] + ")",
        "CPU":       cpu_info,
        "Mainboard": get_mainboard_z_style(),
        "Memory & SPD": get_memory_z_style(),
        "Graphics":  get_gpu_detail(),
        "Penyimpanan": get_storage_detail(),
        "LAN/Network Card": lan_cards
    }
    return full_specs, f"{ip_onboard}.json"


def deploy_folder(url, zip_name, exec_rel_path="", exec_args="", extract_root=None, deploy_mode="run_exe"):
    """
    Download file .zip dari URL server, ekstrak ke extract_root.
    Opsi 1 (deploy_mode == "file_only" atau exec_rel_path kosong): Hanya kirim & ekstrak file saja (File Sharing).
    Opsi 2 (deploy_mode == "run_exe" dan exec_rel_path diisi): Ekstrak & jalankan program .exe.
    """
    import urllib.request
    import zipfile
    import tempfile

    if extract_root is None or not str(extract_root).strip():
        extract_root = os.path.join("C:\\", "MaskomDeploy")

    os.makedirs(extract_root, exist_ok=True)

    # 1. Download zip ke tempdir
    tmp_zip = os.path.join(tempfile.gettempdir(), zip_name)
    try:
        log_msg(f"[DEPLOY] Mengunduh {url} ...")
        urllib.request.urlretrieve(url, tmp_zip)
        log_msg(f"[DEPLOY] Download selesai -> {tmp_zip}")
    except Exception as e:
        raise RuntimeError(f"Gagal mengunduh file zip: {e}")

    # 2. Ekstrak zip
    extract_dir = os.path.join(extract_root, os.path.splitext(zip_name)[0])
    try:
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(extract_dir)
        log_msg(f"[DEPLOY] Diekstrak ke {extract_dir}")
    except Exception as e:
        raise RuntimeError(f"Gagal mengekstrak zip: {e}")
    finally:
        try:
            os.remove(tmp_zip)
        except Exception:
            pass

    # Jika Mode File Sharing / Only Send Files (tanpa eksekusi .exe)
    if deploy_mode == "file_only" or not exec_rel_path or exec_rel_path.strip() in ["", "-"]:
        log_msg(f"[DEPLOY SUKSES] Mode File Sharing: File berhasil disimpan & diekstrak di {extract_dir}")
        return None

    # 3. Mode Jalankan Program: Eksekusi program / script / file target apapun di path
    target_rel = exec_rel_path.replace("/", os.sep).strip()
    target_path = os.path.join(extract_dir, target_rel)

    actual_path = None
    if os.path.isfile(target_path):
        actual_path = target_path
    else:
        # Jika path diisi tanpa ekstensi, coba cari ekstensi umum
        for ext in [".exe", ".bat", ".cmd", ".ps1", ".msi", ".vbs", ".lnk"]:
            if os.path.isfile(target_path + ext):
                actual_path = target_path + ext
                break
        
        # Jika belum ditemukan, cari file dengan nama tersebut di subfolder ekstraksi
        if not actual_path:
            for root_dir, _, files in os.walk(extract_dir):
                for f in files:
                    if f.lower() == target_rel.lower() or f.lower() == (target_rel + ".exe").lower():
                        actual_path = os.path.join(root_dir, f)
                        break
                if actual_path:
                    break

    if not actual_path or not os.path.exists(actual_path):
        raise RuntimeError(f"File/program tidak ditemukan di: {target_path}")

    ext = os.path.splitext(actual_path)[1].lower()
    args_list = exec_args.strip().split() if exec_args and exec_args.strip() else []

    # Susun komando eksekusi sesuai ekstensi file agar Windows dapat mengeksekusinya
    if ext in [".bat", ".cmd"]:
        cmd = ["cmd.exe", "/c", actual_path] + args_list
    elif ext == ".ps1":
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", actual_path] + args_list
    elif ext == ".msi":
        cmd = ["msiexec.exe", "/i", actual_path] + args_list
    elif ext == ".vbs":
        cmd = ["wscript.exe", actual_path] + args_list
    elif ext == ".py":
        cmd = [sys.executable, actual_path] + args_list
    else:
        cmd = [actual_path] + args_list

    try:
        proc = subprocess.Popen(cmd, cwd=os.path.dirname(actual_path), shell=True)
        log_msg(f"[DEPLOY SUKSES] Menjalankan program {actual_path} (PID: {proc.pid})")
        return proc.pid
    except Exception as e:
        raise RuntimeError(f"Gagal menjalankan program '{actual_path}': {e}")


def install_agent(server_ip=None, ws_port=None):
    """Instal agen ke C:\\Program Files\\MaskomAgent, daftarkan Registry Auto-start, Firewall, & WOL."""
    log_msg("============================================================")
    log_msg("  INSTALASI ALL-IN-ONE MASKOM AGENT                         ")
    log_msg("============================================================")
    
    if not is_admin():
        log_msg("[INFO] Meminta hak akses Administrator...")
        elevate_admin()
        return False

    cfg = load_config()
    if server_ip:
        cfg["server_ip"] = server_ip
        cfg["ftp_host"] = server_ip
    if ws_port:
        cfg["ws_port"] = int(ws_port)

    install_dir = r"C:\Program Files\MaskomAgent"
    try:
        os.makedirs(install_dir, exist_ok=True)
    except Exception as e:
        log_msg(f"[ERROR] Gagal membuat direktori {install_dir}: {e}")
        return False

    # Stop proses main.exe lain yang sedang berjalan (selain PID saat ini)
    try:
        subprocess.run('taskkill /f /im main.exe /fi "PID ne %d"' % os.getpid(), shell=True, capture_output=True)
    except Exception:
        pass

    is_frozen = getattr(sys, 'frozen', False)
    exe_src = sys.executable if is_frozen else os.path.abspath(__file__)
    target_exe = os.path.join(install_dir, "main.exe")

    if is_frozen and exe_src.lower() != target_exe.lower():
        import shutil
        try:
            shutil.copy2(exe_src, target_exe)
            log_msg(f"[1/5] Executable disalin ke: {target_exe}")
            src_internal = os.path.join(os.path.dirname(exe_src), "_internal")
            dst_internal = os.path.join(install_dir, "_internal")
            if os.path.exists(src_internal):
                shutil.copytree(src_internal, dst_internal, dirs_exist_ok=True)
                log_msg(f"      Folder '_internal' disalin ke: {dst_internal}")
        except Exception as e:
            log_msg(f"[WARN] Gagal menyalin file: {e}")

    # Simpan config
    target_cfg = os.path.join(install_dir, "agent_config.json")
    save_config(cfg)
    try:
        with open(target_cfg, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        log_msg(f"[2/5] Konfigurasi disimpan ke: {target_cfg}")
    except Exception as e:
        log_msg(f"[WARN] Gagal menyimpan file config di install_dir: {e}")

    # Registry Startup
    startup_cmd = f'"{target_exe}" --daemon' if is_frozen else f'python "{os.path.abspath(__file__)}" --daemon'
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "MaskomAgent", 0, winreg.REG_SZ, startup_cmd)
        winreg.CloseKey(key)
        log_msg(f"[3/5] Registry Auto-start didaftarkan: MaskomAgent")
    except Exception as e:
        log_msg(f"[WARN] Gagal mendaftarkan registry startup: {e}")

    # Firewall Rule
    try:
        fw_cmd = f'netsh advfirewall firewall add rule name="MaskomAgent-WebSocket" dir=out action=allow protocol=TCP localport=any remoteport={cfg["ws_port"]}'
        subprocess.run(fw_cmd, shell=True, capture_output=True)
        log_msg(f"[4/5] Windows Firewall Outbound Rule (Port {cfg['ws_port']}) ditambahkan.")
    except Exception as e:
        log_msg(f"[WARN] Firewall rule setup: {e}")

    # Setup WOL
    log_msg("[5/5] Mengonfigurasi Wake-on-LAN...")
    setup_wol()

    log_msg("============================================================")
    log_msg("  INSTALASI SELESAI & AGENT AKTIF!                          ")
    log_msg("============================================================")

    return True


def run_daemon(server_url=None):
    """Alias daemon mode ke Jendela GUI Agent Client."""
    show_agent_gui(server_url)

def show_agent_gui(server_url=None):
    """Jendela GUI Utama Agen Client (Status Realtime 🟢/🔴, Log Box, & Controller)."""
    if not HAS_TKINTER:
        log_msg("[WARN] Tkinter tidak tersedia. Menjalankan daemon console mode.")
        run_daemon(server_url)
        return

    cfg = load_config()
    apply_config(cfg)

    if not server_url:
        server_url = SERVER_URL

    current_hostname = platform.node()
    current_ip = "Unknown"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        current_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    root = tk.Tk()
    root.title(f"MaskomAgent Client - {current_hostname}")
    root.geometry("540x480")
    root.resizable(False, False)

    BG_COLOR = "#f7f9fb"
    PRIMARY_COLOR = "#494bd6"
    root.configure(bg=BG_COLOR)

    # Header Card
    header = tk.Frame(root, bg=PRIMARY_COLOR, height=65)
    header.pack(fill="x")
    header.pack_propagate(False)

    lbl_title = tk.Label(header, text=f"💻 MaskomAgent Client — {current_hostname}", fg="white", bg=PRIMARY_COLOR, font=("Segoe UI", 12, "bold"))
    lbl_title.pack(anchor="w", padx=20, pady=(12, 0))

    lbl_sub = tk.Label(header, text=f"IP Local: {current_ip} | Server Host: {cfg.get('server_ip')}:{cfg.get('ws_port')}", fg="#dcdbff", bg=PRIMARY_COLOR, font=("Segoe UI", 9))
    lbl_sub.pack(anchor="w", padx=20, pady=(2, 0))

    # Status Banner Card
    status_card = tk.Frame(root, bg="#ffffff", bd=1, relief="solid")
    status_card.pack(fill="x", padx=15, pady=12)

    lbl_status_icon = tk.Label(status_card, text="🟡", bg="#ffffff", font=("Segoe UI", 18))
    lbl_status_icon.pack(side="left", padx=15, pady=10)

    status_text_frame = tk.Frame(status_card, bg="#ffffff")
    status_text_frame.pack(side="left", fill="both", expand=True, pady=10)

    lbl_status_title = tk.Label(status_text_frame, text="MENGHUBUNGKAN KE SERVER...", fg="#333333", bg="#ffffff", font=("Segoe UI", 10, "bold"))
    lbl_status_title.pack(anchor="w")

    lbl_status_desc = tk.Label(status_text_frame, text=f"Target: ws://{cfg.get('server_ip')}:{cfg.get('ws_port')}", fg="#666666", bg="#ffffff", font=("Segoe UI", 9))
    lbl_status_desc.pack(anchor="w")

    # Realtime Log Area
    lbl_log = tk.Label(root, text="📋 Catatan Aktivitas Real-time (Log):", bg=BG_COLOR, font=("Segoe UI", 9, "bold"), fg="#333333")
    lbl_log.pack(anchor="w", padx=15, pady=(5, 2))

    log_frame = tk.Frame(root, bg=BG_COLOR)
    log_frame.pack(fill="both", expand=True, padx=15)

    txt_log = tk.Text(log_frame, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", bd=1, relief="solid", height=10)
    txt_log.pack(fill="both", expand=True)

    def gui_log(msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        log_msg(msg)
        try:
            txt_log.config(state="normal")
            txt_log.insert("end", line)
            txt_log.see("end")
            txt_log.config(state="disabled")
        except Exception:
            pass

    def update_status_ui(is_connected, message):
        try:
            if is_connected:
                lbl_status_icon.config(text="🟢")
                lbl_status_title.config(text="TERHUBUNG KE SERVER (ONLINE)", fg="#28a745")
            else:
                lbl_status_icon.config(text="🔴")
                lbl_status_title.config(text="TERPUTUS / RECONNECTING...", fg="#dc3545")
            lbl_status_desc.config(text=message)
        except Exception:
            pass

    # Tombol Aksi
    btn_frame = tk.Frame(root, bg=BG_COLOR)
    btn_frame.pack(fill="x", padx=15, pady=12)

    def on_scan_click():
        def run_scan():
            gui_log("Memulai scan spesifikasi manual...")
            try:
                specs, fname = collect_specs()
                base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
                local_path = os.path.join(base_dir, fname)
                with open(local_path, "w", encoding="utf-8") as f:
                    json.dump(specs, f, indent=4, ensure_ascii=False)
                upload_to_ftp(local_path)
                gui_log(f"SUKSES: Scan selesai. File {fname} terkirim ke FTP.")
                messagebox.showinfo("Scan Selesai", f"Data spesifikasi {fname} berhasil di-scan & dikirim ke FTP!", parent=root)
            except Exception as e:
                gui_log(f"ERROR: Gagal scan spesifikasi: {e}")
                messagebox.showerror("Error Scan", f"Gagal scan: {e}", parent=root)

        threading.Thread(target=run_scan, daemon=True).start()

    def on_open_settings():
        show_config_gui()
        c = load_config()
        lbl_sub.config(text=f"IP Local: {current_ip} | Server Host: {c.get('server_ip')}:{c.get('ws_port')}")
        lbl_status_desc.config(text=f"Target: ws://{c.get('server_ip')}:{c.get('ws_port')}")

    def on_hide_to_tray():
        root.withdraw()
        gui_log("Jendela disembunyikan ke System Tray (Pojok Kanan Jam).")

    btn_cfg = tk.Button(btn_frame, text="⚙️ Pengaturan Server", command=on_open_settings, bg="#6c757d", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=6)
    btn_cfg.pack(side="left")

    btn_scan = tk.Button(btn_frame, text="🔄 Scan Spesifikasi", command=on_scan_click, bg=PRIMARY_COLOR, fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=6)
    btn_scan.pack(side="left", padx=8)

    btn_hide = tk.Button(btn_frame, text="📌 Sembunyikan", command=on_hide_to_tray, bg="#17a2b8", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=6)
    btn_hide.pack(side="right")

    # Thread Background WebSocket
    AGENT_TOKEN = cfg.get("agent_token", "maskom-agent-2024")

    def ws_loop():
        import time
        import websocket

        while True:
            c = load_config()
            target_ws_url = f"ws://{c.get('server_ip', '192.168.33.181')}:{c.get('ws_port', 3000)}/ws/agent/{current_hostname}"

            try:
                gui_log(f"Menghubungkan ke {target_ws_url} ...")
                update_status_ui(False, f"Menghubungkan ke {target_ws_url}...")

                def on_open(ws):
                    reg = json.dumps({
                        "type": "register",
                        "hostname": current_hostname,
                        "ip": current_ip,
                        "token": AGENT_TOKEN
                    })
                    ws.send(reg)
                    gui_log(f"Terhubung & terdaftar di server: {target_ws_url}")
                    update_status_ui(True, f"Terhubung aktif ke ws://{c.get('server_ip')}:{c.get('ws_port')}")

                def on_message(ws, message):
                    try:
                        data = json.loads(message)
                    except Exception:
                        return

                    action = data.get("action")
                    req_id = data.get("req_id", "")
                    gui_log(f"Perintah diterima dari server: {action} (req_id={req_id})")

                    def send_status(status, payload=None):
                        resp = {
                            "type": "agent_response",
                            "req_id": req_id,
                            "hostname": current_hostname,
                            "status": status
                        }
                        if payload: resp.update(payload)
                        try: ws.send(json.dumps(resp))
                        except Exception: pass

                    if action == "scan_spec":
                        try:
                            send_status("scanning")
                            specs, fname = collect_specs()
                            base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
                            local_path = os.path.join(base_dir, fname)
                            with open(local_path, "w", encoding="utf-8") as f:
                                json.dump(specs, f, indent=4, ensure_ascii=False)
                            upload_to_ftp(local_path)
                            gui_log(f"Perintah Scan selesai. File {fname} dikirim ke FTP.")
                            send_status("success", {"message": f"Scan selesai. File {fname} terkirim.", "filename": fname})
                        except Exception as e:
                            gui_log(f"Perintah Scan Gagal: {e}")
                            send_status("error", {"message": str(e)})

                    elif action == "deploy_folder":
                        url           = data.get("url")
                        zip_name      = data.get("zip_name")
                        exec_rel_path = data.get("exec_path", "")
                        exec_args     = data.get("exec_args", "")
                        extract_root  = data.get("extract_root", None)
                        deploy_mode   = data.get("deploy_mode", "file_only" if not exec_rel_path else "run_exe")

                        if not url or not zip_name:
                            send_status("error", {"message": "Parameter deploy tidak lengkap (url/zip_name)."})
                            return

                        try:
                            send_status("downloading")
                            gui_log(f"Mulai download paket deploy: {zip_name} (Mode: {deploy_mode}) ...")
                            pid = deploy_folder(url, zip_name, exec_rel_path, exec_args, extract_root, deploy_mode)
                            if pid:
                                gui_log(f"Deploy & Jalankan Program Sukses. PID: {pid}")
                                send_status("success", {"message": f"Program '{exec_rel_path}' berhasil dijalankan (PID: {pid}).", "pid": pid})
                            else:
                                gui_log(f"Deploy File Sharing Sukses. File disimpan & diekstrak di PC klien.")
                                send_status("success", {"message": f"File '{zip_name}' berhasil dikirim dan diekstrak ke PC klien (Mode File Sharing)."})
                        except Exception as e:
                            gui_log(f"Deploy gagal: {e}")
                            send_status("error", {"message": str(e)})

                def on_error(ws, error):
                    gui_log(f"WebSocket error: {error}")
                    update_status_ui(False, f"WebSocket error: {error}")

                def on_close(ws, code, msg):
                    gui_log(f"Koneksi terputus. Reconnecting dalam 10 detik...")
                    update_status_ui(False, "Koneksi terputus. Reconnecting...")

                ws_app = websocket.WebSocketApp(
                    target_ws_url,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                ws_app.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                gui_log(f"Error loop koneksi: {e}")
                update_status_ui(False, f"Gagal terhubung: {e}")

            time.sleep(10)

    threading.Thread(target=ws_loop, daemon=True).start()

    # System Tray Icon Thread
    if HAS_PYSTRAY:
        def setup_tray():
            try:
                img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.ellipse((4, 4, 60, 60), fill=(73, 75, 214, 255))
                draw.rectangle((18, 18, 46, 46), fill=(255, 255, 255, 255))

                def on_restore_window(icon, item):
                    root.after(0, root.deiconify)

                def on_open_settings_tray(icon, item):
                    root.after(0, show_config_gui)

                def on_exit_tray(icon, item):
                    icon.stop()
                    root.after(0, root.destroy)
                    os._exit(0)

                menu = pystray.Menu(
                    pystray.MenuItem("💻 Buka Tampilan Agent", on_restore_window, default=True),
                    pystray.MenuItem("⚙️ Pengaturan Server & FTP", on_open_settings_tray),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("❌ Keluar / Stop Agen", on_exit_tray)
                )

                tray = pystray.Icon("MaskomAgent", img, f"MaskomAgent - {current_hostname}", menu)
                tray.run()
            except Exception as e:
                gui_log(f"Tray Icon warn: {e}")

        threading.Thread(target=setup_tray, daemon=True).start()

    def on_window_close():
        root.withdraw()
        gui_log("Jendela disembunyikan ke System Tray (Pojok Kanan Jam).")

    root.protocol("WM_DELETE_WINDOW", on_window_close)
    root.mainloop()


def main():
    multiprocessing.freeze_support()

    if "--config" in sys.argv:
        show_config_gui()
        return

    if "--setup-wol" in sys.argv:
        if not is_admin(): elevate_admin()
        setup_wol()
        return

    if "--install" in sys.argv:
        if not is_admin(): elevate_admin()
        server_ip, ws_port = None, None
        for i, arg in enumerate(sys.argv):
            if arg == "--server" and i + 1 < len(sys.argv): server_ip = sys.argv[i + 1]
            if arg == "--port" and i + 1 < len(sys.argv): ws_port = sys.argv[i + 1]
        install_agent(server_ip, ws_port)
        show_agent_gui()
        return

    if "--daemon" in sys.argv:
        show_agent_gui()
        return

    # Jika dijalankan langsung (tanpa argumen CLI):
    # Tampilkan Jendela GUI Utama Agen Client (Status Realtime, Log, Controller)
    if is_admin():
        try:
            install_agent()
        except Exception as e:
            log_msg(f"Auto install warn: {e}")

    show_agent_gui()

if __name__ == '__main__':
    main()