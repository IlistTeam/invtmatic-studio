# INVTmatic Studio: навык и постоянный MCP

Пакет для разработки IEC 61131-3 ST в INVTmatic Studio: навык Codex,
31 инструмент постоянного MCP, сохранённый резервный Python-адаптер и тесты.
Проверено на Windows с INVTmatic Studio V3.0.1.4, CODESYS core 3.5.20.60,
ScriptEngine 4.1.0.0, Node 24.19.0. На другой установке сначала проверьте
[совместимость](references/environment.md). Studio и её библиотеки в пакет не входят.

MCP создаёт собственное окно Studio и работает с копиями проектов. Доступны
редактирование/компиляция/экспорт ST, создание POU/GVL/DUT, циклических задач и
привязок программ, а также запуск и наблюдение **положительно проверенной симуляции**.
Управление физическим ПЛК и сетевой поиск не реализованы.

## Установка

Нужны установленная Studio с ScriptEngine, интерактивный сеанс Windows, Git,
Node/npm и Codex. Для резервного адаптера и guard-тестов нужен Python 3.10+.
Используйте реальные интерпретаторы, а не Windows Store aliases.

Клонируйте этот репозиторий в выбранную папку. Затем скопируйте только ресурсы
навыка в каталог навыков Codex. Пример PowerShell для **новой** установки:

```powershell
git clone https://github.com/IlistTeam/Skills.git C:\Tools\Skills
$packageRoot = 'C:\Tools\Skills\invtmatic-studio'
$skillDestination = Join-Path $env:USERPROFILE '.codex\skills\invtmatic-studio'
if (Test-Path -LiteralPath $skillDestination) { throw 'Навык уже установлен: сначала сравните версии' }
New-Item -ItemType Directory -Path $skillDestination -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $packageRoot 'SKILL.md') -Destination $skillDestination
foreach ($resource in @('agents', 'references', 'scripts')) {
    Copy-Item -LiteralPath (Join-Path $packageRoot $resource) -Destination $skillDestination -Recurse
}
```

Если используется собственный `CODEX_HOME`, укажите его каталог `skills` вместо
пути по умолчанию. Код MCP остаётся в клоне; после регистрации этот клон нужен
для запуска сервера. Не переносите его без обновления регистрации.

Соберите MCP, используя lockfile:

```powershell
Set-Location (Join-Path $packageRoot 'mcp')
npm ci --ignore-scripts
npm run build
npm test
python tests/invt-runtime-guards.py
```

Зарегистрируйте сервер для нужного рабочего каталога проектов. Замените путь
проекта на свой; сервер не читает проекты за пределами этого каталога:

```powershell
$projectRoot = 'E:\PLCProjects'
$nodeExecutable = (Get-Command node -CommandType Application).Source
$serverEntrypoint = Join-Path $packageRoot 'mcp\dist\invt-server.js'
codex mcp add invtmatic-persistent -- $nodeExecutable $serverEntrypoint --workspace $projectRoot
```

Используется только `dist/invt-server.js`. Добавляйте или обновляйте одну секцию
конфигурации, сохраняя остальные серверы. Пример эквивалентного TOML:

```toml
[mcp_servers.invtmatic-persistent]
command = 'C:\Program Files\nodejs\node.exe'
args = ['C:\Tools\Skills\invtmatic-studio\mcp\dist\invt-server.js', '--workspace', 'E:\PLCProjects']
startup_timeout_sec = 30
tool_timeout_sec = 180
```

Путь Node в примере надо сверить с `$nodeExecutable`. При другой установке Studio
передайте `--exe` и `--profile` после проверки её окружения. Регистрация и MCP
инициализация Studio не запускают. После изменения кода пересоберите сервер и
переподключите MCP/чат: работающий процесс не перечитывает инструменты.
Синтаксис настройки: [документация Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Первый цикл работы

Попросите Codex использовать `$invtmatic-studio`. Проверьте наличие 31 инструмента
в пространстве `invtmatic-persistent`. Начните с `invt_session_status`, затем
`invt_session_start`, `invt_open_copy`, `invt_inspect` и базовой компиляции.
Для симуляции следуйте [отдельной процедуре](references/simulation-debugging.md):
нужны свежие GUID приложения, target_id и проверенный режим устройства.
Сохраните путь рабочей копии перед закрытием; после теста завершите свою сессию.

Имена и аргументы инструментов, обработка ошибок и восстановление:
[persistent.md](references/persistent.md). Резервный адаптер регистрируется отдельно:
[mcp-setup.md](references/mcp-setup.md); его три исполняемых скрипта сохранены
без изменения. Его результаты и жизненный цикл отличаются от постоянного MCP.

## Проверки и этап 6

В обычных host-тестах Studio не запускается: 7 тестов сессии и 7 runtime guard-тестов.
CI выполняет только эти проверки и сборку на Windows. Native-тесты в `mcp/tests`
требуют Studio; запускайте их отдельно на включённой интерактивной Windows-сессии.
Включённая копия `analysis/side-scriptengine-check/API_Check_v6.project` — тестовый
TM750 fixture с IoStandard 3.5.15.0, не готовый проект машины.

В опубликованном пакете удалены неиспользуемые Vitest/tsx/uuid; v4 UUID создаёт
стандартный `crypto.randomUUID`. Совместимые зависимости обновлены в lockfile.
На 14.10.2026 `npm audit` и `npm audit --omit=dev` сообщают 0 уязвимостей.
Установленная рабочая сборка на исходной машине этим выпуском не заменялась.
Переносимая сборка также прошла native-проверку в Studio: 31 инструмент,
редактирование/диагностика/исправление/экспорт/повторное открытие, неизменность
исходника и штатное закрытие. [Результат проверки](mcp/docs/invt-package-validation-2026-10-14.json).

Native-проверка переносимого пакета:

```powershell
Set-Location (Join-Path $packageRoot 'mcp')
node tests/invt-live.cjs
```

Этап 6: через внутренний Core API в симуляции подтверждены breakpoint,
Step Over/Into/Out, позиция исходника, изменение переменных и глубины стека,
снятие собственной точки и Stop из HALT. Это исследовательский прототип;
публичных инструментов полноценного отладчика пока нет. Остаются привязка
произвольной строки ST, защита от устаревшего кода, повторные continue,
чужие точки, многозадачность/watchdog и локальные переменные кадров.
Подробности: [исследование](mcp/docs/invt-debugger-research.md),
[наблюдения](mcp/docs/invt-debugger-proof-2026-10-14.json),
[план](mcp/docs/invt-debugging-plan.md).

Воспроизведение фиксированного исследовательского опыта на своей копии:
`node tests/invt-debugger-research.cjs breakpoint_proof`. Он использует внутренние
API именно проверенной версии; его нельзя считать обычным MCP-инструментом.

Происхождение исходников и контрольные суммы — в [provenance.json](provenance.json).
MCP адаптирован из luke-harriman/Codesys-MCP; его [MIT license](mcp/LICENSE) сохранена.
Инструкции навыка переписаны для INVT по результатам испытаний. Локальная
конфигурация, секреты, DLL поставщика, временные сессии и журналы не включены.
