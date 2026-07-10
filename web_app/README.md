# MaskomApp — Web App Manajemen Infrastruktur IT

Web application berbasis Node.js + Express + EJS untuk manajemen aset komputer, inventaris, dan kontrol jaringan (Wake-on-LAN & Remote Desktop).

---

## 🚀 Cara Menjalankan

```bash
cd c:\laragon\www\MaskomApp\web_app
npm install
npm start
```

Akses di browser: **http://localhost:3000**

---

## 📁 Struktur Proyek

```
web_app/
├── server.js              # Backend Express + semua API endpoint
├── package.json
├── data_komputer/         # Folder data JSON per perangkat (output main.py)
├── vnc/
│   └── x64/
│       └── vncviewer.exe  # UltraVNC Viewer executable
└── views/
    ├── partials/
    │   ├── header.ejs
    │   └── footer.ejs
    ├── dashboard.ejs       # Halaman dasbor utama
    ├── inventory.ejs       # Halaman daftar inventaris komputer
    ├── asset.ejs           # Halaman detail aset per komputer
    └── wol.ejs             # Halaman Wake-on-LAN
```

---

## ✅ Fitur yang Sudah Berjalan

### 1. 📊 Dashboard
- Ringkasan total aset, status online/offline
- Grafik distribusi OS dan komputer aktif

### 2. 🖥️ Inventaris Komputer (`/inventory`)
Data dibaca langsung dari file `.json` hasil `main.py` di folder `data_komputer/`.

**Kolom Tabel:**
| Kolom | Sumber Data |
|---|---|
| Nama Perangkat | `User Session (Whoami).Hostname` |
| NO DAT | `DAT` *(field khusus, bisa diisi manual)* |
| Serial Number | `Serial Number` *(field khusus, bisa diisi manual)* |
| Departemen | `Departemen` *(field khusus, bisa diisi manual)* |
| User | `Pengguna` atau fallback ke `Username` Windows |
| Alamat IP | `LAN/Network Card[].IPv4 Address` |
| OS | `Sistem Operasi` |
| RAM | `Memory & SPD.General.Total Size` + Tipe DDR |
| Penyimpanan | `Penyimpanan[0]` — deteksi otomatis HDD/SSD |
| Status | Aktif (default) |

**Fitur Tambahan di Halaman Inventaris:**
- ✅ **CRUD Aset** — Tambah, Edit, Hapus via modal
- ✅ **Pencarian real-time** (search bar)
- ✅ **Ekspor CSV** — Unduh seluruh data inventaris ke file `.csv`
- ✅ **Impor CSV massal** — Upload file CSV untuk update NO DAT, Serial, Departemen, Pengguna ke banyak perangkat sekaligus (tanpa merusak data JSON lainnya)

> **Format CSV (8 kolom):**
> `Filename, Hostname, IP Address, OS, NO DAT, Serial Number, Departemen, Pengguna`
>
> ⚠️ Jangan ubah kolom `Filename` — ini adalah kunci referensi ke file JSON.

### 3. 🔍 Detail Aset (`/asset/:filename`)
- Spesifikasi lengkap: CPU, RAM, GPU, Mainboard, Storage, OS
- Menampilkan: NO DAT, Serial Number, Departemen, Pengguna
- Identitas Jaringan: IP, MAC, Subnet
- **Tombol "Desktop Jarak Jauh"** — meluncurkan UltraVNC Viewer langsung dengan IP pre-filled

### 4. ⚡ Wake-on-LAN (`/wol`)
- Daftar semua perangkat beserta MAC Address
- **Multi-select** — pilih lebih dari 1 komputer sekaligus
- Kirim Magic Packet ke semua komputer yang dicentang
- Pencarian real-time

### 5. 🖥️ Desktop Jarak Jauh (UltraVNC)
- Klik tombol **"Desktop Jarak Jauh"** di halaman detail aset
- Server Node.js akan meluncurkan `vncviewer.exe` dengan IP komputer target otomatis
- Path executable dikonfigurasi di `server.js`:
  ```js
  const VNC_VIEWER_PATH = 'C:\\laragon\\www\\MaskomApp\\web_app\\vnc\\x64\\vncviewer.exe';
  ```

---

## 🔌 API Endpoint

### Perangkat (CRUD)
| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/api/devices` | Ambil semua data perangkat |
| `POST` | `/api/devices` | Tambah perangkat baru |
| `PUT` | `/api/devices/:filename` | Update field perangkat |
| `DELETE` | `/api/devices/:filename` | Hapus perangkat |

**Body `PUT /api/devices/:filename` (semua opsional):**
```json
{
  "hostname": "PC-ADMIN-01",
  "ip": "192.168.1.5",
  "mac": "00:1A:2B:3C:4D:5E",
  "os": "Windows 11",
  "dat": "C02.123456",
  "serial_number": "TAC10Y0058",
  "departement": "IT",
  "pengguna": "Budi Santoso"
}
```

> Field `dat`, `serial_number`, `departement`, `pengguna` disisipkan ke JSON **tanpa mengubah** data spesifikasi hardware lainnya.

### Wake-on-LAN
| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/api/wol` | Kirim Magic Packet |

**Body:**
```json
{ "macs": ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"] }
```

### Remote Desktop (VNC)
| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/api/remote/vnc` | Luncurkan UltraVNC Viewer |

**Body:**
```json
{ "ip": "192.168.1.5" }
```

---

## 🗄️ Format Data JSON Perangkat

File disimpan di `data_komputer/<hostname>.json`. Field yang dihasilkan `main.py` **tidak akan pernah diubah** oleh web app. Web app hanya **menambahkan** field-field berikut di level root:

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

## ⚙️ Konfigurasi

| Variabel | Default | Deskripsi |
|---|---|---|
| `PORT` | `3000` | Port server |
| `VNC_PATH` | `...vnc\x64\vncviewer.exe` | Path UltraVNC Viewer |

Bisa juga diset via environment variable, contoh:
```bash
$env:VNC_PATH="C:\Program Files\UltraVNC\vncviewer.exe"
npm start
```

---

## 📦 Dependencies

```json
{
  "express": "web server",
  "ejs": "template engine",
  "cors": "cross-origin support",
  "wake_on_lan": "kirim Magic Packet WOL"
}
```

Install: `npm install`

---

## 📝 Catatan Penting

- ⚠️ **Jangan format file `.ejs` dengan auto-formatter HTML** (Prettier/Beautify di VS Code), karena akan merusak sintaks EJS tag `<% %>`. Set file `.ejs` ke mode **Plain Text** di VS Code.
- UltraVNC Server harus sudah aktif di komputer target agar Remote Desktop berhasil terhubung.
- WOL hanya bekerja jika komputer target sudah dikonfigurasi untuk menerima Magic Packet (aktifkan di BIOS/UEFI dan Network Adapter).
