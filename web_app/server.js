// Load environment variables dari .env SEBELUM apapun
require('dotenv').config();

const express = require('express');
const path = require('path');
const fs = require('fs');
const wol = require('wake_on_lan');
const cors = require('cors');
const { spawn } = require('child_process');
const ftp = require('basic-ftp');
const cron = require('node-cron');
const session = require('express-session');
const axios = require('axios');
const ping = require('ping');
const { WebSocketServer } = require('ws');
const http = require('http');
const net = require('net');

const app = express();
const PORT = process.env.PORT || 3000;

// Set EJS as templating engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Middleware
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors());

// Konfigurasi Session
app.use(session({
    secret: process.env.SESSION_SECRET || 'maskomapp-secret-key-12345',
    resave: false,
    saveUninitialized: false,
    cookie: {
        secure: false, // Set true jika menggunakan HTTPS
        maxAge: 24 * 60 * 60 * 1000 // Berlaku 1 hari
    }
}));

// Middleware Proteksi Halaman
function requireAuth(req, res, next) {
    if (req.session && req.session.user) {
        return next();
    }
    res.redirect('/login');
}

// Teruskan data session ke semua views
app.use((req, res, next) => {
    res.locals.userSession = req.session.user || null;
    next();
});


// Helpers for data reading
const dataDir = path.join(__dirname, 'data_komputer');
if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
}

function getDevices() {
    let devices = [];
    try {
        const files = fs.readdirSync(dataDir);
        files.forEach(file => {
            if (file.endsWith('.json')) {
                const filePath = path.join(dataDir, file);
                const fileContent = fs.readFileSync(filePath, 'utf8');
                try {
                    const data = JSON.parse(fileContent);
                    devices.push({
                        filename: file,
                        data: data
                    });
                } catch (e) {
                    console.error('Error parsing JSON:', file);
                }
            }
        });
    } catch (e) {
        console.error('Error reading data directory', e);
    }
    return devices;
}

// =============================================
// FTP SYNC — Konfigurasi & State
// =============================================
const FTP_CONFIG = {
    host: process.env.FTP_HOST || '192.168.33.181',
    port: parseInt(process.env.FTP_PORT) || 21,
    user: process.env.FTP_USER || '',
    password: process.env.FTP_PASS || '',
    path: process.env.FTP_PATH || '/maskom',
    secure: false // Ubah ke true jika server FTP mendukung FTPS
};

const FTP_COOLDOWN_MS = (parseInt(process.env.FTP_SYNC_COOLDOWN) || 30) * 1000;

// State sinkronisasi (disimpan di memori, direset saat server restart)
let syncState = {
    isRunning: false,
    lastSyncAt: null,
    lastSyncStatus: null,   // 'success' | 'error' | null
    lastSyncMessage: '',
    lastSyncCount: 0,
    lastSyncErrors: [],
    nextAutoSync: null,
};

/**
 * Sanitasi nama file: hanya izinkan karakter aman, blokir path traversal
 * @param {string} filename 
 * @returns {string|null} nama file yang bersih, atau null jika berbahaya
 */
function sanitizeFilename(filename) {
    // Hanya izinkan huruf, angka, titik, underscore, strip
    const safe = path.basename(filename);
    if (/[^a-zA-Z0-9._\-]/.test(safe)) return null;
    if (!safe.endsWith('.json')) return null;
    if (safe.startsWith('.')) return null;
    return safe;
}

/**
 * Fungsi utama: sinkronisasi file JSON dari FTP ke data_komputer/
 * Mengembalikan objek hasil sinkronisasi.
 */
