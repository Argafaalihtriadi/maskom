# Project Plan Pengembangan MaskomApp

Dokumen ini merangkum rencana pengembangan lanjutan untuk web aplikasi manajemen infrastruktur IT **MaskomApp**. Anda dapat menggunakan dokumen ini sebagai acuan roadmap pengerjaan fitur baru.

---

## 🗺️ Peta Jalan & Prioritas Fitur

### 🔴 Prioritas Tinggi (Paling Berdampak / Core)
Fitur-fitur yang krusial untuk membuat data MaskomApp menjadi dinamis dan informatif.

#### 1. Deteksi Status Perangkat Real-time (Ping/Status Check)
*   **Tujuan:** Mengganti status "Online" yang saat ini di-hardcode agar menunjukkan status jaringan komputer yang sebenarnya.
*   **Rencana Teknis:**
    *   Pasang library `ping` (atau menggunakan native `ping` command via `child_process`).
    *   Buat API endpoint `/api/devices/ping` atau `/api/devices/:filename/ping`.
    *   Pada frontend, buat JavaScript worker/interval untuk melakukan ping periodik ke IP Address perangkat secara asinkron agar tidak membebani pemuatan halaman pertama kali.
*   **Dampak:** Dashboard dan tabel inventaris akan menampilkan status nyata (Online/Offline) dan latensi (ms).

#### 2. Audit Log & Riwayat Aktivitas Real-time
*   **Tujuan:** Mengaktifkan panel "Feed Aktivitas" di Dashboard dengan data riwayat nyata, bukan dummy data.
*   **Rencana Teknis:**
    *   Buat file log internal di server (misal: `data_komputer/audit_log.json`).
    *   Buat middleware/utilitas logger di backend untuk merekam aktivitas penting:
        *   "Sync FTP berhasil/gagal (jumlah file)"
        *   "Perangkat [Hostname] berhasil ditambahkan/diubah/dihapus"
        *   "Mengirim paket WOL ke [MAC Address]"
        *   "Membuka Remote Desktop ke [IP Address]"
    *   Buat API `/api/logs` untuk dibaca oleh Dashboard secara berkala.

---

### 🟡 Prioritas Menengah (Peningkatan UX & Pelaporan)
Peningkatan fungsionalitas visual dan kemudahan penggunaan aplikasi sehari-hari.

#### 3. ✅ Ekspor Laporan PDF Lengkap (Dashboard & Aset) — **SELESAI**
*   **Implementasi:**
    *   CSS `@media print` komprehensif ditambahkan ke `partials/header.ejs` (berlaku global).
    *   Layout cetak: ukuran A4 landscape, header laporan formal (nama perusahaan + tanggal), tabel dengan border, sembunyikan nav/sidebar/tombol aksi.
    *   Tombol **"Ekspor PDF"** di Dashboard → memanggil `window.print()`.
    *   Tombol **"Ekspor PDF"** di Detail Aset → memanggil `printAsset()` dengan tanggal inject otomatis.

#### 4. ✅ Filter & Pencarian Lanjutan (Multi-filter) — **SELESAI**
*   **Implementasi:**
    *   Dropdown **Departemen** dan **OS**: diisi secara dinamis dari data JSON aktual via EJS (tidak hardcoded lagi).
    *   Dropdown **Status**: tetap manual (Aktif/Siaga/Tidak Aktif) karena status bersifat statis.
    *   Fungsi `applyFilters()`: filter kombinasi antara keyword search + ketiga dropdown bekerja secara real-time.
    *   **Filter Badge**: muncul ketika filter aktif, menampilkan ringkasan filter dan jumlah perangkat yang ditemukan.
    *   Tombol **"Bersihkan Filter"** berfungsi mereset semua filter sekaligus.

#### 5. Topologi Jaringan Interaktif yang Dinamis
*   **Tujuan:** Mengganti visualisasi topologi statis di dashboard dengan grafik dinamis yang menggambarkan hubungan komputer ke switch/router.
*   **Rencana Teknis:**
    *   Gunakan library visualisasi javascript ringan di frontend seperti `vis-network` or `Cytoscape.js`.
    *   Petakan IP Address gateway utama (Router) sebagai pusat node, lalu hubungkan komputer-komputer (berdasarkan subnet atau departemen) sebagai node cabang.

---

### 🟢 Prioritas Rendah (Keamanan & Otomasi Tingkat Lanjut)
Cocok untuk skala lingkungan production yang lebih besar.

#### 6. Autentikasi Pengguna & Hak Akses
*   **Tujuan:** Mengamankan akses halaman administrasi agar tidak sembarang orang di jaringan lokal bisa menghapus aset atau melakukan remote desktop.
*   **Rencana Teknis:**
    *   Implementasikan sistem login sederhana menggunakan session (`express-session`).
    *   Buat database pengguna sederhana (bisa file JSON aman atau SQLite) menggunakan enkripsi password `bcrypt`.
    *   Bagi hak akses menjadi `Admin` (akses penuh: tambah/edit/hapus/remote) dan `Viewer` (hanya melihat spesifikasi komputer).

#### 7. Eksekusi Scan Otomatis (Integrasi python `main.py`)
*   **Tujuan:** Memperbarui data spesifikasi hardware komputer dengan menjalankan script scanner `main.py` langsung dari web.
*   **Rencana Teknis:**
    *   Buat trigger di backend untuk mengeksekusi python script menggunakan `child_process.spawn`.
    *   Mendistribusikan script scan (agent) ke PC klien secara otomatis (jika ada infrastruktur pendukung) atau melakukan scan jarak jauh via WMI/WinRM jika kredensial diizinkan.

---

## 🛠️ Langkah Menjalankan Project Plan Selanjutnya

Jika Anda ingin melanjutkan pengerjaan fitur-fitur di atas, langkah paling terdekat yang direkomendasikan adalah **mengimplementasikan Fitur #1 (Ping Real-time)** terlebih dahulu, karena infrastrukturnya sudah ada (data IP Address setiap komputer telah tersimpan di file JSON).

Anda dapat meminta saya membuatkan fitur tersebut kapan saja dengan memberikan instruksi. Dokumen rencana ini juga disimpan di file internal Anda untuk dibaca kembali sewaktu-waktu.
