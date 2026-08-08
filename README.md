# MaskomApp — Sistem Manajemen Infrastruktur IT

**MaskomApp** adalah aplikasi untuk inventarisasi, pemantauan spesifikasi, dan kontrol jarak jauh komputer dalam satu jaringan lokal (LAN). Project ini terdiri dari dua komponen utama:

1. **Agen Scanner (Python)** — `main.py` — mendeteksi spesifikasi mendalam komputer (CPU, RAM, GPU, Mainboard, Storage, LAN) lalu mengunggahnya ke server FTP terpusat. Juga menyediakan mode Admin *Wake-on-LAN (WOL)* untuk menyalakan komputer lain.
2. **Web App (Node.js + Express + EJS)** — `web_app/` — dashboard inventaris, detail aset, kontrol WOL, dan *Remote Desktop* (UltraVNC) berbasis data JSON hasil scanner.

---

## 🏗️ Arsitektur

```
+-------------------+        FTP (data JSON)        +------------------------+
|  PC Klien (Agent) |  -------------------------->  |  Server FTP Terpusat   |
|  main.py / .exe   |                              |  /maskom/*.json         |
+-------------------+                               +-----------+------------+
                                                              ^
                                                              | sync (cron/manual)
                                                              v
+-------------------+        HTTP (REST API)         +------------------------+
|  Browser Admin    |  <-------------------------->  |  Web App (Node.js)     |
|  Dashboard / WOL  |                              |  web_app/server.js       |
+-------------------+                               +------------------------+
                                                              |
                                                              | spawn (VNC)
                                                              v
                                                   UltraVNC Viewer (Remote Desktop)
```

---

## 📁 Struktur Direktori

```
MaskomApp/
├── main.py                     # Agen scanner PC + Mode Admin WOL (di-build jadi .exe via main.spec)
├── main.spec                   # Konfigurasi PyInstaller untuk build executable
├── spesifikasi_komputer.py     # Versi mandiri scanner spesifikasi (output spesifikasi_lengkap_komputer.json)
├── spesifikasi_lengkap_komputer.json  # Contoh/output spesifikasi lokal
├── project_plan_pengembangan.md       # Roadmap & rencana fitur lanjutan
│
├── web_app/                    # 🌐 APLIKASI WEB (lihat penjelasan di bawah)
│   ├── server.js               # Backend Express + semua API endpoint
│   ├── package.json
│   ├── .env.example            # Template konfigurasi environment
│   ├── data_komputer/          # Folder data JSON per perangkat (hasil sync FTP)
│   ├── vnc/x64/vncviewer.exe   # UltraVNC Viewer executable
│   ├── views/                  # Template EJS (dashboard, inventory, asset, wol)
│   └── public/                 # Asset statis (CSS, JS, gambar)
│
├── Wol pendukung/              # 🔧 Script bantu persiapan WOL di sisi klien
│   ├── Setup-WOL.ps1           # Audit & perbaiki setting WOL Windows (Administrator)
│   └── Jalankan-SetupWOL.bat   # Launcher script di atas
│
└── UI MENU WEB/                # 🎨 Desain/prototype UI (kode HTML & screenshot)
    ├── dasbor_utama/
    ├── inventaris_komputer/
    ├── detail_aset_support224/
    ├── kontrol_wake_on_lan/
    └── protech_infrastructure_system/
```

---

## ⚙️ Prasyarat

- **Python 3.10+** (untuk menjalankan agen scanner) dengan library:
  ```bash
  pip install py-cpuinfo psutil
  ```
- **Node.js 18+** dan `npm` (untuk web app).
- **Server FTP** di jaringan lokal (default `192.168.33.181`) untuk pertukaran data JSON.
- **UltraVNC Server** sudah aktif di masing-masing PC klien agar *Remote Desktop* berfungsi.

---

## 🚀 Cara Menjalankan

### A. Agen Scanner (PC Klien)

```bash
# Mode 1 (default): cek spesifikasi & upload ke FTP
python main.py

# Mode 2: Mode Admin WOL (nyalakan komputer lain)
python main.py
# lalu pilih "2" pada menu
```

> Atau gunakan file executable hasil build (`main.exe`) tanpa perlu instal Python.