async function syncFromFTP() {
    if (syncState.isRunning) {
        return { success: false, message: 'Sinkronisasi sedang berjalan, harap tunggu.' };
    }

    syncState.isRunning = true;
    const client = new ftp.Client();
    client.ftp.verbose = false; // set true untuk debug FTP detail

    const downloaded = [];
    const errors = [];

    try {
        console.log(`[FTP SYNC] Menghubungi ${FTP_CONFIG.host}:${FTP_CONFIG.port}...`);

        await client.access({
            host: FTP_CONFIG.host,
            port: FTP_CONFIG.port,
            user: FTP_CONFIG.user,
            password: FTP_CONFIG.password,
            secure: FTP_CONFIG.secure,
        });

        console.log(`[FTP SYNC] Terhubung. Membuka direktori: ${FTP_CONFIG.path}`);
        await client.cd(FTP_CONFIG.path);

        // Ambil daftar file di direktori
        const fileList = await client.list();
        const jsonFiles = fileList.filter(f => f.type === ftp.FileType.File && f.name.endsWith('.json'));

        console.log(`[FTP SYNC] Ditemukan ${jsonFiles.length} file JSON.`);

        for (const remoteFile of jsonFiles) {
            const cleanName = sanitizeFilename(remoteFile.name);
            if (!cleanName) {
                console.warn(`[FTP SYNC] Nama file dilewati (tidak aman): ${remoteFile.name}`);
                errors.push(`File dilewati (nama tidak aman): ${remoteFile.name}`);
                continue;
            }

            const localPath = path.join(dataDir, cleanName);
            const tempLocalPath = path.join(dataDir, `_temp_${cleanName}`);

            try {
                // Download file ke file temporary terlebih dahulu
                await client.downloadTo(tempLocalPath, remoteFile.name);

                // Baca & validasi JSON dari FTP
                const ftpContentRaw = fs.readFileSync(tempLocalPath, 'utf8');
                let ftpData = JSON.parse(ftpContentRaw);

                // Jika file lokal sudah ada, gabungkan field kustom yang sudah diinput manual agar tidak hilang
                if (fs.existsSync(localPath)) {
                    try {
                        const localContentRaw = fs.readFileSync(localPath, 'utf8');
                        const localData = JSON.parse(localContentRaw);

                        // Pertahankan data manual lokal jika ada
                        if (localData["DAT"] !== undefined) ftpData["DAT"] = localData["DAT"];
                        if (localData["Serial Number"] !== undefined) ftpData["Serial Number"] = localData["Serial Number"];
                        if (localData["Departemen"] !== undefined) ftpData["Departemen"] = localData["Departemen"];
                        if (localData["Pengguna"] !== undefined) ftpData["Pengguna"] = localData["Pengguna"];
                    } catch (e) {
                        console.warn(`[FTP SYNC] Gagal membaca data lokal lama untuk merge: ${cleanName}. Menggunakan data baru.`);
                    }
                }

                // Tulis hasil gabungan (merge) ke localPath utama
                fs.writeFileSync(localPath, JSON.stringify(ftpData, null, 4), 'utf8');
                
                // Hapus file temporary
                if (fs.existsSync(tempLocalPath)) {
                    fs.unlinkSync(tempLocalPath);
                }

                downloaded.push(cleanName);
                console.log(`[FTP SYNC] ✓ ${cleanName} (berhasil dimerge)`);
            } catch (fileErr) {
                errors.push(`Gagal download/merge ${remoteFile.name}: ${fileErr.message}`);
                console.error(`[FTP SYNC] ✗ ${remoteFile.name}: ${fileErr.message}`);

                // Bersihkan file temp jika tersisa
                try { if (fs.existsSync(tempLocalPath)) fs.unlinkSync(tempLocalPath); } catch (_) {}
            }
        }

        const message = `Berhasil: ${downloaded.length} file diperbarui` +
            (errors.length > 0 ? `, ${errors.length} gagal.` : '.');

        syncState.lastSyncAt = new Date().toISOString();
        syncState.lastSyncStatus = errors.length === jsonFiles.length && jsonFiles.length > 0 ? 'error' : 'success';
        syncState.lastSyncMessage = message;
        syncState.lastSyncCount = downloaded.length;
        syncState.lastSyncErrors = errors;

        console.log(`[FTP SYNC] Selesai. ${message}`);
        return { success: true, message, downloaded, errors };

    } catch (err) {
        const message = `Gagal terhubung ke FTP: ${err.message}`;
        console.error(`[FTP SYNC] ERROR: ${message}`);

        syncState.lastSyncAt = new Date().toISOString();
        syncState.lastSyncStatus = 'error';
        syncState.lastSyncMessage = message;
        syncState.lastSyncCount = 0;
        syncState.lastSyncErrors = [message];

        return { success: false, message, downloaded, errors: [message] };
    } finally {
        client.close();
        syncState.isRunning = false;
    }
}

// =============================================
// API Endpoint: Manual Sync (dengan cooldown)
// =============================================
let lastManualSyncTime = 0;

app.post('/api/ftp/sync', requireAuth, async (req, res) => {
    // Blokir jika sedang berjalan
    if (syncState.isRunning) {
        return res.status(429).json({
            success: false,
            message: 'Sinkronisasi sedang berjalan. Harap tunggu sebentar.'
        });
    }

    // Cooldown: cegah spam klik tombol
    const now = Date.now();
    const elapsed = now - lastManualSyncTime;
    if (elapsed < FTP_COOLDOWN_MS) {
        const sisaDetik = Math.ceil((FTP_COOLDOWN_MS - elapsed) / 1000);
        return res.status(429).json({
            success: false,
            message: `Terlalu cepat. Tunggu ${sisaDetik} detik lagi sebelum sync berikutnya.`
        });
    }

    lastManualSyncTime = now;

    try {
        const result = await syncFromFTP();
        res.json(result);
    } catch (err) {
        res.status(500).json({ success: false, message: 'Error tidak terduga: ' + err.message });
    }
});

// =============================================
// API Endpoint: Status Sync Terakhir
// =============================================
app.get('/api/ftp/status', requireAuth, (req, res) => {
    const cooldownSisa = Math.max(0, Math.ceil((FTP_COOLDOWN_MS - (Date.now() - lastManualSyncTime)) / 1000));

    res.json({
        ...syncState,
        cooldownSisa,
        ftpHost: FTP_CONFIG.host,
        ftpPath: FTP_CONFIG.path,
        // Jangan kirim password ke frontend!
        ftpConfigured: !!(FTP_CONFIG.user && FTP_CONFIG.password),
        totalDevices: getDevices().length,
    });
});

// =============================================
// Auto Sync — node-cron
// =============================================
const CRON_SCHEDULE = process.env.FTP_SYNC_CRON;

if (CRON_SCHEDULE && cron.validate(CRON_SCHEDULE)) {
    console.log(`[FTP SYNC] Auto-sync aktif dengan jadwal: "${CRON_SCHEDULE}"`);
    const cronJob = cron.schedule(CRON_SCHEDULE, async () => {
        console.log(`[FTP SYNC] Memulai sinkronisasi otomatis...`);
        await syncFromFTP();
    });
    // Hitung jadwal berikutnya (simpel, hanya tampilkan jadwal saja)
    syncState.nextAutoSync = CRON_SCHEDULE;
} else if (CRON_SCHEDULE) {
    console.warn(`[FTP SYNC] FTP_SYNC_CRON tidak valid: "${CRON_SCHEDULE}". Auto-sync dinonaktifkan.`);
} else {
    console.log(`[FTP SYNC] Auto-sync tidak dikonfigurasi (FTP_SYNC_CRON kosong).`);
}

// =============================================
// Routes - Autentikasi
// =============================================
app.get('/login', (req, res) => {
    if (req.session.user) {
        return res.redirect('/');
    }
    res.render('login', { error: null });
});

