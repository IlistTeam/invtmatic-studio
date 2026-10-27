'use strict';
// Keep stdio in this process: no shell, extra server or output on stdout.
const fs = require('node:fs');
const path = require('node:path');

function launchSettings(root, env = process.env) {
  const config = env.ILIST_INVT_CONFIG || (env.LOCALAPPDATA &&
    path.join(env.LOCALAPPDATA, 'IlistTeam', 'invtmatic-studio', 'config.json'));
  if (!config || !fs.existsSync(config)) {
    throw new Error('INVTmatic plugin is not configured. Run scripts/setup-plugin.ps1 from the installed plugin; see docs/PLUGIN.md.');
  }
  const settings = JSON.parse(fs.readFileSync(config, 'utf8').replace(/^\uFEFF/, ''));
  if (typeof settings.workspace !== 'string' || !path.isAbsolute(settings.workspace)) {
    throw new Error('Configure an absolute workspace outside the plugin.');
  }
  const workspace = fs.realpathSync(settings.workspace);
  const relative = path.relative(fs.realpathSync(root), workspace);
  if (relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative))) {
    throw new Error('Workspace must be outside the plugin cache.');
  }
  if (!fs.statSync(workspace).isDirectory()) throw new Error('Workspace is not a directory.');
  const entry = path.join(root, 'mcp', 'dist', 'invt-server.js');
  if (!fs.existsSync(entry)) throw new Error('MCP is not built. Run scripts/setup-plugin.ps1 for this installed version.');
  const args = ['--workspace', workspace];
  if (settings.studio_exe) args.push('--exe', settings.studio_exe);
  if (settings.studio_profile) args.push('--profile', settings.studio_profile);
  // Physical flags intentionally remain opt-in through the documented manual registration.
  return { entry, args };
}

module.exports = { launchSettings };
if (require.main === module) {
  try {
    const { entry, args } = launchSettings(path.resolve(__dirname, '..'));
    process.argv = [process.execPath, entry, ...args];
    require(entry);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
