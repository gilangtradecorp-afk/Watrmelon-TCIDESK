// Tradecorp CRM local server. No dependencies: run `node server.js`.
// Serves the model and keeps shared data in model/writes.json so every PC on the office network sees the same records.
// shortcut: no login, anyone who can reach the port can read and write; add real login (Entra) before real customer data.
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.env.PORT) || 8080;
const DIR = path.join(__dirname, 'model');
const FILE = process.env.CRM_DATA || path.join(DIR, 'writes.json');
const COLS = ['enquiries', 'requests', 'catalog', 'meta'];
const STATIC = { '/': 'index.html', '/index.html': 'index.html', '/seed.json': 'seed.json' };
const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8' };

function load() {
  try { return JSON.parse(fs.readFileSync(FILE, 'utf8')); }
  catch (e) {
    if (e.code !== 'ENOENT') throw new Error(`Cannot read ${FILE}: ${e.message}. Fix or move the file; refusing to start so data is not overwritten.`);
    return { ver: 0, enquiries: {}, requests: {}, catalog: {}, meta: {} };
  }
}

let data = load();

function save() {
  // write to a temp file first, then rename, so a crash mid-write never leaves a half-written file
  const tmp = FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 1));
  fs.renameSync(tmp, FILE);
}

function send(res, code, body, type = TYPES['.json']) {
  res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store' });
  res.end(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body));
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');

  if (req.method === 'GET' && STATIC[url.pathname]) {
    const f = path.join(DIR, STATIC[url.pathname]);
    return fs.readFile(f, (err, buf) => err ? send(res, 404, { error: 'not found' }) : send(res, 200, buf, TYPES[path.extname(f)]));
  }

  if (req.method === 'GET' && url.pathname === '/api/data') return send(res, 200, data);

  const m = url.pathname.match(/^\/api\/doc\/([a-z]+)\/([\w.-]{1,80})$/);
  if (req.method === 'PUT' && m) {
    const [, col, id] = m;
    if (!COLS.includes(col)) return send(res, 400, { error: 'unknown collection', code: 'invalid-argument' });
    let body = '';
    req.on('data', c => { body += c; if (body.length > 1e6) req.destroy(); });
    req.on('end', () => {
      let doc;
      try { doc = JSON.parse(body); } catch { return send(res, 400, { error: 'bad JSON', code: 'invalid-argument' }); }
      if (!doc || typeof doc !== 'object' || Array.isArray(doc)) return send(res, 400, { error: 'doc must be an object', code: 'invalid-argument' });
      const before = data[col][id];
      data[col][id] = doc;
      data.ver++;
      try { save(); } catch (e) {
        data[col][id] = before; data.ver--;
        console.error('Save failed:', e.message);
        return send(res, 500, { error: 'save failed', code: 'unavailable' });
      }
      send(res, 200, { ok: true, ver: data.ver });
    });
    return;
  }

  send(res, 404, { error: 'not found' });
});

if (require.main === module) {
  server.listen(PORT, () => {
    console.log(`Tradecorp CRM running: http://localhost:${PORT}`);
    console.log(`Other PCs on the network: http://<this PC's IP address>:${PORT}`);
    console.log(`Data file: ${FILE}`);
  });
}

module.exports = server;