app.post('/login', async (req, res) => {
    const { username, password } = req.body;

    // Hardcoded Admin Bypass
    if (username === 'maskom' && password === '210117') {
        req.session.user = {
            id: 'admin_001',
            username: 'maskom',
            email: 'admin@maskom.local',
            deptName: 'System Admin',
            divName: 'IT',
            groupName: 'Super Admin',
            token: 'local-admin-token-xyz'
        };
        return res.redirect('/');
    }

    try {
        // Panggil API External Login
        const response = await axios.post('http://192.168.33.146:8000/api-ims/auth/users/login', {
            username,
            password
        }, {
            timeout: 5000 // batas timeout 5 detik
        });

        if (response.data && response.data.success) {
            // Simpan data login ke session
            req.session.user = {
                id: response.data.user.id,
                username: response.data.user.username,
                email: response.data.user.email,
                deptName: response.data.user.deptName,
                divName: response.data.user.divName,
                groupName: response.data.user.groupName,
                token: response.data.token
            };
            return res.redirect('/');
        } else {
            return res.render('login', { error: 'Username atau password salah.' });
        }
    } catch (err) {
        console.error('Login Error:', err.message);
        let errorMsg = 'Gagal menghubungi server autentikasi.';
        if (err.response && err.response.data && err.response.data.message) {
            errorMsg = err.response.data.message;
        } else if (err.response && err.response.status === 401) {
            errorMsg = 'Username atau password salah.';
        }
        res.render('login', { error: errorMsg });
    }
});

app.get('/logout', (req, res) => {
    req.session.destroy((err) => {
        if (err) console.error('Gagal destroy session:', err);
        res.redirect('/login');
    });
});

// =============================================
// Routes - Views
// =============================================
app.get('/', requireAuth, (req, res) => {
    const devices = getDevices();
    const totalDevices = devices.length;
    res.render('dashboard', { totalDevices, devices, syncState });
});

app.get('/inventory', requireAuth, (req, res) => {
    const devices = getDevices();
    res.render('inventory', { devices, syncState });
});

app.get('/wol', requireAuth, (req, res) => {
    const devices = getDevices();
    res.render('wol', { devices });
});

app.get('/monitoring', requireAuth, (req, res) => {
    const devices = getDevices();
    res.render('monitoring', { devices, syncState });
});

app.get('/asset/:id', requireAuth, (req, res) => {
    const devices = getDevices();
    const id = req.params.id;
    const device = devices.find(d => d.filename === `${id}.json` || d.filename === id);
    if (!device) {
        return res.status(404).send('Asset not found');
    }
    res.render('asset', { device });
});

// =============================================
// Routes - API Perangkat (CRUD)
// =============================================
app.get('/api/devices', requireAuth, (req, res) => {
    res.json(getDevices());
});

app.post('/api/devices', requireAuth, (req, res) => {
    const { hostname, ip, mac, os } = req.body;
    if (!hostname) {
        return res.status(400).json({ success: false, message: 'Hostname is required' });
    }

    const newDevice = {
        "Sistem Operasi": os || "Unknown",
        "Waktu Scan (Lokal)": new Date().toISOString(),
        "User Session (Whoami)": {
            "Username": "Manual Entry",
            "Hostname": hostname
        },
        "LAN/Network Card": [
            {
                "Description": "Manual Entry Adapter",
                "Physical Address (MAC)": mac || "00:00:00:00:00:00",
                "Status Hardware": "Connected",
                "IPv4 Address": ip || "0.0.0.0",
                "Subnet Mask": "255.255.255.0"
            }
        ]
    };

    const filename = `${hostname.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.json`;
    const filePath = path.join(dataDir, filename);

    fs.writeFile(filePath, JSON.stringify(newDevice, null, 4), (err) => {
        if (err) {
            console.error('Error saving device', err);
            return res.status(500).json({ success: false, message: 'Failed to save device' });
        }
        res.json({ success: true, message: 'Device created successfully' });
    });
});

app.put('/api/devices/:filename', requireAuth, (req, res) => {
    const filename = req.params.filename;
    const filePath = path.join(dataDir, filename);
    const { hostname, ip, mac, os, dat, serial_number, departement, pengguna } = req.body;

    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ success: false, message: 'Device not found' });
    }

    fs.readFile(filePath, 'utf8', (err, data) => {
        if (err) return res.status(500).json({ success: false, message: 'Error reading device' });

        let deviceData;
        try {
            deviceData = JSON.parse(data);
        } catch (e) {
            return res.status(500).json({ success: false, message: 'Invalid JSON format in file' });
        }

        if (os) deviceData["Sistem Operasi"] = os;
        if (dat !== undefined) deviceData["DAT"] = dat;
        if (serial_number !== undefined) deviceData["Serial Number"] = serial_number;
        if (departement !== undefined) deviceData["Departemen"] = departement;
        if (pengguna !== undefined) deviceData["Pengguna"] = pengguna;

        if (hostname) {
            if (!deviceData["User Session (Whoami)"]) deviceData["User Session (Whoami)"] = {};
            deviceData["User Session (Whoami)"]["Hostname"] = hostname;
        }
        if (ip || mac) {
            if (!deviceData["LAN/Network Card"] || deviceData["LAN/Network Card"].length === 0) {
                deviceData["LAN/Network Card"] = [{}];
            }
            if (ip) deviceData["LAN/Network Card"][0]["IPv4 Address"] = ip;
            if (mac) deviceData["LAN/Network Card"][0]["Physical Address (MAC)"] = mac;
            deviceData["LAN/Network Card"][0]["Status Hardware"] = "Connected";
        }

        fs.writeFile(filePath, JSON.stringify(deviceData, null, 4), (err) => {
            if (err) return res.status(500).json({ success: false, message: 'Failed to update device' });
            res.json({ success: true, message: 'Device updated successfully' });
        });
    });
});

// =============================================
// EKSPOR LAPORAN INVENTARIS LENGKAP
// =============================================

/**
 * Helper: Ekstrak data perangkat menjadi flat object untuk CSV/PDF
 */
