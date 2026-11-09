'use strict';
/* =========================================================
   Aloqa server — self-hosted messenger backend.
   One process serves the web app, a JSON API, real-time
   delivery over WebSocket and temporary media storage.
   Storage: SQLite (built into Node 22+) + files on disk.
   ========================================================= */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { DatabaseSync } = require('node:sqlite');
const { WebSocketServer } = require('ws');

const PORT = Number(process.env.PORT) || 8080;
const HOST = process.env.HOST || '0.0.0.0';
const DATA = path.resolve(process.env.DATA_DIR || path.join(__dirname, 'data'));
const APP_DIR = path.resolve(process.env.APP_DIR || path.join(__dirname, '..', 'app'));
const MEDIA_DIR = path.join(DATA, 'media');
const MEDIA_TTL_H = Number(process.env.MEDIA_TTL_HOURS) || 72;
const MAX_UPLOAD = (Number(process.env.MAX_UPLOAD_MB) || 50) * 1024 * 1024;
const HISTORY = 80; // messages per chat sent on connect
fs.mkdirSync(MEDIA_DIR, { recursive: true });

/* ---------- Database ---------- */
const db = new DatabaseSync(path.join(DATA, 'aloqa.db'));
db.exec(`
  PRAGMA journal_mode = WAL;
  PRAGMA foreign_keys = ON;
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, phone TEXT NOT NULL UNIQUE, name TEXT NOT NULL, username TEXT UNIQUE,
    bio TEXT NOT NULL DEFAULT '', color TEXT NOT NULL, pass TEXT NOT NULL,
    last_seen INTEGER NOT NULL, created_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY, type TEXT NOT NULL, title TEXT, created_by TEXT, created_at INTEGER NOT NULL, last_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS members (
    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member', last_read INTEGER NOT NULL DEFAULT 0, muted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id));
  CREATE INDEX IF NOT EXISTS members_user ON members(user_id);
  CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind TEXT NOT NULL, body TEXT,
    meta TEXT NOT NULL DEFAULT '{}', reply_to TEXT, media_id TEXT, created_at INTEGER NOT NULL);
  CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id, created_at);
  CREATE TABLE IF NOT EXISTS media (
    id TEXT PRIMARY KEY, key TEXT NOT NULL, owner TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL,
    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
`);
const Q = sql => db.prepare(sql);
const sql = {
  userByPhone: Q('SELECT * FROM users WHERE phone = ?'),
  userById: Q('SELECT * FROM users WHERE id = ?'),
  insertUser: Q('INSERT INTO users (id, phone, name, color, pass, last_seen, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)'),
  insertSession: Q('INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)'),
  sessionUser: Q('SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?'),
  deleteSession: Q('DELETE FROM sessions WHERE token_hash = ?'),
  touchUser: Q('UPDATE users SET last_seen = ? WHERE id = ?'),
  updateProfile: Q('UPDATE users SET name = ?, bio = ? WHERE id = ?'),
  myChats: Q('SELECT c.*, m.last_read, m.muted FROM chats c JOIN members m ON m.chat_id = c.id WHERE m.user_id = ? ORDER BY c.last_at DESC'),
  chatById: Q('SELECT * FROM chats WHERE id = ?'),
  chatMembers: Q('SELECT user_id, role, last_read, muted FROM members WHERE chat_id = ?'),
  isMember: Q('SELECT 1 AS ok FROM members WHERE chat_id = ? AND user_id = ?'),
  partners: Q('SELECT DISTINCT u.id, u.phone, u.name, u.username, u.bio, u.color, u.last_seen FROM members a JOIN members b ON a.chat_id = b.chat_id JOIN users u ON u.id = b.user_id WHERE a.user_id = ?'),
  partnerIds: Q('SELECT DISTINCT b.user_id AS id FROM members a JOIN members b ON a.chat_id = b.chat_id WHERE a.user_id = ? AND b.user_id <> a.user_id'),
  sharesChat: Q('SELECT 1 AS ok FROM members a JOIN members b ON a.chat_id = b.chat_id WHERE a.user_id = ? AND b.user_id = ? LIMIT 1'),
  findDirect: Q(`SELECT c.id FROM chats c JOIN members a ON a.chat_id = c.id AND a.user_id = ? JOIN members b ON b.chat_id = c.id AND b.user_id = ? WHERE c.type = 'direct' LIMIT 1`),
  insertChat: Q('INSERT INTO chats (id, type, title, created_by, created_at, last_at) VALUES (?, ?, ?, ?, ?, ?)'),
  insertMember: Q('INSERT INTO members (chat_id, user_id, role, last_read) VALUES (?, ?, ?, ?)'),
  recentMessages: Q('SELECT * FROM (SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?) ORDER BY created_at ASC'),
  messageById: Q('SELECT * FROM messages WHERE id = ?'),
  insertMessage: Q('INSERT INTO messages (id, chat_id, sender_id, kind, body, meta, reply_to, media_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'),
  deleteMessage: Q('DELETE FROM messages WHERE id = ?'),
  updateMeta: Q('UPDATE messages SET meta = ? WHERE id = ?'),
  bumpChat: Q('UPDATE chats SET last_at = ? WHERE id = ?'),
  setRead: Q('UPDATE members SET last_read = MAX(last_read, ?) WHERE chat_id = ? AND user_id = ?'),
  setMuted: Q('UPDATE members SET muted = ? WHERE chat_id = ? AND user_id = ?'),
  insertMedia: Q('INSERT INTO media (id, key, owner, mime, size, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)'),
  mediaById: Q('SELECT * FROM media WHERE id = ?'),
  expiredMedia: Q('SELECT id FROM media WHERE expires_at <= ?'),
  deleteMedia: Q('DELETE FROM media WHERE id = ?')
};

