const express = require('express');
const path = require('path');
const fs = require('fs');
const wol = require('wake_on_lan');
const cors = require('cors');
const { spawn } = require('child_process');

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

// Routes - Views
app.get('/', (req, res) => {
    // For dashboard, we might want to pass some aggregate data
    const devices = getDevices();
    const totalDevices = devices.length;
    // Assuming simple metrics for now
    res.render('dashboard', { totalDevices, devices });
});

app.get('/inventory', (req, res) => {
    const devices = getDevices();
    res.render('inventory', { devices });
});

app.get('/wol', (req, res) => {
    const devices = getDevices();
    res.render('wol', { devices });
});

app.get('/asset/:id', (req, res) => {
    const devices = getDevices();
    const id = req.params.id; // Could be filename without .json
    const device = devices.find(d => d.filename === `${id}.json` || d.filename === id);
    if (!device) {
        return res.status(404).send('Asset not found');
    }
    res.render('asset', { device });
});

// Routes - API
app.get('/api/devices', (req, res) => {
    res.json(getDevices());
});

app.post('/api/devices', (req, res) => {
    const { hostname, ip, mac, os } = req.body;
    if (!hostname) {
        return res.status(400).json({ success: false, message: 'Hostname is required' });
    }

    // Create a basic structured device JSON
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

app.put('/api/devices/:filename', (req, res) => {
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

        // Update basic fields
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

app.delete('/api/devices/:filename', (req, res) => {
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

app.post('/api/wol', (req, res) => {
    const { macs } = req.body; // Changed from mac to macs array

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
// Remote Desktop: Launch UltraVNC Viewer
// =============================================
// Path UltraVNC bisa disesuaikan di sini
const VNC_VIEWER_PATH = process.env.VNC_PATH || 'C:\\laragon\\www\\MaskomApp\\web_app\\vnc\\x64\\vncviewer.exe';

app.post('/api/remote/vnc', (req, res) => {
    const { ip } = req.body;
    if (!ip || ip === 'Unknown') {
        return res.status(400).json({ success: false, message: 'Alamat IP tidak valid.' });
    }

    try {
        // UltraVNC supports: vncviewer.exe [ip]::[port]
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

app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