function flattenDevice(device) {
    const d = device.data;
    const userInfo = d["User Session (Whoami)"] || {};
    const cpu = d["CPU"] || {};
    const mb = d["Mainboard"] || {};
    const memGen = (d["Memory & SPD"] && d["Memory & SPD"]["General"]) ? d["Memory & SPD"]["General"] : {};
    const graphics = (d["Graphics"] && d["Graphics"].length > 0) ? d["Graphics"][0] : {};
    const storageList = d["Penyimpanan"] || [];
    const lanCards = d["LAN/Network Card"] || [];

    // LAN utama: cari yang Connected, fallback ke index 0
    const mainLan = lanCards.find(c => c["Status Hardware"] && c["Status Hardware"].includes("Connected")) || lanCards[0] || {};
    // LAN kedua (jika ada)
    const secondLan = lanCards.length > 1 ? lanCards[1] : {};

    // Storage: gabungkan semua drive
    const storageStr = storageList.map(s =>
        `${s["Model/Nama Drive"] || ''} (${s["Tipe Interfasi"] || s["Tipe"] || ''} - ${s["Kapasitas"] || ''})`
    ).join(' | ');

    return {
        "Filename": device.filename,
        "Hostname": userInfo.Hostname || '-',
        "Username": userInfo.Username || '-',
        "Full Identity": userInfo["Full Identity"] || '-',
        "NO DAT": d["DAT"] || '-',
        "Serial Number": d["Serial Number"] || '-',
        "Departemen": d["Departemen"] || '-',
        "Pengguna": d["Pengguna"] || '-',
        "Sistem Operasi": d["Sistem Operasi"] || '-',
        // CPU
        "CPU": cpu.Name || '-',
        "CPU Specification": cpu.Specification || '-',
        "CPU Core Speed (MHz)": cpu["Core Speed"] || '-',
        "CPU Cores": cpu.Cores || '-',
        "CPU Threads": cpu.Threads || '-',
        "CPU Code Name": cpu["Code Name"] || '-',
        "CPU Package": cpu.Package || '-',
        // Mainboard
        "Mainboard Manufacturer": mb["Motherboard Manufacturer"] || '-',
        "Mainboard Model": mb.Model || '-',
        "BIOS Vendor": mb["BIOS Vendor"] || '-',
        "BIOS Version": mb["BIOS Version"] || '-',
        "BIOS Date": mb["BIOS Date"] || '-',
        // RAM
        "RAM Total": memGen["Total Size"] || '-',
        "RAM Type": memGen.Type || '-',
        "RAM Channel": memGen["Channel #"] || '-',
        "RAM Frequency": memGen["DRAM Frequency"] || '-',
        // GPU
        "GPU": graphics["Name/Model"] || '-',
        "GPU VRAM": graphics["Dedicated VRAM"] || '-',
        "GPU Driver": graphics["Driver Version"] || '-',
        // Storage (semua drive)
        "Penyimpanan": storageStr || '-',
        // LAN Utama
        "IP Address (LAN1)": mainLan["IPv4 Address"] || '-',
        "MAC Address (LAN1)": mainLan["Physical Address (MAC)"] || '-',
        "Subnet Mask (LAN1)": mainLan["Subnet Mask"] || '-',
        "Default Gateway (LAN1)": mainLan["Default Gateway"] || '-',
        "LAN1 Adapter": mainLan["Description (Nama Perangkat)"] || '-',
        // LAN Kedua (opsional)
        "IP Address (LAN2)": secondLan["IPv4 Address"] || '-',
        "MAC Address (LAN2)": secondLan["Physical Address (MAC)"] || '-',
        "LAN2 Adapter": secondLan["Description (Nama Perangkat)"] || '-',
    };
}

// GET /api/export/inventory.csv — Download CSV lengkap semua perangkat
app.get('/api/export/inventory.csv', requireAuth, (req, res) => {
    const devices = getDevices();
    if (devices.length === 0) {
        return res.status(404).json({ success: false, message: 'Tidak ada data perangkat.' });
    }

    const rows = devices.map(flattenDevice);
    const headers = Object.keys(rows[0]);

    // Fungsi escape CSV (handle koma dan quote di dalam nilai)
    function escapeCSV(val) {
        const str = String(val === null || val === undefined ? '' : val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    }

    const csvLines = [
        headers.map(escapeCSV).join(','),
        ...rows.map(row => headers.map(h => escapeCSV(row[h])).join(','))
    ];

    const timestamp = new Date().toISOString().slice(0, 10);
    const filename = `inventaris_maskom_${timestamp}.csv`;

    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    // BOM UTF-8 agar Excel bisa membaca karakter Indonesia dengan benar
    res.send('\uFEFF' + csvLines.join('\n'));
});

// GET /export — Halaman Preview & Ekspor Laporan Inventaris
app.get('/export', requireAuth, (req, res) => {
    const devices = getDevices();
    const rows = devices.map(flattenDevice);
    const timestamp = new Date().toLocaleString('id-ID');
    res.render('export', { rows, totalDevices: devices.length, timestamp, syncState });
});

app.delete('/api/devices/:filename', requireAuth, (req, res) => {
    const filename = req.params.filename;
    const filePath = path.join(dataDir, filename);

    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ success: false, message: 'Device not found' });
    }

    fs.unlink(filePath, (err) => {
        if (err) return res.status(500).json({ success: false, message: 'Failed to delete device' });
        res.json({ success: true, message: 'Device deleted successfully' });
    });
});


// =============================================
// API: Wake-on-LAN
// =============================================
app.post('/api/wol', requireAuth, (req, res) => {
    const { macs } = req.body;

    if (!macs || !Array.isArray(macs) || macs.length === 0) {
        return res.status(400).json({ success: false, message: 'MAC Addresses array is required' });
    }

    let sentCount = 0;
    let errors = [];

    macs.forEach(mac => {
        wol.wake(mac, (error) => {
            if (error) {
                console.error(`WOL Error for ${mac}:`, error);
                errors.push(mac);
            } else {
                console.log(`WOL packet sent to ${mac}`);
            }

            sentCount++;
            if (sentCount === macs.length) {
                if (errors.length === macs.length) {
                    return res.status(500).json({ success: false, message: 'Failed to send all WOL packets' });
                }
                return res.json({ success: true, message: `Magic packets sent. Failed: ${errors.length}` });
            }
        });
    });
});

