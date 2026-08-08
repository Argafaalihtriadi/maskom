# MaskomApp — Web App Manajemen Infrastruktur IT

Web application berbasis Node.js + Express + EJS untuk manajemen aset komputer, inventaris, kontrol jaringan (Wake-on-LAN), remote control, file transfer, dan monitoring real-time.

---

## Cara Menjalankan

```bash
cd c:\laragon\www\MaskomApp\web_app
npm install
npm start
```

Akses di browser: **http://localhost:3000**

---

## Struktur Proyek

```
web_app/
├── server.js              # Backend Express + semua API endpoint
├── package.json
├── .env                   # Konfigurasi environment (PORT, SESSION_SECRET, dll)
├── data_komputer/         # Folder data JSON per perangkat (output main.py)
├── public/
│   └── screenshots/       # Screenshot hasil monitoring agent
├── uploads/               # File upload sementara
├── Wol pendukung/         # Script client-side
│   ├── Setup-Client.ps1      # Setup lengkap PC client (WOL, remote, agent)
│   ├── Setup-WOL.ps1         # Setup WOL & remote shutdown
│   ├── Agent-Monitor.ps1     # Screen capture agent (berjalan di client)
│   ├── Launcher-Agent.vbs    # VBS launcher (fully hidden, no window/taskbar)
│   ├── Jalankan-Setup-Client.bat
│   └── Jalankan-SetupWOL.bat
├── vnc/
│   └── x64/
│       └── vncviewer.exe  # UltraVNC Viewer executable
└── views/
    ├── partials/
    │   ├── header.ejs
    │   └── footer.ejs
    ├── login.ejs         # Halaman login
    ├── dashboard.ejs     # Halaman dasbor utama
    ├── inventory.ejs     # Halaman daftar inventaris komputer
    ├── asset.ejs         # Halaman detail aset per komputer
    ├── monitoring.ejs    # Halaman monitoring real-time (screenshot)
    ├── wol.ejs           # Halaman Wake-on-LAN
    ├── vnc.ejs           # Halaman Remote Desktop via noVNC
    └── export.ejs        # Halaman ekspor data
```

---

## Fitur yang Sudah Berjalan

### 1. Dashboard
- Ringkasan total aset, status online/offline
- Grafik distribusi OS dan komputer aktif

### 2. Inventaris Komputer (`/inventory`)
Data dibaca langsung dari file `.json` hasil `main.py` di folder `data_komputer/`.

**Fitur:**
- CRUD Aset — Tambah, Edit, Hapus via modal
- Pencarian real-time (search bar)
- Ekspor CSV — Unduh seluruh data inventaris ke file `.csv`
- Impor CSV massal — Upload file CSV untuk update data ke banyak perangkat

### 3. Detail Aset (`/asset/:filename`)
- Spesifikasi lengkap: CPU, RAM, GPU, Mainboard, Storage, OS
- Menampilkan: NO DAT, Serial Number, Departemen, Pengguna
- Identitas Jaringan: IP, MAC, Subnet
- Tombol remote control: VNC, Shutdown, Lock, Kirim Pesan

### 4. Wake-on-LAN (`/wol`)
- Daftar semua perangkat beserta MAC Address
- Multi-select — kirim Magic Packet ke banyak komputer sekaligus
- Pencarian real-time

### 5. Remote Control (`/monitoring`)
- **Shutdown / Restart** — matikan atau restart komputer client dari jarak jauh via WMI
- **Lock Workstation** — kunci layar komputer client
- **Kirim Pesan** — tampilkan popup message di layar client (`msg` command)
- **Jalankan Perintah** — eksekusi command/script apapun di client via WMI
- **File Transfer** — upload file ke client (via WMI atau SMB), download dari client

### 6. Live Monitoring (`/monitoring`)
- Tampilan grid semua perangkat dengan screenshot real-time
- Screenshot otomatis di-refresh setiap 5 detik
- Status online/offline berdasarkan ping
- Pilih perangkat untuk remote control

### 7. Remote Desktop
- **UltraVNC Viewer** — luncurkan VNC viewer langsung dari browser
- **noVNC (Web VNC)** — akses remote desktop langsung di browser tanpa instalasi viewer

### 8. FTP Sync
- Sinkronisasi data inventaris dari FTP server
- Import otomatis file JSON ke folder `data_komputer/`

---

## API Endpoint

### Autentikasi
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/login` | Halaman login |
| `POST` | `/login` | Login (username & password) |
| `GET` | `/logout` | Logout |

### Perangkat (CRUD)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/api/devices` | Ambil semua data perangkat |
| `POST` | `/api/devices` | Tambah perangkat baru |
| `PUT` | `/api/devices/:filename` | Update field perangkat |
| `DELETE` | `/api/devices/:filename` | Hapus perangkat |
| `GET` | `/api/export/inventory.csv` | Ekspor CSV inventaris |

### Wake-on-LAN
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/wol` | Kirim Magic Packet |

**Body:** `{ "macs": ["AA:BB:CC:DD:EE:FF"] }`

### Ping / Status
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/api/ping?ips=...` | Ping satu atau banyak IP |

