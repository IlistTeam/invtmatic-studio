# INVTmatic persistent MCP

Версия INVT 0.4.0, 31 фиксированный инструмент. Инструкции установки и границы
проверенных возможностей находятся в [README пакета](../README.md).

```powershell
npm ci --ignore-scripts
npm run build
npm test
npm run test:guards
node dist/invt-server.js --workspace E:\PLCProjects
```

Последняя команда запускает stdio MCP, который ожидает MCP-клиента; она не
является интерактивной консолью. Для Codex зарегистрируйте её по инструкции пакета.

`--exe`, `--profile`, `--timeout-ms` — дополнительные параметры.
Входная точка — только `dist/invt-server.js`; неподтверждённые общие CODESYS
online-entrypoints в этот пакет не включены.

Host-тесты не требуют Studio. Native-тесты, симуляция и исследовательские probes
требуют установленной Studio и создают собственное окно/копию под `.invt/`.
Результаты сохраняются локально под `analysis/`; эти отчёты не коммитятся.

См. [план](docs/invt-debugging-plan.md), [матрицу API](docs/invt-debug-capabilities.md)
и [исследование пошаговой отладки](docs/invt-debugger-research.md).