/* ---------- Helpers ---------- */
const now = () => Date.now();
const uuid = () => crypto.randomUUID();
const isUuid = s => typeof s === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s);
const sha256 = s => crypto.createHash('sha256').update(s).digest('hex');
const COLORS = ['g1', 'g2', 'g3', 'g4', 'g5', 'g6', 'g7'];
const KINDS = new Set(['text', 'image', 'video', 'voice', 'file', 'location', 'contact', 'poll', 'event']);
const SCRYPT = { N: 16384, r: 8, p: 1 };
function hashPassword(p) {
  const salt = crypto.randomBytes(16);
  return salt.toString('hex') + ':' + crypto.scryptSync(p, salt, 32, SCRYPT).toString('hex');
}
function checkPassword(p, stored) {
  const [salt, hash] = stored.split(':');
  const got = crypto.scryptSync(p, Buffer.from(salt, 'hex'), 32, SCRYPT);
  return crypto.timingSafeEqual(got, Buffer.from(hash, 'hex'));
}
const normPhone = p => { const s = String(p || '').replace(/[\s()-]/g, ''); return /^\+\d{8,15}$/.test(s) ? s : null; };
const publicUser = u => ({ id: u.id, phone: u.phone, name: u.name, username: u.username, bio: u.bio, color: u.color, lastSeen: u.last_seen, online: online.has(u.id) });

/* Simple in-memory rate limit: max `n` hits per `ms` per key */
const hits = new Map();
function limited(key, n = 10, ms = 10 * 60e3) {
  const t = now(), arr = (hits.get(key) || []).filter(x => t - x < ms);
  arr.push(t); hits.set(key, arr); return arr.length > n;
}
setInterval(() => { const t = now(); for (const [k, v] of hits) if (!v.some(x => t - x < 10 * 60e3)) hits.delete(k); }, 60e3).unref();

function newSession(userId) {
  const token = crypto.randomBytes(32).toString('base64url');
  sql.insertSession.run(sha256(token), userId, now());
  return token;
}
function userFromToken(token) { return token ? sql.sessionUser.get(sha256(String(token))) : null; }

function mediaInfo(id) {
  if (!id) return null;
  const m = sql.mediaById.get(id);
  if (!m || m.expires_at <= now()) return { expired: true };
  return { url: `media/${m.id}?k=${m.key}`, mime: m.mime, size: m.size, expiresAt: m.expires_at };
}
function msgOut(r) {
  let meta = {}; try { meta = JSON.parse(r.meta); } catch { /* keep empty */ }
  return { id: r.id, chatId: r.chat_id, from: r.sender_id, kind: r.kind, body: r.body || '', meta, replyTo: r.reply_to, media: mediaInfo(r.media_id), ts: r.created_at };
}
function chatOut(c, uid) {
  return {
    id: c.id, type: c.type, title: c.title, lastAt: c.last_at,
    members: sql.chatMembers.all(c.id).map(m => ({ id: m.user_id, role: m.role, lastRead: m.last_read, muted: !!m.muted })),
    messages: sql.recentMessages.all(c.id, HISTORY).map(msgOut)
  };
}

