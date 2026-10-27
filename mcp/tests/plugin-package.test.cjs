'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
const root = path.resolve(__dirname, '../..');
const { launchSettings } = require('../../scripts/start-plugin.cjs');

test('portable and compatibility manifests resolve the same installed components', () => {
  const portable = JSON.parse(fs.readFileSync(path.join(root, 'plugin.json'), 'utf8'));
  const legacy = JSON.parse(fs.readFileSync(path.join(root, '.codex-plugin/plugin.json'), 'utf8'));
  assert.equal(portable.name, legacy.name);
  assert.equal(portable.version, legacy.version);
  const mcp = JSON.parse(fs.readFileSync(path.join(root, 'mcp.json'), 'utf8'));
  const fallback = JSON.parse(fs.readFileSync(path.join(root, '.mcp.json'), 'utf8'));
  assert.deepEqual(mcp.mcpServers, fallback.mcpServers);
  assert.ok(fs.existsSync(path.join(root, legacy.skills, 'invtmatic-studio/SKILL.md')));
});

test('relocated installed launcher initializes MCP with no IDE and no physical tools', { timeout: 60000 }, async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'invt-plugin-'));
  const installed = path.join(directory, 'installed plugin');
  const workspace = path.join(directory, 'user projects');
  fs.mkdirSync(path.join(installed, 'scripts'), { recursive: true });
  fs.mkdirSync(path.join(installed, 'mcp'), { recursive: true });
  fs.mkdirSync(workspace);
  fs.copyFileSync(path.join(root, 'scripts/start-plugin.cjs'), path.join(installed, 'scripts/start-plugin.cjs'));
  fs.cpSync(path.join(root, 'mcp/dist'), path.join(installed, 'mcp/dist'), { recursive: true });
  fs.cpSync(path.join(root, 'mcp/node_modules'), path.join(installed, 'mcp/node_modules'), { recursive: true });
  const config = path.join(directory, 'config.json');
  fs.writeFileSync(config, JSON.stringify({ workspace }));
  const transport = new StdioClientTransport({ command: process.execPath,
    args: [path.join(installed, 'scripts/start-plugin.cjs')], cwd: directory,
    env: { ...process.env, ILIST_INVT_CONFIG: config }, stderr: 'pipe' });
  const client = new Client({ name: 'plugin-package-test', version: '1.0.0' });
  try {
    await client.connect(transport);
    const { tools } = await client.listTools();
    assert.equal(tools.length, 44);
    assert.ok(!tools.some(t => /_plc$|_plc_|plc_gateways/.test(t.name)));
    const response = await client.callTool({ name: 'invt_session_status', arguments: {} });
    assert.ok(!response.isError);
    const status = JSON.parse(response.content[0].text);
    assert.equal(status.state, 'stopped');
    assert.equal(status.pid, null);
    assert.equal(status.physical_runtime_allowed, false);
    assert.equal(status.physical_discovery_allowed, false);
    for (const args of [
      { name: 'Task', interval_ms: 0, priority: 5 },
      { name: 'Task', interval_ms: 10, priority: 5, watchdog: { enabled: true } }
    ]) {
      const invalid = await client.callTool({ name: 'invt_create_task', arguments: args });
      assert.ok(invalid.isError);
      assert.match(invalid.content[0].text, /validation|Invalid arguments/i);
      assert.doesNotMatch(invalid.content[0].text, /Session not ready/);
    }
    assert.ok(!fs.existsSync(path.join(workspace, '.invt')));
    fs.writeFileSync(config, JSON.stringify({ workspace: installed }));
    assert.throws(() => launchSettings(installed, { ILIST_INVT_CONFIG: config }), /outside/);
    assert.throws(() => launchSettings(installed, { ILIST_INVT_CONFIG: path.join(directory, 'missing') }), /not configured/);
  } finally {
    await client.close();
    // This directory was allocated by this test and contains only its own copies.
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
