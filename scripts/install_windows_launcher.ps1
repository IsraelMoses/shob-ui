param(
    [switch]$NoDesktop,
    [switch]$StartMenu
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PywLauncher = Join-Path $ProjectRoot "run_shob_ui.pyw"
$BatLauncher = Join-Path $ProjectRoot "run_shob_ui.bat"

if (-not (Test-Path $PywLauncher)) {
    throw "Missing launcher: $PywLauncher"
}

function Get-PythonWindowLauncher {
    $venvPythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
    if (Test-Path $venvPythonw) {
        return @{
            Target = $venvPythonw
            Arguments = "`"$PywLauncher`""
        }
    }

    $pyw = Get-Command "pyw.exe" -ErrorAction SilentlyContinue
    if ($pyw) {
        return @{
            Target = $pyw.Source
            Arguments = "-3 `"$PywLauncher`""
        }
    }

    $pythonw = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
    if ($pythonw) {
        return @{
            Target = $pythonw.Source
            Arguments = "`"$PywLauncher`""
        }
    }

    return @{
        Target = $BatLauncher
        Arguments = ""
    }
}

function New-ShobShortcut {
    param(
        [string]$ShortcutPath
    )

    $launcher = Get-PythonWindowLauncher
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $launcher.Target
    $shortcut.Arguments = $launcher.Arguments
    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.Description = "Start Shob UI"
    $shortcut.IconLocation = $launcher.Target
    $shortcut.Save()

    Write-Host "Created shortcut: $ShortcutPath"
}

if (-not $NoDesktop) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    New-ShobShortcut -ShortcutPath (Join-Path $desktop "Shob UI.lnk")
}

if ($StartMenu) {
    $startMenu = [Environment]::GetFolderPath("Programs")
    New-ShobShortcut -ShortcutPath (Join-Path $startMenu "Shob UI.lnk")
}

Write-Host "Done. You can now start Shob UI from the shortcut."
