# INVTmatic Studio: навык и постоянный MCP

Пакет для разработки IEC 61131-3 ST в INVTmatic Studio: навык Codex,
44 инструмента постоянного MCP (v0.6), сохранённый резервный Python-адаптер и тесты.
Проверено на Windows с INVTmatic Studio V3.0.1.4, CODESYS core 3.5.20.60,
OnlineManager 3.5.20.61, Breakpoints 3.5.20.60, ScriptEngine 4.1.0.0, Node 24.19.0. На другой установке сначала проверьте
[совместимость](references/environment.md). Studio и её библиотеки в пакет не входят.

MCP создаёт собственное окно Studio и работает с копиями проектов. Доступны
редактирование/компиляция/экспорт ST, создание POU/GVL/DUT, циклических задач и
привязок программ, а также запуск и наблюдение **положительно проверенной симуляции**.
Восемь новых инструментов добавляют точки останова, позиции ST, состояние/стек
и Step Into/Over/Out. Ещё пять инструментов читают локальные значения текущих
кадров и создают/записывают/перечисляют/удаляют trace. Управление физическим ПЛК
и сетевой поиск не реализованы.

## Установка

### Короткий промпт для Codex

На другом компьютере скопируйте этот промпт в чат Codex:

```text
Установи навык invtmatic-studio вместе с постоянным MCP из https://github.com/IlistTeam/invtmatic-studio по инструкции README.md. Сначала уточни у меня, где сохранить репозиторий с MCP и какую папку использовать для проектов ПЛК. Используй выбранные пути, без предположений о буквах дисков. Размести навык в действующем каталоге skills Codex с учётом CODEX_HOME. Собери сервер, выполни тесты и зарегистрируй invtmatic-persistent для выбранной папки проектов. Сохрани остальные настройки Codex и проверь подключение MCP.
```

Папка репозитория с MCP и рабочая папка проектов выбираются при установке.
Репозиторий публичный;
для обычного клонирования авторизация GitHub не требуется.

### Установка вручную

Нужны установленная Studio с ScriptEngine, интерактивный сеанс Windows, Git,
Node/npm и Codex. Для резервного адаптера и guard-тестов нужен Python 3.10+.
Используйте реальные интерпретаторы, а не Windows Store aliases.

Клонируйте этот репозиторий в выбранную папку. Затем скопируйте только ресурсы
навыка в каталог навыков Codex. Пример PowerShell для **новой** установки:

```powershell
$packageRoot = Read-Host 'Полный путь к папке для репозитория и MCP'
git clone https://github.com/IlistTeam/invtmatic-studio.git $packageRoot
if ($LASTEXITCODE -ne 0) { throw 'Клонирование не выполнено' }
$packageRoot = (Resolve-Path -LiteralPath $packageRoot).Path
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$skillDestination = Join-Path $codexRoot 'skills\invtmatic-studio'
if (Test-Path -LiteralPath $skillDestination) { throw 'Навык уже установлен: сначала сравните версии' }
New-Item -ItemType Directory -Path $skillDestination -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $packageRoot 'SKILL.md') -Destination $skillDestination
foreach ($resource in @('agents', 'references', 'scripts')) {
    Copy-Item -LiteralPath (Join-Path $packageRoot $resource) -Destination $skillDestination -Recurse
}
```

Каталог навыка определяется по `CODEX_HOME`, либо по профилю текущего пользователя.
Код MCP остаётся в выбранном клоне; после регистрации этот клон нужен
для запуска сервера. Не переносите его без обновления регистрации.

Соберите MCP, используя lockfile:

```powershell
Set-Location (Join-Path $packageRoot 'mcp')
npm ci --ignore-scripts
npm run build
npm test
npm run test:guards
```

Зарегистрируйте сервер для выбранного рабочего каталога проектов. Если папки ещё
нет, пример создаст её. Сервер не читает проекты за пределами этого каталога:

```powershell
$projectRoot = Read-Host 'Полный путь к рабочей папке проектов ПЛК'
if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
}
$projectRoot = (Resolve-Path -LiteralPath $projectRoot).Path
$nodeExecutable = (Get-Command node -CommandType Application).Source
$serverEntrypoint = Join-Path $packageRoot 'mcp\dist\invt-server.js'
codex mcp add invtmatic-persistent -- $nodeExecutable $serverEntrypoint --workspace $projectRoot
```

Используется только `dist/invt-server.js`. Добавляйте или обновляйте одну секцию
конфигурации, сохраняя остальные серверы. Шаблон эквивалентного TOML: замените
значения в угловых скобках фактическими путями из переменных выше.

```toml
[mcp_servers.invtmatic-persistent]
command = '<полный путь к node.exe>'
args = ['<полный путь к invt-server.js>', '--workspace', '<полный путь к папке проектов ПЛК>']
startup_timeout_sec = 30
tool_timeout_sec = 180
```

