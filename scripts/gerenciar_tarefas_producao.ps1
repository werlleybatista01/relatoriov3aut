param(
    [ValidateSet("Prepare", "Activate", "Rollback")]
    [string]$Mode,
    [string]$RepoDir
)

$ErrorActionPreference = "Stop"
$TaskName = "Atualizar Dashboard Almoxarifado V2"
$RepoDir = (Resolve-Path $RepoDir).Path.TrimEnd("\")
$StateFile = Join-Path $RepoDir ".migracao-dashboard-v2.json"
$OldAutomation = Join-Path $env:USERPROFILE "Desktop\automacao"

function Get-LegacyTasks {
    $oldBat = (Join-Path $OldAutomation "atualizar_silencioso.bat").ToLowerInvariant()
    $knownNames = @(
        "Atualizar Dashboard Almoxarifado",
        "Atualizar Dashboard Almoxarifado Modular"
    )

    @(Get-ScheduledTask | Where-Object {
        if ($_.TaskName -eq $TaskName) { return $false }
        if ($knownNames -contains $_.TaskName) { return $true }

        $actionText = ($_.Actions | ForEach-Object {
            "{0} {1}" -f $_.Execute, $_.Arguments
        }) -join " "
        return $actionText.ToLowerInvariant().Contains($oldBat)
    })
}

function Write-MigrationState($backupDir, $taskNames) {
    $state = [ordered]@{
        createdAt = (Get-Date).ToString("o")
        backupDir = $backupDir
        oldAutomation = $OldAutomation
        disabledTasks = @($taskNames)
    }
    $state | ConvertTo-Json -Depth 4 | Set-Content -Path $StateFile -Encoding UTF8
}

function Restore-LegacyTasks {
    if (-not (Test-Path $StateFile)) {
        Write-Host "Nenhum registro de migração foi encontrado."
        return
    }
    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
    foreach ($name in @($state.disabledTasks)) {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($task) {
            Enable-ScheduledTask -InputObject $task | Out-Null
            Write-Host "Tarefa anterior reativada: $name"
        }
    }
}

if ($Mode -eq "Prepare") {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDir = Join-Path $env:USERPROFILE "Desktop\backup_automacao_dashboard_$stamp"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

    if (Test-Path $OldAutomation) {
        Copy-Item -Path (Join-Path $OldAutomation "*") -Destination $backupDir -Recurse -Force
    }

    $legacyTasks = @(Get-LegacyTasks)
    $taskReport = @($legacyTasks | ForEach-Object {
        [ordered]@{
            name = $_.TaskName
            path = $_.TaskPath
            state = [string]$_.State
            actions = @($_.Actions | ForEach-Object {
                [ordered]@{
                    execute = $_.Execute
                    arguments = $_.Arguments
                    workingDirectory = $_.WorkingDirectory
                }
            })
        }
    })
    $taskReport | ConvertTo-Json -Depth 6 | Set-Content `
        -Path (Join-Path $backupDir "tarefas_anteriores.json") -Encoding UTF8

    Write-MigrationState $backupDir @($legacyTasks.TaskName)
    foreach ($task in $legacyTasks) {
        Disable-ScheduledTask -InputObject $task | Out-Null
        Write-Host "Tarefa anterior pausada: $($task.TaskName)"
    }
    Write-Host "Backup da automação anterior: $backupDir"
    exit 0
}

if ($Mode -eq "Activate") {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $batchPath = Join-Path $RepoDir "atualizar_silencioso.bat"
    $arguments = "/d /c `"`"$batchPath`"`""
    $action = New-ScheduledTaskAction `
        -Execute $env:ComSpec `
        -Argument $arguments `
        -WorkingDirectory $RepoDir
    $trigger = New-ScheduledTaskTrigger `
        -Once `
        -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 5)
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 4)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Atualiza e publica os dados pseudonimizados do dashboard a cada 5 minutos." `
        -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Tarefa V2 criada e iniciada: $TaskName"
    exit 0
}

if ($Mode -eq "Rollback") {
    $current = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($current) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Tarefa V2 removida: $TaskName"
    }
    Restore-LegacyTasks
    exit 0
}
