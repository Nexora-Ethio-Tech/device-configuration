try {
  const path = require('path');
  const fs = require('fs');
  const backendEnv = path.join(__dirname, 'backend', '.env');
  const localEnv = path.join(__dirname, '.env');
  if (fs.existsSync(backendEnv)) {
    require('dotenv').config({ path: backendEnv });
  } else if (fs.existsSync(localEnv)) {
    require('dotenv').config({ path: localEnv });
  } else {
    require('dotenv').config();
  }
} catch (e) {
  // dotenv not installed/loaded in this execution context
}
const ZKLib = require('zkteco-js');
const axios = require('axios');

// ── Configuration ─────────────────────────────────────────────
const ZK_DEVICE_IP = process.env.ZK_DEVICE_IP || '192.168.1.201';   // Your device's IP address
const ZK_DEVICE_PORT = parseInt(process.env.ZK_DEVICE_PORT || '4370', 10);
const ZK_PASSWORD = parseInt(process.env.ZK_PASSWORD || '0', 10);                  // Change if you set a device password

const API_URL = process.env.API_URL || 'https://abdi-adama.com/api/machine/attendance';
const API_KEY = process.env.API_KEY || 'abdi_adama_zk_secure_key_2026';

// Derive SMS endpoints from API_URL
const BASE_MACHINE_URL = API_URL.replace(/\/attendance$/, '');
const SMS_PENDING_URL = `${BASE_MACHINE_URL}/sms/pending`;
const SMS_UPDATE_URL = `${BASE_MACHINE_URL}/sms/update`;

// ── State: track the last synced log index to avoid resending ──
let lastSyncedIndex = 0;

async function syncAttendance() {
  const zk = new ZKLib(ZK_DEVICE_IP, ZK_DEVICE_PORT, 10000, 4000);

  try {
    await zk.createSocket();
    console.log(`[ZK] Connected to device at ${ZK_DEVICE_IP}:${ZK_DEVICE_PORT}`);

    // Sync device time with local machine time
    try {
      await zk.setTime(new Date());
      console.log('[ZK] ✓ Device clock synchronized successfully.');
    } catch (timeErr) {
      console.warn('[ZK] ⚠ Failed to sync device clock:', timeErr.message || timeErr);
    }

    // Read all attendance logs from device
    const logsObj = await zk.getAttendances();
    const logs = logsObj.data;

    if (!Array.isArray(logs) || logs.length === 0) {
      console.log('[ZK] No attendance logs found on device.');
      return;
    }

    // Only process new logs since last sync
    const newLogs = logs.slice(lastSyncedIndex);
    if (newLogs.length === 0) {
      console.log('[ZK] No new logs since last sync.');
      return;
    }

    // Format for your backend's expected payload
    const formattedLogs = newLogs.map(log => {
      const d = new Date(log.record_time);
      const pad = (n) => String(n).padStart(2, '0');
      const localISO = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
      return {
        zkDeviceId: String(log.user_id),
        timestamp: localISO,
        type: typeof log.state === 'number' ? log.state : 0
      };
    });

    console.log(`[ZK] Sending ${formattedLogs.length} log(s) to backend...`);

    const response = await axios.post(API_URL, { logs: formattedLogs }, {
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY
      },
      timeout: 15000
    });

    console.log(`[ZK] ✓ Backend response:`, response.data);
    lastSyncedIndex = logs.length; // advance pointer

  } catch (err) {
    console.error('[ZK] Error:', err.message || err);
  } finally {
    try { await zk.disconnect(); } catch (_) { }
  }
}

async function syncSMS() {
  try {
    // 1. Fetch pending SMS from production server
    const pendingRes = await axios.get(SMS_PENDING_URL, {
      headers: { 'x-api-key': API_KEY },
      timeout: 10000
    });

    if (!pendingRes.data || !pendingRes.data.success) {
      return;
    }

    const pendingSMS = pendingRes.data.sms;
    if (!Array.isArray(pendingSMS) || pendingSMS.length === 0) {
      return;
    }

    console.log(`[SMS Sync] Found ${pendingSMS.length} pending SMS message(s) to dispatch.`);

    // 2. Initialize local SMS modem configurations
    const localModemUrl = process.env.SMS_MODEM_URL || 'http://192.168.8.1';

    // Get token
    let token = null;
    try {
      const tokenRes = await axios.get(`${localModemUrl}/api/webserver/token`, { timeout: 5000 });
      const match = tokenRes.data.match(/<token>(.*?)<\/token>/);
      if (match && match[1]) {
        token = match[1].trim();
      }
    } catch (tokenErr) {
      console.error(`[SMS Sync] Failed to get token from local modem at ${localModemUrl}:`, tokenErr.message);
    }

    if (!token) {
      console.error('[SMS Sync] Skipping SMS dispatch because modem token is unavailable.');
      return;
    }

    function htmlEscape(text) {
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function getCurrentDateTime() {
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }

    for (const sms of pendingSMS) {
      const { id, parent_phone, message } = sms;
      console.log(`[SMS Sync] Sending message to ${parent_phone}...`);

      const payload = `<?xml version="1.0" encoding="UTF-8"?>
<request>
    <Index>-1</Index>
    <Phones>
        <Phone>${parent_phone}</Phone>
    </Phones>
    <Sca></Sca>
    <Content>${htmlEscape(message)}</Content>
    <Length>${message.length}</Length>
    <Reserved>1</Reserved>
    <Date>${getCurrentDateTime()}</Date>
</request>`;

      let success = false;
      try {
        const res = await axios.post(`${localModemUrl}/api/sms/send-sms`, payload, {
          timeout: 10000,
          headers: {
            '__RequestVerificationToken': token,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          },
        });
        const responseText = String(res.data);
        if (responseText.includes('OK') || responseText.includes('<response>OK</response>')) {
          success = true;
          console.log(`[SMS Sync] ✓ Successfully sent to ${parent_phone}`);
        } else {
          console.warn(`[SMS Sync] ✗ Modem rejected SMS to ${parent_phone}`);
        }
      } catch (sendErr) {
        console.error(`[SMS Sync] ✗ Failed to transmit to ${parent_phone}:`, sendErr.message);
      }

      // Update status on the server
      try {
        await axios.post(SMS_UPDATE_URL, {
          id,
          status: success ? 'sent' : 'failed'
        }, {
          headers: {
            'Content-Type': 'application/json',
            'x-api-key': API_KEY
          },
          timeout: 10000
        });
        console.log(`[SMS Sync] Sent status update to server for ${parent_phone}`);
      } catch (updateErr) {
        console.error(`[SMS Sync] Failed to update SMS status on server:`, updateErr.message);
      }
    }

  } catch (err) {
    console.error('[SMS Sync] Error:', err.message || err);
  }
}

// Run immediately, then set up intervals
syncAttendance();
syncSMS();
setInterval(syncAttendance, 2 * 60 * 1000); // sync attendance logs every 2 minutes
setInterval(syncSMS, 10 * 1000); // poll and dispatch pending SMS every 10 seconds

console.log('[ZK Sync Client] Started. Syncing attendance every 2m, polling SMS every 10s.');