/* ---------- Real-time connections ---------- */
const online = new Map(); // userId -> Set<WebSocket>
function sendTo(userId, obj) {
  const set = online.get(userId); if (!set) return;
  const data = JSON.stringify(obj);
  for (const ws of set) if (ws.readyState === 1) ws.send(data);
}
const chatUserIds = chatId => sql.chatMembers.all(chatId).map(m => m.user_id);
function toChat(chatId, obj, exceptUser) { for (const id of chatUserIds(chatId)) if (id !== exceptUser) sendTo(id, obj); }
function toPartners(userId, obj) { for (const { id } of sql.partnerIds.all(userId)) sendTo(id, obj); }

function handleSocket(ws, user) {
  const uid = user.id;
  let set = online.get(uid);
  const first = !set; if (!set) { set = new Set(); online.set(uid, set); }
  set.add(ws);
  if (first) toPartners(uid, { type: 'presence', userId: uid, online: true, lastSeen: now() });
  const fresh = sql.userById.get(uid);
  ws.send(JSON.stringify({
    type: 'init', me: publicUser(fresh), mediaTtlHours: MEDIA_TTL_H,
    profiles: sql.partners.all(uid).map(publicUser),
    chats: sql.myChats.all(uid).map(c => chatOut(c, uid))
  }));

  const reply = (ref, obj) => ws.send(JSON.stringify({ ...obj, ref }));
  ws.on('message', raw => {
    let d; try { d = JSON.parse(raw.toString()); } catch { return; }
    if (!d || typeof d.type !== 'string') return;
    if (limited('ws:' + uid, 600, 60e3)) return reply(d.ref, { type: 'error', code: 'rate', message: 'Слишком много действий, подождите немного' });
    try { onEvent(d); } catch (e) { console.error('ws event error', e); reply(d.ref, { type: 'error', code: 'server', message: 'Ошибка сервера' }); }
  });
  ws.on('close', () => {
    set.delete(ws);
    if (!set.size) {
      online.delete(uid); const t = now(); sql.touchUser.run(t, uid);
      toPartners(uid, { type: 'presence', userId: uid, online: false, lastSeen: t });
    }
  });

  function onEvent(d) {
    const member = cid => typeof cid === 'string' && !!sql.isMember.get(cid, uid);
    switch (d.type) {
      case 'ping': return reply(d.ref, { type: 'pong' });

      case 'send': {
        if (!isUuid(d.id) || !member(d.chatId) || !KINDS.has(d.kind)) return reply(d.ref, { type: 'error', code: 'bad_request', message: 'Сообщение не отправлено' });
        if (sql.messageById.get(d.id)) return reply(d.ref, { type: 'ack', id: d.id });
        const body = typeof d.body === 'string' ? d.body.slice(0, 4000) : '';
        const meta = JSON.stringify(d.meta && typeof d.meta === 'object' ? d.meta : {});
        if (meta.length > 8192) return reply(d.ref, { type: 'error', code: 'too_big', message: 'Сообщение слишком большое' });
        if (d.kind === 'text' && !body.trim()) return;
        let mediaId = null;
        if (d.mediaId) { const m = sql.mediaById.get(String(d.mediaId)); if (!m || m.owner !== uid) return reply(d.ref, { type: 'error', code: 'media', message: 'Файл не найден' }); mediaId = m.id; }
        let replyTo = null;
        if (d.replyTo) { const r = sql.messageById.get(String(d.replyTo)); if (r && r.chat_id === d.chatId) replyTo = r.id; }
        const t = now();
        sql.insertMessage.run(d.id, d.chatId, uid, d.kind, body, meta, replyTo, mediaId, t);
        sql.bumpChat.run(t, d.chatId); sql.setRead.run(t, d.chatId, uid);
        const out = msgOut(sql.messageById.get(d.id));
        reply(d.ref, { type: 'ack', id: d.id, ts: t, media: out.media });
        toChat(d.chatId, { type: 'message', message: out });
        return;
      }
      case 'typing': if (member(d.chatId)) toChat(d.chatId, { type: 'typing', chatId: d.chatId, userId: uid }, uid); return;
      case 'read': {
        if (!member(d.chatId)) return;
        const t = now(); sql.setRead.run(t, d.chatId, uid);
        toChat(d.chatId, { type: 'read', chatId: d.chatId, userId: uid, at: t }, uid);
        return;
      }
      case 'mute': if (member(d.chatId)) sql.setMuted.run(d.muted ? 1 : 0, d.chatId, uid); return;
      case 'delete': {
        const m = sql.messageById.get(String(d.id));
        if (!m || m.sender_id !== uid) return;
        sql.deleteMessage.run(m.id);
        if (m.media_id) removeMedia(m.media_id);
        toChat(m.chat_id, { type: 'deleted', chatId: m.chat_id, id: m.id });
        return;
      }
      case 'vote': case 'rsvp': {
        const m = sql.messageById.get(String(d.id));
        if (!m || !member(m.chat_id)) return;
        const meta = JSON.parse(m.meta || '{}');
        if (d.type === 'vote' && m.kind === 'poll') {
          const opt = Number(d.opt);
          if (!Array.isArray(meta.opts) || !(opt >= 0 && opt < meta.opts.length)) return;
          meta.votes = meta.votes || {}; if (uid in meta.votes) return;
          meta.votes[uid] = opt;
        } else if (d.type === 'rsvp' && m.kind === 'event') {
          meta.going = meta.going || {};
          if (meta.going[uid]) delete meta.going[uid]; else meta.going[uid] = true;
        } else return;
        sql.updateMeta.run(JSON.stringify(meta), m.id);
        toChat(m.chat_id, { type: 'update', message: msgOut(sql.messageById.get(m.id)) });
        return;
      }
      case 'start_chat': {
        const phone = normPhone(d.phone);
        const other = phone && sql.userByPhone.get(phone);
        if (!other) return reply(d.ref, { type: 'error', code: 'not_found', message: 'Пользователь с таким номером не найден в Aloqa' });
        if (other.id === uid) return reply(d.ref, { type: 'error', code: 'self', message: 'Это ваш собственный номер' });
        let row = sql.findDirect.get(uid, other.id), created = false;
        if (!row) {
          const id = uuid(), t = now();
          db.exec('BEGIN');
          try {
            sql.insertChat.run(id, 'direct', null, uid, t, t);
            sql.insertMember.run(id, uid, 'owner', t); sql.insertMember.run(id, other.id, 'member', 0);
            db.exec('COMMIT');
          } catch (e) { db.exec('ROLLBACK'); throw e; }
          row = { id }; created = true;
        }
        const chat = sql.chatById.get(row.id);
        const me = sql.userById.get(uid);
        reply(d.ref, { type: 'chat', chat: chatOut(chat, uid), profiles: [publicUser(other)] });
        if (created) sendTo(other.id, { type: 'chat', chat: chatOut(chat, other.id), profiles: [publicUser(me)] });
        return;
      }
      case 'profile': {
        const name = String(d.name || '').trim().slice(0, 64), bio = String(d.bio ?? fresh.bio ?? '').slice(0, 140);
        if (!name) return;
        sql.updateProfile.run(name, bio, uid);
        const p = publicUser(sql.userById.get(uid));
        sendTo(uid, { type: 'profile', profile: p }); toPartners(uid, { type: 'profile', profile: p });
        return;
      }
    }
  }
}

