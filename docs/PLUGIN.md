# Плагин INVTmatic Studio

Версия плагина и MCP — 0.7.1. Нужны Windows, интерактивный сеанс,
Node.js/npm (проверенная линия Node 24), установленная INVTmatic Studio с
ScriptEngine. Библиотеки и Studio не поставляются в пакете. Лицензия исходного
MCP сохранена в `mcp/LICENSE`.

## Установка из общего каталога

```powershell
codex plugin marketplace add IlistTeam/plugin-marketplace
```

В каталоге **IlistTeam Plugins** установите **INVTmatic Studio**.
Если CLI поддерживает установку: `codex plugin add invtmatic-studio@ilistteam`.
После установки используйте `$invtmatic-studio` для первичной настройки.

Из корня **установленной копии** плагина выполните, выбрав свою рабочую папку:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-plugin.ps1 -Workspace 'C:\Projects\INVT'
```

Путь — пример, его выбирает пользователь. Для другой установки Studio передайте
`-StudioExe '<полный путь к exe>'` и `-StudioProfile '<профиль>'` после проверки
окружения. Скрипт устанавливает зависимости по lockfile без lifecycle-скриптов,
собирает MCP и сохраняет настройки в
`%LOCALAPPDATA%\IlistTeam\invtmatic-studio\config.json`.
Проекты находятся вне установленного пакета, переживают обновление и удаление.
Не переносите проекты в кэш и не коммитьте пользовательские настройки.

Переподключите MCP/откройте новый чат. `invt_session_status` должен вернуть
`state: stopped`, `physical_runtime_allowed: false`; список содержит 44 инструмента.
Это проверяет транспорт, а не работу Studio или симуляции. Запуск Studio
выполняется отдельной операцией `invt_session_start` в рамках задачи.

Если уже установлен отдельный навык/MCP `invtmatic-persistent`, отключите старую
регистрацию перед включением версии из плагина. Не удаляйте резервный адаптер
и пользовательские проекты. Один MCP должен владеть одной Studio-сессией.

## Обновление

Обновите источник командой `codex plugin marketplace upgrade ilistteam`, затем
обновите плагин в клиенте. Повторите setup из новой установленной копии с прежними
параметрами: node_modules/dist не входят в Git. Закройте собственную активную
сессию перед переключением MCP; не завершайте чужую Studio.
Простой `git pull` в клоне не обновляет установленный кэш.

Пакет использует только стандартные инструменты разработки/симуляции.
Для отдельно запрошенного физического TM751 применяется ручная регистрация
по [процедуре ПЛК](../references/physical-plc.md); она не включается установкой.

В 0.7.1 обновлены Zod и транзитивные body-parser/fast-uri для устранения
предупреждений npm audit; проверяется новая схема через MCP tools/list.

## Проверки без Studio

```powershell
cd mcp
npm ci --ignore-scripts
npm run build
npm test
npm run test:guards
node --test tests/plugin-package.test.cjs
```

Проверка пакета переносит launcher и сборку в другую папку, выполняет настоящий
MCP initialize/tools/list/status без запуска IDE, проверяет отказ при отсутствии
настроек и при workspace внутри кэша. Нативная приёмка описана в основном README.
