# Offline fallback MCP registration

For the preferred persistent server, read [persistent.md](persistent.md).
The instructions here apply only to the preserved Python fallback.

This adapter uses Python 3.10+ standard library only and MCP stdio protocol
2024-11-05. Newer clients can negotiate that version. It exposes three tools:
`invt_submit`, `invt_status`, `invt_cancel`. Job operations are `inspect`, `build`,
`patch_st`, `export_pou`.

Run the server under the ordinary interactive Windows user who has INVTmatic
Studio installed. `--workspace` restricts project inputs and outputs. The default
Studio executable/profile match the verified installation; override them explicitly
after an upgrade. A desktop session and the Studio installation remain necessary.

Example registration after installing this skill in the default skills folder:

```powershell
$pythonExecutable = (Get-Command python -CommandType Application).Source
$fallbackScript = Join-Path $env:USERPROFILE '.codex\skills\invtmatic-studio\scripts\invt_mcp.py'
codex mcp add invtmatic-offline -- $pythonExecutable $fallbackScript --workspace 'E:\PLCProjects'
```

Equivalent TOML entry (merge only this section, never replace the whole config):

```toml
[mcp_servers.invtmatic-offline]
command = 'C:\Python312\python.exe'
args = ['C:\Users\YOUR_USER\.codex\skills\invtmatic-studio\scripts\invt_mcp.py', '--workspace', 'E:\PLCProjects']
```

Startup is lightweight; long Studio operations happen as background jobs. A
single server handles one job at a time. The CLI and MCP runner also share a
workspace lock. The initial `invt_submit` response is not proof of success: poll
`invt_status` and inspect `ok`, `build_ok`, and `result_file`.

When the client closes stdin, the server cancels its active job and terminates
only the dedicated process it owns. Source projects are never overwritten.
This is a development integration, with no connection to a PLC.