/* ---------- Media cleanup: files live only MEDIA_TTL_HOURS ---------- */
function removeMedia(id) {
  sql.deleteMedia.run(id);
  fs.rm(path.join(MEDIA_DIR, id), { force: true }, () => {});
}
function cleanupMedia() {
  const expired = sql.expiredMedia.all(now());
  for (const { id } of expired) removeMedia(id);
  if (expired.length) console.log(`media cleanup: removed ${expired.length} expired file(s)`);
}
cleanupMedia();
setInterval(cleanupMedia, 15 * 60e3).unref();

/* ---------- HTTP ---------- */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2'
};
const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
  'Permissions-Policy': 'camera=(self), microphone=(self), geolocation=(self)'
};
function json(res, code, obj) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...SECURITY_HEADERS });
  res.end(JSON.stringify(obj));
}
function readJson(req, limit = 16 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => { size += c.length; if (size > limit) { reject(Object.assign(new Error('too big'), { code: 413 })); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString() || '{}')); } catch { reject(Object.assign(new Error('bad json'), { code: 400 })); } });
    req.on('error', reject);
  });
}
/* Trust X-Forwarded-For only behind our own reverse proxy (TRUST_PROXY=1), otherwise it can be spoofed */
const clientIp = req => String((process.env.TRUST_PROXY && req.headers['x-forwarded-for']) || req.socket.remoteAddress || '').split(',')[0].trim();
const bearer = req => (String(req.headers.authorization || '').match(/^Bearer (.+)$/) || [])[1];