// =============================================
// API: Real-time Ping
// =============================================
app.get('/api/ping', requireAuth, async (req, res) => {
    const { ip } = req.query;
    
    if (!ip) {
        return res.status(400).json({ success: false, message: 'IP address is required' });
    }

    try {
        const result = await ping.promise.probe(ip, {
            timeout: 2, // timeout 2 seconds
        });
        res.json({
            success: true,
            ip: result.host,
            alive: result.alive,
            time: result.time
        });
    } catch (err) {
        res.status(500).json({ success: false, message: 'Ping failed: ' + err.message });
    }
});

// =============================================
// Remote Desktop: Launch UltraVNC Viewer
// =============================================
const VNC_VIEWER_PATH = process.env.VNC_PATH || 'C:\\laragon\\www\\MaskomApp\\web_app\\vnc\\x64\\vncviewer.exe';

app.post('/api/remote/vnc', requireAuth, (req, res) => {
    const { ip } = req.body;
    if (!ip || ip === 'Unknown') {
        return res.status(400).json({ success: false, message: 'Alamat IP tidak valid.' });
    }

    try {
        const proc = spawn(VNC_VIEWER_PATH, [ip + '::5900'], {
            detached: true,
            stdio: 'ignore',
            windowsHide: false
        });
        proc.unref();
        res.json({ success: true, message: 'UltraVNC Viewer diluncurkan untuk ' + ip });
    } catch (err) {
        res.status(500).json({ success: false, message: 'Gagal meluncurkan VNC: ' + err.message });
    }
});

// =============================================
// Remote Shutdown / Restart via WMI
// =============================================
app.post('/api/remote/shutdown', requireAuth, (req, res) => {
    const ips = req.body.ips || [req.body.ip];
    const action = req.body.action || 'shutdown';
    const validIps = ips.filter(ip => ip && ip !== 'Unknown');
    if (!validIps.length) return res.status(400).json({ success: false, message: 'Alamat IP tidak valid.' });

    const flag = action === 'restart' ? '/r' : '/s';
    const label = action === 'restart' ? 'Restart' : 'Shutdown';
    const results = { success: true, message: '', failed: [] };
    let done = 0;
    let responded = false;

    validIps.forEach(ip => {
        const cmd = `shutdown ${flag} /m \\\\${ip} /t 15 /c "MaskomApp: ${label}" /f`;
        const proc = spawn('powershell.exe', ['-NoProfile', '-Command', cmd], { windowsHide: true });
        proc.on('close', (code) => {
            if (code !== 0) results.failed.push(ip);
            done++;
            if (done >= validIps.length && !responded) respond();
        });
        proc.on('error', () => { results.failed.push(ip); done++; if (done >= validIps.length && !responded) respond(); });
    });

    function respond() {
        if (responded) return;
        responded = true;
        results.message = `${label} dikirim ke ${validIps.length - results.failed.length} perangkat` + (results.failed.length ? `, ${results.failed.length} gagal.` : '.');
        if (results.failed.length === validIps.length) return res.status(500).json(results);
        res.json(results);
    }
});

// =============================================
// Remote Control: Lock, Message, Run Program
// =============================================

