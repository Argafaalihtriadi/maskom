import json
import os
import platform
import subprocess
import cpuinfo  # Pastikan sudah: pip install py-cpuinfo
import psutil

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
            
            # Mendeteksi NVMe vs SATA SSD vs HDD
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
    import re

    # 1. Jalankan perintah ipconfig /all secara langsung
    ipconfig_output = run_command("ipconfig /all")
    
    # Pecah output berdasarkan "Ethernet adapter" atau "Wireless LAN adapter"
    sections = re.split(r'(Ethernet adapter|Wireless LAN adapter)', ipconfig_output)
    
    adapters_dict = {}
    
    # 2. Parsing text ipconfig secara terstruktur
    for i in range(1, len(sections), 2):
        adapter_type = sections[i].strip()
        adapter_body = sections[i+1] if i+1 < len(sections) else ""
        
        # Ambil nama adapter (misal: "32" atau "AT & HH")
        match_name = re.search(r'^(.*?):', adapter_body)
        if not match_name: continue
        adapter_display_name = f"{adapter_type} {match_name.group(1).strip()}"
        
        # Ekstrak field-field penting dari teks di bawahnya
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
            
            # Deteksi Deskripsi Perangkat (Hardware Name)
            if "Description" in line_clean and ":" in line_clean:
                desc = line_clean.split(":", 1)[1].strip()
            # Deteksi Alamat Fisik (MAC Address)
            elif "Physical Address" in line_clean and ":" in line_clean:
                mac = line_clean.split(":", 1)[1].strip().replace("-", ":").upper()
            # Deteksi IPv4 Address
            elif "IPv4 Address" in line_clean and ":" in line_clean:
                ipv4 = line_clean.split(":", 1)[1].replace("(Preferred)", "").strip()
            # Deteksi Subnet Mask
            elif "Subnet Mask" in line_clean and ":" in line_clean:
                subnet = line_clean.split(":", 1)[1].strip()
            # Deteksi Default Gateway
            elif "Default Gateway" in line_clean and ":" in line_clean:
                gw_val = line_clean.split(":", 1)[1].strip()
                if gw_val: gateway = gw_val
            # Deteksi DNS Servers
            elif "DNS Servers" in line_clean and ":" in line_clean:
                dns_val = line_clean.split(":", 1)[1].strip()
                if dns_val: dns_servers.append(dns_val)
                inside_dns = True
                continue
            
            # Jika baris selanjutnya masih merupakan bagian dari baris DNS Server multi-line
            if inside_dns:
                if ":" not in line_clean and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', line_clean):
                    dns_servers.append(line_clean)
                else:
                    inside_dns = False

        if not desc: 
            desc = adapter_display_name

        # Tentukan Kategori Perangkat
        desc_lower = desc.lower()
        if "wireless" in desc_lower or "wi-fi" in desc_lower or "wlan" in desc_lower:
            kategori = "Wireless Wi-Fi Adapter"
        else:
            kategori = "LAN / Ethernet Card (Kabel)"

        # Gunakan MAC atau Deskripsi sebagai key unik agar tidak dobel
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

    # 3. Sinkronisasi paksa dengan database perangkat fisik terpasang lewat WMIC NIC 
    # Langkah ini untuk memastikan adapter yang sedang "Disabled total" (tidak muncul di ipconfig) tetap tertangkap hardwarenya.
    cmd_hardware = "wmic nic where \"PhysicalAdapter=true\" get Name, Manufacturer, MACAddress, NetConnectionStatus /Format:List"
    output_hardware = run_command(cmd_hardware)
    
    for b in output_hardware.split("\n\n"):
        if not b.strip(): continue
        data = parse_wmic_list(b)
        name = data.get("Name", "").strip()
        if not name: continue
        
        # Abaikan miniport virtual bawaan OS
        if "miniport" in name.lower() or "vpn" in name.lower(): continue
        
        hardware_mac = data.get("MACAddress", "").strip().replace("-", ":").upper()
        status_code = data.get("NetConnectionStatus", "")
        
        # Terjemahkan status Windows connection
        if status_code == "2": status_koneksi = "Connected (Terhubung)"
        elif status_code == "7": status_koneksi = "Media Disconnected (Kabel Cabut)"
        else: status_koneksi = "Disabled (Dinonaktifkan)"

        key_check = hardware_mac if hardware_mac else name
        
        if key_check in adapters_dict:
            # Jika di ipconfig terbaca terhubung, biarkan statusnya terhubung
            if adapters_dict[key_check]["IPv4 Address"] == "Disconnected / No IP":
                adapters_dict[key_check]["Status Hardware"] = status_koneksi
            if data.get("Manufacturer"):
                adapters_dict[key_check]["Merk/Manufaktur"] = data.get("Manufacturer").strip()
        else:
            # Jika hardware ada tapi tidak terdeteksi sama sekali di ipconfig (Berarti statusnya mati total/Disabled)
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

def main():
    print("Mengekstrak seluruh data spesifikasi + Perangkat Jaringan... Mohon tunggu.")
    cpu_info = get_cpu_z_style()
    
    full_specs = {
        "Sistem Operasi": platform.system() + " " + platform.release() + " (" + platform.architecture()[0] + ")",
        "CPU": cpu_info,
        "Mainboard": get_mainboard_z_style(),
        "Memory & SPD": get_memory_z_style(),
        "Graphics": get_gpu_detail(),
        "Penyimpanan": get_storage_detail(),
        "LAN/Network Card": get_lan_card_detail()
    }
    
    nama_file = "spesifikasi_lengkap_komputer.json"
    with open(nama_file, "w", encoding="utf-8") as f:
        json.dump(full_specs, f, indent=4, ensure_ascii=False)
        
    print(f"\nSelesai! Semua spesifikasi mendalam telah disimpan di:\n{os.path.abspath(nama_file)}")

if __name__ == '__main__':
    main()