async function api(req, res, url) {
  const route = req.method + ' ' + url.pathname;
  if (route === 'GET /api/health') return json(res, 200, { app: 'aloqa', version: 1, mediaTtlHours: MEDIA_TTL_H, maxUploadMb: MAX_UPLOAD / 1048576 });

  if (route === 'GET /api/phone') {
    if (limited('phone:' + clientIp(req), 30)) return json(res, 429, { error: 'Слишком много попыток, подождите 10 минут' });
    const phone = normPhone(url.searchParams.get('p'));
    if (!phone) return json(res, 400, { error: 'Неверный формат номера' });
    return json(res, 200, { registered: !!sql.userByPhone.get(phone) });
  }

  if (route === 'POST /api/register' || route === 'POST /api/login') {
    const b = await readJson(req);
    const phone = normPhone(b.phone), pass = String(b.password || '');
    if (!phone) return json(res, 400, { error: 'Неверный формат номера' });
    if (limited('auth:' + clientIp(req) + phone)) return json(res, 429, { error: 'Слишком много попыток, подождите 10 минут' });
    if (route === 'POST /api/register') {
      const name = String(b.name || '').trim().slice(0, 64);
      if (!name) return json(res, 400, { error: 'Укажите имя' });
      if (pass.length < 6) return json(res, 400, { error: 'Пароль должен быть не короче 6 символов' });
      if (sql.userByPhone.get(phone)) return json(res, 409, { error: 'Этот номер уже зарегистрирован — войдите с паролем' });
      const id = uuid(), t = now();
      sql.insertUser.run(id, phone, name, COLORS[crypto.randomInt(COLORS.length)], hashPassword(pass), t, t);
      return json(res, 200, { token: newSession(id) });
    }
    const u = sql.userByPhone.get(phone);
    if (!u || !checkPassword(pass, u.pass)) return json(res, 401, { error: 'Неверный номер или пароль' });
    return json(res, 200, { token: newSession(u.id) });
  }

  const token = bearer(req), user = userFromToken(token);
  if (!user) return json(res, 401, { error: 'Нужно войти заново' });

  if (route === 'POST /api/logout') { sql.deleteSession.run(sha256(token)); return json(res, 200, { ok: true }); }

  if (route === 'POST /api/upload') {
    const mime = String(req.headers['content-type'] || 'application/octet-stream').split(';')[0].trim().toLowerCase();
    if (!/^[a-z]+\/[a-z0-9.+-]+$/.test(mime)) return json(res, 400, { error: 'Неизвестный тип файла' });
    const len = Number(req.headers['content-length'] || 0);
    if (len > MAX_UPLOAD) return json(res, 413, { error: `Файл больше ${MAX_UPLOAD / 1048576} МБ` });
    const id = uuid(), key = crypto.randomBytes(16).toString('base64url'), file = path.join(MEDIA_DIR, id);
    let size = 0, aborted = false;
    const out = fs.createWriteStream(file);
    await new Promise(resolve => {
      req.on('data', c => { size += c.length; if (size > MAX_UPLOAD && !aborted) { aborted = true; req.unpipe(out); out.destroy(); fs.rm(file, { force: true }, () => {}); resolve(); } });
      req.pipe(out); out.on('finish', resolve); out.on('error', resolve); req.on('error', resolve);
    });
    if (aborted) return json(res, 413, { error: `Файл больше ${MAX_UPLOAD / 1048576} МБ` });
    if (!size) { fs.rm(file, { force: true }, () => {}); return json(res, 400, { error: 'Пустой файл' }); }
    const t = now(), exp = t + MEDIA_TTL_H * 3600e3;
    sql.insertMedia.run(id, key, user.id, mime, size, t, exp);
    return json(res, 200, { id, url: `media/${id}?k=${key}`, mime, size, expiresAt: exp });
  }
  return json(res, 404, { error: 'Не найдено' });
}