Для `command` используйте `$nodeExecutable`, для `args` — `$serverEntrypoint` и
`$projectRoot`. При другой установке Studio
передайте `--exe` и `--profile` после проверки её окружения. Регистрация и MCP
инициализация Studio не запускают. После изменения кода пересоберите сервер и
переподключите MCP/чат: работающий процесс не перечитывает инструменты.
Синтаксис настройки: [документация Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Первый цикл работы

Попросите Codex использовать `$invtmatic-studio`. Проверьте наличие 44 инструментов
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

В обычных host-тестах Studio не запускается: 44 проверки: 9 сессии, 7 runtime, 14 debugger и 14 frames/trace.
CI выполняет только эти проверки и сборку на Windows. Native-тесты в `mcp/tests`
требуют Studio; запускайте их отдельно на включённой интерактивной Windows-сессии.
Включённая копия `analysis/side-scriptengine-check/API_Check_v6.project` — тестовый
TM750 fixture с IoStandard 3.5.15.0, не готовый проект машины.

В опубликованном пакете удалены неиспользуемые Vitest/tsx/uuid; v4 UUID создаёт
стандартный `crypto.randomUUID`. Совместимые зависимости обновлены в lockfile.
На 14.10.2026 `npm audit` и `npm audit --omit=dev` сообщают 0 уязвимостей.
Установленная рабочая сборка на исходной машине этим выпуском не заменялась.
Историческая сборка v0.4 также прошла native-проверку в Studio: 31 инструмент,
редактирование/диагностика/исправление/экспорт/повторное открытие, неизменность
исходника и штатное закрытие. [Результат проверки](mcp/docs/invt-package-validation-2026-10-14.json).

Native-проверка переносимого пакета:

```powershell
Set-Location (Join-Path $packageRoot 'mcp')
node tests/invt-live.cjs
```

Базовый отладчик этапа 6 реализован в v0.5.0: breakpoint, Step Over/Into/Out,
точные строки/колонки ST, защита поколений кода и соединения, повторные continue,
сохранность чужих определений и несколько задач проверены через MCP.
Новые инструменты появляются после пересборки и переподключения MCP/чата.

HALT приостанавливает выбранную задачу; другие задачи могут продолжать выполнение.
STOP из HALT требует явного `halt_behavior`: `finish_cycle` разрешает завершить
оставшиеся операторы цикла, `abort_cycle` может привести к exception STOP и
требует отдельного восстановления. Disconnect/close/session_stop без этого
выбора отказывают, сохраняя проект и значения. Не выбирайте поведение молча.
Потеря владельца/EOF применяет abort, без скрытого завершения цикла.

Подробности: [инструкции отладки](references/breakpoint-debugging.md),
[исследование](mcp/docs/invt-debugger-research.md),
[приёмка](mcp/docs/invt-debugger-validation-2026-10-14.json),
[план](mcp/docs/invt-debugging-plan.md).
MCP v0.6 проверен в отдельной копии TM750: локальные значения вложенных
функций до/после возврата, отказ старым дескрипторам даже при быстром повторном
попадании на ту же точку, запись trace с CSV-экспортом, выборочная очистка,
сохранение чужой записи и явное восстановление после потери связи.
Повторные рекурсивные кадры явно отклоняются: API не выбирает вызов однозначно.
Удаление конфигурации trace требует disconnect; MCP не выполняет logout молча.

Проверки разработки: 44 host-теста, 58 новых MCP-вызовов и 7 фиксированных проб;
регрессия 102 debugger и 116 runtime. Авария владельца и EOF во время записи
trace проверены отдельно. [Приёмка v0.6](mcp/docs/invt-v06-validation-2026-10-14.json).
Проверка переносимого пакета и текущий выпуск отмечаются в
[плане](mcp/docs/invt-debugging-plan.md). Прежние отчёты v0.4/v0.5 сохранены
как исторические результаты со своими исходными версиями и числами.

Проверка непосредственно через MCP чата тоже прошла: все 44 инструмента
доступны; 85 записанных вызовов испытали 13 инструментов отладки, локальных
переменных и trace, включая 19 ожидаемых защитных отказов. Две записи дали
по 29 отсчётов каждого сигнала, без переполнения; исходник сохранён, очистка
runtime и штатное закрытие Studio подтверждены.
[Реестр чата](mcp/docs/invt-v06-chat-registry-validation-2026-10-14.json),
[функциональная приёмка](mcp/docs/invt-v06-chat-debugger-validation-2026-10-14.json).

Уточнение навыка: Step Out может вернуть в продолжение строки вызова до
присваивания результата. Проверяйте текущую позицию и свежие значения после
следующего шага; [подробности](references/breakpoint-debugging.md).

Native-приёмка на копии fixture (из папки mcp, нужна установленная Studio):

```powershell
node tests/invt-debugger-live.cjs
node tests/invt-runtime-live.cjs
node tests/invt-advanced-live.cjs --extended
node tests/invt-recursive-frames-live.cjs
node tests/invt-debugger-lifecycle.cjs --trace
```

Перед чтением кадров или trace следуйте
[advanced-debugging.md](references/advanced-debugging.md). В обновлённом сервере
44 инструмента; старый чат может показывать 31 до обновления соединения/реестра.
Симуляция не проверяет реальные I/O, Modbus-устройства или EtherCAT-сервоприводы.

Происхождение исходников и контрольные суммы — в [provenance.json](provenance.json).
MCP адаптирован из luke-harriman/Codesys-MCP; его [MIT license](mcp/LICENSE) сохранена.
Инструкции навыка переписаны для INVT по результатам испытаний. Локальная
конфигурация, секреты, DLL поставщика, временные сессии и журналы не включены.