### B. Web App (Server / Admin)

```bash
cd web_app
npm install
cp .env.example .env      # lalu isi FTP_HOST, FTP_USER, FTP_PASS, dll
npm start
```

Buka **http://localhost:3000** di browser.

---

## 🌐 Fitur Web App

| Fitur | Penjelasan |
|---|---|
| 📊 **Dashboard** | Ringkasan total aset, status online/offline, grafik distribusi OS. |
| 🖥️ **Inventaris** (`/inventory`) | Tabel aset dari `data_komputer/*.json`. CRUD, pencarian real-time, ekspor/impor CSV, filter multi-departemen/OS. |
| 🔍 **Detail Aset** (`/asset/:filename`) | Spesifikasi lengkap + tombol *Desktop Jarak Jauh* (VNC). |
| ⚡ **Wake-on-LAN** (`/wol`) | Multi-select komputer & kirim Magic Packet. |
| 🖥️ **Remote Desktop** | Meluncurkan UltraVNC Viewer dengan IP target otomatis. |
| 🔄 **FTP Sync** | Sinkronisasi data JSON dari server FTP (otomatis via cron & manual), dengan cooldown anti-spam. |
| 🔌 **Ping Real-time** | Status online/offline & latensi dihitung dari IP perangkat. |

### Endpoint API (ringkas)

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/api/devices` | Ambil semua perangkat |
| `POST` | `/api/devices` | Tambah perangkat |
| `PUT` | `/api/devices/:filename` | Update field perangkat |
| `DELETE` | `/api/devices/:filename` | Hapus perangkat |
| `POST` | `/api/wol` | Kirim Magic Packet (`{ "macs": [...] }`) |
| `POST` | `/api/remote/vnc` | Luncurkan VNC (`{ "ip": "..." }`) |
| `POST` | `/api/ftp/sync` | Trigger sinkronisasi FTP manual |

---

## 🔧 Konfigurasi (`.env`)

| Variabel | Default | Deskripsi |
|---|---|---|
| `PORT` | `3000` | Port web server |
| `FTP_HOST` | `192.168.33.181` | Alamat server FTP |
| `FTP_USER` / `FTP_PASS` | — | Kredensial FTP |
| `FTP_PATH` | `/maskom` | Direktori data di FTP |
| `FTP_PORT` | `21` | Port FTP |
| `FTP_SYNC_CRON` | `0 */1 * * *` | Jadwal auto-sync (cron) |
| `FTP_SYNC_COOLDOWN` | `30` | Cooldown sync manual (detik) |
| `VNC_PATH` | `...vnc\x64\vncviewer.exe` | Path UltraVNC Viewer |

---

## 🔧 Persiapan WOL di PC Klien

Agar komputer bisa dibangunkan via WOL, jalankan script bantu **sebagai Administrator** di masing-masing PC klien:

```powershell
# Audit saja (tidak mengubah apa pun)
powershell -ExecutionPolicy Bypass -File "Wol pendukung\Setup-WOL.ps1" -AuditOnly

# Audit + perbaiki otomatis (aktifkan Magic Packet, matikan Fast Startup, dll)
powershell -ExecutionPolicy Bypass -File "Wol pendukung\Setup-WOL.ps1"
```

---

## 📝 Catatan Penting

- ⚠️ **Jangan format file `.ejs`** dengan auto-formatter HTML (Prettier/Beautify) karena akan merusak tag EJS `<% %>`. Set ke mode *Plain Text* di editor.
- Field tambahan hasil web (`DAT`, `Serial Number`, `Departemen`, `Pengguna`) **disisipkan** ke JSON tanpa mengubah data spesifikasi hardware dari `main.py`.
- WOL hanya berfungsi jika target sudah dikonfigurasi menerima Magic Packet (BIOS/UEFI + Network Adapter).
- FTP credential tersimpan di konfigurasi — jangan commit file `.env` berisi rahasia ke repository publik.

---

## 🗺️ Roadmap

Lihat [`project_plan_pengembangan.md`](project_plan_pengembangan.md) untuk rencana fitur lanjutan (topologi jaringan dinamis, audit log, autentikasi pengguna, integrasi scan otomatis, dll).