function serveMedia(req, res, url) {
  const id = url.pathname.split('/')[2];
  const m = isUuid(id) && sql.mediaById.get(id);
  if (!m || m.key !== url.searchParams.get('k') || m.expires_at <= now()) { res.writeHead(404, SECURITY_HEADERS); return res.end('Файл удалён или не найден'); }
  const file = path.join(MEDIA_DIR, m.id);
  const headers = { 'Content-Type': m.mime, 'Accept-Ranges': 'bytes', 'Cache-Control': 'private, max-age=600', 'Content-Disposition': 'inline', ...SECURITY_HEADERS };
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
  if (range) {
    let start = range[1] ? Number(range[1]) : m.size - Number(range[2]);
    let end = range[1] && range[2] ? Number(range[2]) : m.size - 1;
    if (start >= m.size || start < 0 || end < start) { res.writeHead(416, { 'Content-Range': `bytes */${m.size}` }); return res.end(); }
    end = Math.min(end, m.size - 1);
    res.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${m.size}`, 'Content-Length': end - start + 1 });
    return fs.createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { ...headers, 'Content-Length': m.size });
  fs.createReadStream(file).pipe(res);
}

function serveStatic(req, res, url) {
  let rel = decodeURIComponent(url.pathname);
  if (rel.endsWith('/')) rel += 'index.html';
  const file = path.resolve(APP_DIR, '.' + rel);
  if (!file.startsWith(APP_DIR + path.sep)) { res.writeHead(403); return res.end(); }
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404, SECURITY_HEADERS); return res.end('Not found'); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream', 'Content-Length': st.size, 'Cache-Control': 'no-cache', ...SECURITY_HEADERS });
    fs.createReadStream(file).pipe(res);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://local');
  try {
    if (url.pathname.startsWith('/api/')) return await api(req, res, url);
    if (url.pathname.startsWith('/media/') && req.method === 'GET') return serveMedia(req, res, url);
    if (req.method === 'GET' || req.method === 'HEAD') return serveStatic(req, res, url);
    res.writeHead(405); res.end();
  } catch (e) {
    if (!res.headersSent) json(res, e.code === 413 ? 413 : e.code === 400 ? 400 : 500, { error: e.code ? 'Неверный запрос' : 'Ошибка сервера' });
    if (!e.code) console.error(e);
  }
});

/* WebSocket: first message must be {type:'auth', token} */
const wss = new WebSocketServer({ server, path: '/ws', maxPayload: 64 * 1024 });
wss.on('connection', ws => {
  let authed = false;
  const timer = setTimeout(() => { if (!authed) ws.close(4001, 'auth timeout'); }, 10e3);
  ws.isAlive = true; ws.on('pong', () => { ws.isAlive = true; });
  ws.once('message', raw => {
    clearTimeout(timer);
    let d; try { d = JSON.parse(raw.toString()); } catch { return ws.close(4001, 'bad auth'); }
    const user = d && d.type === 'auth' && userFromToken(d.token);
    if (!user) return ws.close(4001, 'unauthorized');
    authed = true; handleSocket(ws, user);
  });
});
/* Drop dead connections so presence stays accurate */
setInterval(() => { for (const ws of wss.clients) { if (!ws.isAlive) { ws.terminate(); continue; } ws.isAlive = false; ws.ping(); } }, 30e3).unref();

server.listen(PORT, HOST, () => console.log(`Aloqa server: http://${HOST}:${PORT}  (app: ${APP_DIR}, data: ${DATA}, media TTL: ${MEDIA_TTL_H} h)`));
const shutdown = () => { console.log('shutting down'); wss.close(); server.close(() => { db.close(); process.exit(0); }); setTimeout(() => process.exit(0), 3000).unref(); };
process.on('SIGTERM', shutdown); process.on('SIGINT', shutdown);
