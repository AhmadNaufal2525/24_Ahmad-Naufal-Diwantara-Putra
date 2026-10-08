/**
 * Serverless function Node.js (Vercel) — penerima laporan dari Supabase.
 *
 * Endpoint:  POST /api/webhook
 * Header:    x-signature: <hex HMAC-SHA256 dari body JSON>
 *
 * Env variable (set di Vercel → Settings → Environment Variables):
 *   HMAC_SECRET          kunci rahasia untuk verifikasi signature
 *   TELEGRAM_BOT_TOKEN   token bot dari @BotFather
 *   TELEGRAM_CHAT_ID     ID chat/grup tujuan notifikasi
 */

import crypto from 'node:crypto';

// Escape karakter khusus untuk parse_mode HTML Telegram
function escapeHtml(value) {
  return String(value ?? '-')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Ambil data laporan dari payload Supabase.
 * Mendukung format Database Webhook Supabase ({ type, table, record, ... })
 * maupun payload langsung ({ status, level, pesan, ... }).
 */
function ambilLaporan(payload) {
  const data = payload?.record ?? payload ?? {};

  const statusMentah = String(data.status ?? data.prediction ?? '').toUpperCase();
  const status = statusMentah === 'BAHAYA' ? 'BAHAYA' : statusMentah === 'AMAN' ? 'AMAN' : 'TIDAK DIKETAHUI';

  return {
    status,
    level: data.level ?? data.threat_level ?? data.level_ancaman ?? '-',
    detail: data.pesan ?? data.message ?? data.detail ?? data.deskripsi ?? '-',
    sumber: payload?.table ? `${payload.schema ?? 'public'}.${payload.table}` : '-',
    event: payload?.type ?? '-',
    waktu: data.created_at ?? new Date().toISOString(),
  };
}

function formatPesan(laporan) {
  const ikon = laporan.status === 'BAHAYA' ? '🚨' : laporan.status === 'AMAN' ? '✅' : 'ℹ️';
  return [
    `${ikon} <b>LAPORAN KEAMANAN</b>`,
    '',
    `<b>Status:</b> ${escapeHtml(laporan.status)}`,
    `<b>Level Ancaman:</b> ${escapeHtml(laporan.level)}`,
    `<b>Detail:</b> ${escapeHtml(laporan.detail)}`,
    '',
    `<b>Sumber:</b> ${escapeHtml(laporan.sumber)} (${escapeHtml(laporan.event)})`,
    `<b>Waktu:</b> ${escapeHtml(laporan.waktu)}`,
  ].join('\n');
}

async function kirimTelegram(text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;

  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'HTML' }),
  });

  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.description || `Telegram error ${res.status}`);
  }
  return data.result;
}

export default async function handler(req, res) {
  // Hanya terima POST
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ status: 'error', message: 'Method not allowed' });
  }

  // Pastikan env variable sudah di-set
  const { HMAC_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID } = process.env;
  if (!HMAC_SECRET || !TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
    return res.status(500).json({ status: 'error', message: 'Konfigurasi server belum lengkap' });
  }

  // 1. Header x-signature wajib ada
  const signature = req.headers['x-signature'];
  if (!signature) {
    return res.status(400).json({ status: 'error', message: 'Bad Request: header x-signature tidak ada' });
  }

  // 2. Ambil body sebagai string JSON
  const body = JSON.stringify(req.body ?? {});

  // 3. Buat HMAC-SHA256 dari body string
  const hmac = crypto.createHmac('sha256', HMAC_SECRET).update(body).digest('hex');

  // 4. Bandingkan dengan header x-signature
  if (hmac !== signature) {
    return res.status(401).json({ status: 'error', message: 'Unauthorized: signature tidak valid' });
  }

  // 5. Signature valid → kirim ke Telegram
  try {
    const laporan = ambilLaporan(req.body);
    const terkirim = await kirimTelegram(formatPesan(laporan));

    return res.status(200).json({
      status: 'success',
      message: 'Laporan diterima dan dikirim ke Telegram',
      data: { laporan, telegram_message_id: terkirim.message_id },
    });
  } catch (err) {
    return res.status(502).json({ status: 'error', message: `Gagal kirim ke Telegram: ${err.message}` });
  }
}