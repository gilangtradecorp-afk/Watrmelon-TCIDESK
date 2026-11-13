// Run: node --test
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'crm-')), 'writes.json');
process.env.CRM_DATA = file;
const server = require('../server.js');

test('server saves a doc, returns it, and rejects bad input', async () => {
  await new Promise(r => server.listen(0, r));
  const base = `http://localhost:${server.address().port}`;
  try {
    const put = (p, body) => fetch(base + p, { method: 'PUT', body });

    assert.equal((await put('/api/doc/enquiries/E1', JSON.stringify({ name: 'A (sample)' }))).status, 200);
    const data = await (await fetch(base + '/api/data')).json();
    assert.deepEqual(data.enquiries.E1, { name: 'A (sample)' });
    assert.equal(data.ver, 1);
    assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')).enquiries.E1, { name: 'A (sample)' });

    assert.equal((await put('/api/doc/users/X', '{}')).status, 400);
    assert.equal((await put('/api/doc/enquiries/E2', 'not json')).status, 400);
    assert.equal((await put('/api/doc/enquiries/E2', '[1]')).status, 400);
    assert.equal((await fetch(base + '/../server.js')).status, 404);
    assert.equal((await fetch(base + '/')).status, 200);
  } finally {
    server.close();
  }
});