### Remote Control (via WMI)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/remote/shutdown` | Shutdown / Restart komputer client |
| `POST` | `/api/remote/lock` | Lock workstation client |
| `POST` | `/api/remote/message` | Kirim popup pesan ke client |
| `POST` | `/api/remote/run` | Eksekusi perintah di client |
| `POST` | `/api/remote/vnc` | Luncurkan UltraVNC Viewer |

### File Transfer (via WMI)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/remote/upload` | Upload file ke client (base64) |
| `POST` | `/api/remote/upload-file` | Upload file via multipart form |
| `GET` | `/api/remote/upload-files` | Daftar file yang sudah diupload |

**Body upload (base64):**
```json
{
  "ip": "192.168.1.5",
  "fileName": "file.txt",
  "content": "base64...",
  "destFolder": "C$\\Temp"
}
```

### Monitoring (Screenshot)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/monitor/screenshot/:id` | Upload screenshot dari agent (tanpa auth) |
| `GET` | `/api/monitor/screenshot/:id` | Ambil screenshot (dengan auth) |

### FTP Sync
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/ftp/sync` | Trigger sinkronisasi FTP |
| `GET` | `/api/ftp/status` | Status sinkronisasi terakhir |

---

## Setup PC Client

Agar PC client bisa dikontrol penuh dari dashboard, jalankan script berikut **sebagai Administrator** di PC client:

### Setup Lengkap (WOL + Remote + Agent Monitoring)
```
powershell -ExecutionPolicy Bypass -File "Setup-Client.ps1"
```

Script ini akan:
1. **WOL** — Aktifkan Wake on Magic Packet, matikan Energy Efficient Ethernet, matikan Fast Startup
2. **Remote Shutdown** — Aktifkan firewall SMB-In, nonaktifkan Remote UAC, aktifkan Remote Registry, set LimitBlankPasswordUse=0
3. **Administrator** — Aktifkan account Administrator
4. **File Transfer** — Buat folder `C:\share`, buka firewall WMI
5. **Agent Monitoring** — Install screen capture agent sebagai Scheduled Task (auto-start saat login)
6. **Jalankan agent seka-rang** — langsung mulai monitoring

### Setup WOL Saja
```
powershell -ExecutionPolicy Bypass -File "Setup-WOL.ps1"
```

### Jalankan Tanpa Jendela Terminal
Double-click `Jalankan-Setup-Client.bat` — script berjalan hidden.

---

## Agent Monitoring (Screen Capture)

`Agent-Monitor.ps1` berjalan di background setiap PC client:
- Capture layar setiap 3 detik
- Upload sebagai JPEG ke server via HTTP POST
- Tidak ada jendela/taskbar (dijalankan via VBS launcher)
- Auto-start saat user login (Scheduled Task)
- Tidak mengganggu pekerjaan user

### Uninstall Agent
```
powershell -ExecutionPolicy Bypass -File "Agent-Monitor.ps1" -Uninstall
```

---

## Format Data JSON Perangkat

File disimpan di `data_komputer/<ip>.json`. Web app hanya **menambahkan** field berikut di level root (tidak mengubah data hardware):

```json
{
  "DAT": "C02.123456",
  "Serial Number": "TAC10Y0058",
  "Departemen": "IT Support",
  "Pengguna": "Budi Santoso",

  "Sistem Operasi": "...",
  "CPU": { ... },
  "Memory & SPD": { ... },
  "LAN/Network Card": [ ... ],
  "Penyimpanan": [ ... ]
}
```

---

## Konfigurasi

Buat file `.env` di folder `web_app/`:
```
PORT=3000
SESSION_SECRET=your-secret-key
VNC_PATH=C:\laragon\www\MaskomApp\web_app\vnc\x64\vncviewer.exe
FTP_HOST=your-ftp-server
FTP_USER=your-ftp-user
FTP_PASSWORD=your-ftp-password
FTP_REMOTE_PATH=/data_komputer/
```

| Variabel | Default | Deskripsi |
|----------|---------|-----------|
| `PORT` | `3000` | Port server |
| `SESSION_SECRET` | random | Secret key untuk session |
| `VNC_PATH` | `...vnc\x64\vncviewer.exe` | Path UltraVNC Viewer |
| `FTP_HOST` | - | Host FTP untuk sync data |
| `FTP_USER` | - | User FTP |
| `FTP_PASSWORD` | - | Password FTP |
| `FTP_REMOTE_PATH` | `/data_komputer/` | Path remote FTP |

---

## Dependencies

```json
{
  "@novnc/novnc": "Web VNC client",
  "axios": "HTTP client",
  "basic-ftp": "FTP client",
  "cors": "Cross-origin support",
  "dotenv": "Environment variables",
  "ejs": "Template engine",
  "express": "Web server",
  "express-session": "Session-based auth",
  "multer": "File upload handling",
  "node-cron": "Scheduled tasks",
  "ping": "TCP ping",
  "wake_on_lan": "Kirim Magic Packet WOL",
  "ws": "WebSocket support"
}
```

---

## Catatan Penting

- Jangan format file `.ejs` dengan auto-formatter HTML (Prettier/Beautify), karena akan merusak sintaks EJS
- WMI Remote membutuhkan account Administrator di client dan `LocalAccountTokenFilterPolicy=1`
- Screenshot monitoring hanya bekerja jika ada user yang login di PC client
- WOL hanya bekerja jika komputer target sudah dikonfigurasi di BIOS/UEFI dan Network Adapter