function execPowerShell(ip, cmd, label, res) {
    const fullCmd = `powershell.exe -Command "${cmd}"`;
    const proc = spawn('powershell.exe', ['-Command', cmd], { windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => {
        if (code === 0) res.json({ success: true, message: `${label} berhasil dikirim ke ${ip}.` });
        else res.status(500).json({ success: false, message: `${label} gagal: ${stderr.trim() || 'exit code ' + code}` });
    });
    proc.on('error', (e) => res.status(500).json({ success: false, message: `Gagal: ${e.message}` }));
}

app.post('/api/remote/lock', requireAuth, (req, res) => {
    const { ips } = req.body;
    if (!ips || !ips.length) return res.status(400).json({ success: false, message: 'Pilih setidaknya satu perangkat.' });
    const results = { success: true, message: '', failed: [] };
    let done = 0;
    let responded = false;
    ips.forEach(ip => {
        if (!ip || ip === 'Unknown') { done++; if (done >= ips.length && !responded) respond(); return; }
        const proc = spawn('powershell.exe', ['-NoProfile', '-Command', `shutdown /l /m \\\\${ip} /f`], { windowsHide: true });
        proc.on('close', (code) => {
            if (code !== 0) results.failed.push(ip);
            done++;
            if (done >= ips.length && !responded) respond();
        });
        proc.on('error', () => { results.failed.push(ip); done++; if (done >= ips.length && !responded) respond(); });
    });
    function respond() {
        if (responded) return;
        responded = true;
        results.message = `Lock dikirim ke ${ips.length - results.failed.length} perangkat` + (results.failed.length ? `, ${results.failed.length} gagal.` : '.');
        if (results.failed.length === ips.length) return res.status(500).json(results);
        res.json(results);
    }
});

app.post('/api/remote/message', requireAuth, (req, res) => {
    try {
        const { ips, message, title } = req.body;
        if (!ips || !ips.length) return res.status(400).json({ success: false, message: 'Pilih setidaknya satu perangkat.' });
        const msg = (message || 'Pesan dari Administrator').replace(/"/g, '\\"');
        const ttl = (title || 'MaskomApp').replace(/"/g, '\\"');
        const results = { success: true, message: '', failed: [] };
        let done = 0;
        let responded = false;
        ips.forEach(ip => {
            if (!ip || ip === 'Unknown') { done++; if (done >= ips.length && !responded) respond(); return; }
            const psCmd = `Invoke-WmiMethod -ComputerName ${ip} -Class Win32_Process -Name Create -ArgumentList 'cmd.exe /c msg * /time:30 "${ttl}: ${msg}"'`;
            const proc = spawn('powershell.exe', ['-NoProfile', '-Command', psCmd], { windowsHide: true });
            let errData = '';
            proc.stderr.on('data', (d) => { errData += d.toString(); });
            proc.on('close', (code) => {
                if (code !== 0) results.failed.push({ ip, error: errData.trim() || 'exit code ' + code });
                done++;
                if (done >= ips.length && !responded) respond();
            });
            proc.on('error', (e) => { results.failed.push({ ip, error: e.message }); done++; if (done >= ips.length && !responded) respond(); });
        });
        if (!ips.length) respond();
        function respond() {
            if (responded) return;
            responded = true;
            results.message = `Pesan dikirim ke ${ips.length - results.failed.length} perangkat` + (results.failed.length ? `, ${results.failed.length} gagal.` : '.');
            if (results.failed.length === ips.length) return res.status(500).json(results);
            res.json(results);
        }
    } catch (e) {
        console.error('[/api/remote/message] Error:', e);
        res.status(500).json({ success: false, message: e.message });
    }
});

app.post('/api/remote/run', requireAuth, (req, res) => {
    const { ips, command } = req.body;
    if (!ips || !ips.length) return res.status(400).json({ success: false, message: 'Pilih setidaknya satu perangkat.' });
    if (!command) return res.status(400).json({ success: false, message: 'Perintah tidak boleh kosong.' });
    const results = { success: true, message: '', failed: [] };
    let done = 0;
    ips.forEach(ip => {
        if (!ip || ip === 'Unknown') { done++; if (++done === ips.length) respond(); return; }
        const cmd = `Invoke-WmiMethod -ComputerName ${ip} -Class Win32_Process -Name Create -ArgumentList '${command.replace(/'/g, "''")}'`;
        const proc = spawn('powershell.exe', ['-Command', cmd], { windowsHide: true });
        proc.on('close', (code) => {
            if (code !== 0) results.failed.push(ip);
            done++;
            if (done === ips.length) respond();
        });
        proc.on('error', () => { results.failed.push(ip); done++; if (done === ips.length) respond(); });
    });
    function respond() {
        results.message = `Perintah dijalankan di ${ips.length - results.failed.length} perangkat` + (results.failed.length ? `, ${results.failed.length} gagal.` : '.');
        if (results.failed.length === ips.length) return res.status(500).json(results);
        res.json(results);
    }
});

// =============================================
// File Transfer
// =============================================
const MULAI_KERJA = path.join(__dirname, 'mulai_kerja');
if (!fs.existsSync(MULAI_KERJA)) fs.mkdirSync(MULAI_KERJA, { recursive: true });

// Sediakan file upload via HTTP untuk di-download PC target (tanpa auth karena diakses oleh PC target via WMI)
app.use('/temp-upload', express.static(MULAI_KERJA));

function getServerIp() {
    try {
        const os = require('os');
        for (const [name, nets] of Object.entries(os.networkInterfaces())) {
            for (const net of nets) {
                if (net.family === 'IPv4' && !net.internal) return net.address;
            }
        }
    } catch (_) {}
    return '192.168.18.146';
}

app.post('/api/remote/upload', requireAuth, (req, res) => {
    try {
        const { ips, fileName, destFolder } = req.body;
        if (!ips || !ips.length || !fileName) return res.status(400).json({ success: false, message: 'Data tidak lengkap.' });
        const sourcePath = path.join(MULAI_KERJA, fileName);
        if (!fs.existsSync(sourcePath)) return res.status(404).json({ success: false, message: 'File tidak ditemukan di folder upload.' });
        let folder = (destFolder || 'D:\\').trim();
        const driveMatch = folder.match(/^([A-Za-z])/);
        const drive = driveMatch ? driveMatch[1] : 'D';
        folder = drive + ':\\';
        const subPath = destFolder ? destFolder.replace(/^[A-Za-z][\\\/:$]*(.*)$/i, '$1').trim() : '';
        if (subPath) folder += subPath.replace(/[\\\/]+/g, '\\').replace(/^\\+/, '') + '\\';
        const SERVER_IP = getServerIp();
        const downloadUrl = `http://${SERVER_IP}:${PORT}/temp-upload/${encodeURIComponent(fileName)}`;
        const results = { success: true, message: '', failed: [] };
        let done = 0;
        let responded = false;
        ips.forEach(ip => {
            if (!ip || ip === 'Unknown') { done++; if (done >= ips.length && !responded) respond(); return; }
            const destPath = folder + fileName;
            const remoteCmd = `powershell.exe -WindowStyle Hidden -Command "if (-not (Test-Path '${folder}')) { New-Item '${folder}' -ItemType Directory -Force }; Invoke-WebRequest -Uri '${downloadUrl}' -OutFile '${destPath}' -UseBasicParsing"`;
            const psCmd = `\$cmd = '${remoteCmd.replace(/'/g, "''")}'; Invoke-WmiMethod -ComputerName ${ip} -Class Win32_Process -Name Create -ArgumentList \$cmd; Start-Sleep -Seconds 5; Write-Output OK`;
            let errMsg = '';
            const proc = spawn('powershell.exe', ['-NoProfile', '-Command', psCmd], { windowsHide: true });
            proc.stderr.on('data', (d) => { errMsg += d.toString(); });
            proc.stdout.on('data', (d) => { if (d.toString().trim() !== 'OK') errMsg += d.toString(); });
            proc.on('close', (code) => {
                if (code !== 0) results.failed.push({ ip, error: errMsg.trim() || 'exit code ' + code });
                else results.successCount = (results.successCount || 0) + 1;
                done++;
                if (done >= ips.length && !responded) respond();
            });
            proc.on('error', (e) => { results.failed.push({ ip, error: e.message }); done++; if (done >= ips.length && !responded) respond(); });
        });
        function respond() {
            if (responded) return;
            responded = true;
            results.message = `File dikirim ke ${(results.successCount||0)} perangkat` + (results.failed.length ? `, ${results.failed.length} gagal.` : '.');
            if (results.failed.length === ips.length) return res.status(500).json(results);
            res.json(results);
        }
    } catch (e) {
        console.error('[/api/remote/upload] Error:', e);
        res.status(500).json({ success: false, message: e.message });
    }
});

const multer = require('multer');
const uploadStorage = multer({ dest: MULAI_KERJA });
app.post('/api/remote/upload-file', requireAuth, uploadStorage.single('file'), (req, res) => {
    if (!req.file) return res.status(400).json({ success: false, message: 'Pilih file terlebih dahulu.' });
    const origName = req.file.originalname;
    const destPath = path.join(MULAI_KERJA, origName);
    let finalPath = destPath;
    let counter = 1;
    const ext = path.extname(origName);
    const base = path.basename(origName, ext);
    while (fs.existsSync(finalPath)) {
        finalPath = path.join(MULAI_KERJA, `${base} (${counter})${ext}`);
        counter++;
    }
    try {
        fs.renameSync(req.file.path, finalPath);
        res.json({ success: true, message: `File ${path.basename(finalPath)} berhasil diupload.` });
    } catch (e) {
        fs.unlinkSync(req.file.path);
        res.status(500).json({ success: false, message: 'Gagal menyimpan file: ' + e.message });
    }
});

app.get('/api/remote/upload-files', requireAuth, (req, res) => {
    let files = [];
    try { files = fs.readdirSync(MULAI_KERJA).filter(f => fs.statSync(path.join(MULAI_KERJA, f)).isFile()); } catch(e) {}
    res.json({ files });
});

// =============================================
// Monitor Screenshot (via agent)
// =============================================
const SCREENSHOT_DIR = path.join(__dirname, 'public', 'screenshots');
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

app.post('/api/monitor/screenshot/:id', (req, res) => {
    const id = req.params.id.replace(/[^a-zA-Z0-9._-]/g, '');
    if (!id) return res.status(400).json({ success: false });
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
        const filePath = path.join(SCREENSHOT_DIR, id + '.jpg');
        fs.writeFileSync(filePath, Buffer.concat(chunks));
        res.json({ success: true, hostname: id });
    });
});

app.get('/api/monitor/screenshot/:id', requireAuth, (req, res) => {
    const id = req.params.id.replace(/[^a-zA-Z0-9._-]/g, '');
    let filePath = path.join(SCREENSHOT_DIR, id + '.jpg');
    if (!fs.existsSync(filePath)) {
        const devices = getDevices();
        const match = devices.find(d => {
            const info = d.data["User Session (Whoami)"] || {};
            const hostname = info.Hostname || '';
            const ipFromCard = (d.data["LAN/Network Card"] || []).find(c => c["IPv4 Address"]) || {};
            return hostname === id || d.filename.replace('.json','') === id || ipFromCard["IPv4 Address"] === id;
        });
        if (match) {
            const info = match.data["User Session (Whoami)"] || {};
            const hostname = info.Hostname || match.filename.replace('.json','');
            const altPath = path.join(SCREENSHOT_DIR, hostname + '.jpg');
            if (fs.existsSync(altPath)) filePath = altPath;
        }
    }
    if (fs.existsSync(filePath)) {
        res.setHeader('Cache-Control', 'no-cache, max-age=0');
        res.sendFile(filePath);
    } else {
        res.status(204).end();
    }
});

// =============================================
// noVNC — Web-based VNC Client
// =============================================
app.use('/novnc', express.static(path.join(__dirname, 'node_modules', '@novnc', 'novnc')));

app.get('/remote/:ip', requireAuth, (req, res) => {
    res.render('vnc', { ip: req.params.ip, password: process.env.VNC_PASSWORD || '' });
});

// =============================================
// WebSocket Agent Controller (Agen Klien Realtime)
// =============================================

// Map menyimpan koneksi WebSocket agen yang sedang aktif
// key: hostname, value: { ws, ip, connectedAt }
const agentClients = new Map();

// Broadcast status agen ke semua browser admin yang terhubung (jika ada)
function broadcastAgentList() {
    const list = Array.from(agentClients.entries()).map(([hostname, info]) => ({
        hostname,
        ip: info.ip,
        connectedAt: info.connectedAt
    }));
    // Kirim ke semua browser WebSocket (bukan agen) jika ada — opsional untuk future use
}

// =============================================
// API: Daftar Agen yang Sedang Online
// =============================================
app.get('/api/agents', requireAuth, (req, res) => {
    const list = Array.from(agentClients.entries()).map(([hostname, info]) => ({
        hostname,
        ip: info.ip,
        connectedAt: info.connectedAt
    }));
    res.json({ agents: list, total: list.length });
});

// =============================================
// API: Perintah Scan Ulang Spesifikasi (realtime)
// =============================================
app.post('/api/agent/scan/:hostname', requireAuth, (req, res) => {
    const { hostname } = req.params;
    const client = agentClients.get(hostname);

    if (!client) {
        return res.status(404).json({ success: false, message: `Agen '${hostname}' tidak online atau belum terhubung.` });
    }

    const req_id = `scan-${hostname}-${Date.now()}`;
    try {
        client.ws.send(JSON.stringify({ action: 'scan_spec', req_id }));
        res.json({ success: true, message: `Perintah scan dikirim ke ${hostname}.`, req_id });
    } catch (err) {
        agentClients.delete(hostname);
        res.status(500).json({ success: false, message: `Gagal mengirim perintah: ${err.message}` });
    }
});

// =============================================
// API: Deploy Folder Program ke PC Klien
// =============================================
app.post('/api/agent/deploy', requireAuth, (req, res) => {
    const { hostnames, zip_name, exec_path, exec_args, extract_root } = req.body;

    if (!hostnames || !Array.isArray(hostnames) || hostnames.length === 0) {
        return res.status(400).json({ success: false, message: 'Pilih setidaknya satu PC target.' });
    }
    if (!zip_name || !exec_path) {
        return res.status(400).json({ success: false, message: 'zip_name dan exec_path wajib diisi.' });
    }

    const SERVER_IP  = getServerIp();
    const fileUrl    = `http://${SERVER_IP}:${PORT}/temp-upload/${encodeURIComponent(zip_name)}`;
    const sourcePath = path.join(MULAI_KERJA, zip_name);

    if (!fs.existsSync(sourcePath)) {
        return res.status(404).json({ success: false, message: `File '${zip_name}' tidak ditemukan di folder upload server.` });
    }

    const req_id  = `deploy-${Date.now()}`;
    const results = { sent: [], offline: [], req_id };

    hostnames.forEach(hostname => {
        const client = agentClients.get(hostname);
        if (!client) {
            results.offline.push(hostname);
            return;
        }
        try {
            client.ws.send(JSON.stringify({
                action:       'deploy_folder',
                req_id,
                url:          fileUrl,
                zip_name,
                exec_path,
                exec_args:    exec_args || '',
                extract_root: extract_root || null
            }));
            results.sent.push(hostname);
        } catch (err) {
            agentClients.delete(hostname);
            results.offline.push(hostname);
        }
    });

    const msg = `Perintah deploy dikirim ke ${results.sent.length} PC` +
        (results.offline.length ? `, ${results.offline.length} PC offline/tidak terhubung.` : '.');

    res.json({
        success: results.sent.length > 0,
        message: msg,
        ...results
    });
});

// =============================================
// Routes - Halaman Deploy Folder
// =============================================
app.get('/deployer', requireAuth, (req, res) => {
    let uploadedFiles = [];
    try {
        uploadedFiles = fs.readdirSync(MULAI_KERJA)
            .filter(f => fs.statSync(path.join(MULAI_KERJA, f)).isFile());
    } catch (e) {}
    res.render('folder_deployer', { uploadedFiles, syncState });
});

// =============================================
// Start Server (HTTP + WebSocket)
// =============================================
const server = http.createServer(app);

// WebSocket — menangani dua jenis koneksi:
// 1. ws/agent/:hostname  → dari Agen Python (daemon klien)
// 2. ws/vnc/:ip          → dari noVNC browser

const AGENT_TOKEN = process.env.MASKOM_AGENT_TOKEN || 'maskom-agent-2024';

const wss = new WebSocketServer({ server });
wss.on('connection', (ws, req) => {
    const url      = new URL(req.url, `http://${req.headers.host}`);
    const pathname = url.pathname;

    // ── JALUR 1: Agen Klien Python (/ws/agent/:hostname) ──
    if (pathname.startsWith('/ws/agent/')) {
        const hostnameFromPath = decodeURIComponent(pathname.replace('/ws/agent/', '').trim());

        ws.on('message', (raw) => {
            let data;
            try { data = JSON.parse(raw.toString()); } catch { return; }

            // Pesan registrasi awal dari agen
            if (data.type === 'register') {
                const { hostname, ip, token } = data;

                if (token !== AGENT_TOKEN) {
                    console.warn(`[AGENT] Koneksi ditolak (token salah) dari ${ip}`);
                    ws.close();
                    return;
                }

                const finalHostname = hostname || hostnameFromPath;
                agentClients.set(finalHostname, { ws, ip: ip || 'Unknown', connectedAt: new Date().toISOString() });
                console.log(`[AGENT] ✅ Agen terdaftar: ${finalHostname} (${ip})`);

                ws.send(JSON.stringify({ type: 'ack', message: `Selamat datang, ${finalHostname}!` }));
                return;
            }

            // Respons dari agen setelah menjalankan perintah
            if (data.type === 'agent_response') {
                const { hostname, req_id, status, message, pid, filename } = data;
                console.log(`[AGENT] Respons dari ${hostname} | req_id=${req_id} | status=${status} | ${message || ''}`);
                // Status ini bisa dibroadcast ke browser admin jika ada sistem notifikasi
            }
        });

        ws.on('close', () => {
            // Hapus dari daftar aktif saat agen disconnect
            for (const [hostname, info] of agentClients.entries()) {
                if (info.ws === ws) {
                    agentClients.delete(hostname);
                    console.log(`[AGENT] ❌ Agen disconnect: ${hostname}`);
                    break;
                }
            }
        });

        ws.on('error', (err) => {
            console.error(`[AGENT] WebSocket error:`, err.message);
        });

        return; // Jangan lanjut ke handler VNC
    }

    // ── JALUR 2: noVNC Proxy (/ws/vnc/:ip) ──
    const ip = pathname.replace('/ws/vnc/', '').replace(/[^0-9.]/g, '');
    if (!ip) { ws.close(); return; }

    const vncPort   = 5900;
    const tcpSocket = net.createConnection(vncPort, ip);

    ws.on('message', (data) => {
        if (tcpSocket.destroyed) return;
        tcpSocket.write(Buffer.from(data));
    });

    tcpSocket.on('data', (data) => {
        if (ws.readyState === ws.OPEN) {
            ws.send(data);
        }
    });

    ws.on('close', () => tcpSocket.destroy());
    ws.on('error', () => tcpSocket.destroy());
    tcpSocket.on('error', () => { try { ws.close(); } catch(e) {} });
});


// Global error handler
app.use((err, req, res, next) => {
    console.error('[SERVER ERROR]', err.stack || err.message || err);
    if (req.xhr || req.headers.accept?.includes('json')) {
        return res.status(500).json({ success: false, message: err.message || 'Internal Server Error' });
    }
    next(err);
});

server.listen(PORT, () => {
    console.log(`✅ Server berjalan di http://localhost:${PORT}`);
    console.log(`📁 Data komputer: ${dataDir}`);
    console.log(`🌐 FTP Host: ${FTP_CONFIG.host}:${FTP_CONFIG.port}${FTP_CONFIG.path}`);
    console.log(`🔑 FTP User: ${FTP_CONFIG.user ? FTP_CONFIG.user : '(tidak dikonfigurasi)'}`);
});
