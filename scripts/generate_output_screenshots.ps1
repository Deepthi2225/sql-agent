Add-Type -AssemblyName System.Drawing

function New-TextPng {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$Lines,
        [string]$Title = ""
    )

    $font = New-Object System.Drawing.Font("Consolas", 16, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $titleFont = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)

    $padding = 24
    $lineHeight = 30
    $maxLen = ($Lines | Measure-Object -Property Length -Maximum).Maximum
    if (-not $maxLen) { $maxLen = 20 }

    $titleHeight = 0
    if ($Title) { $titleHeight = 42 }

    $width = [Math]::Max(1180, [int]($maxLen * 10.2) + ($padding * 2))
    $height = ($Lines.Count * $lineHeight) + ($padding * 2) + $titleHeight

    $bmp = New-Object System.Drawing.Bitmap $width, $height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

    $bg = [System.Drawing.Color]::FromArgb(14, 23, 38)
    $fg = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(240, 244, 255))
    $accent = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(94, 234, 212))
    $muted = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(161, 174, 197))

    $g.Clear($bg)

    $y = $padding
    if ($Title) {
        $g.DrawString($Title, $titleFont, $accent, $padding, $y)
        $y += $titleHeight
        $g.DrawLine((New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(49, 62, 86), 1)), $padding, $y - 8, $width - $padding, $y - 8)
    }

    foreach ($line in $Lines) {
        $brush = if ($line.StartsWith("PS ") -or $line.StartsWith("> ")) { $accent } else { $fg }
        if ($line.StartsWith("INFO:") -or $line.StartsWith("VITE")) { $brush = $muted }
        $g.DrawString($line, $font, $brush, $padding, $y)
        $y += $lineHeight
    }

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)

    $g.Dispose()
    $bmp.Dispose()
    $font.Dispose()
    $titleFont.Dispose()
    $fg.Dispose()
    $accent.Dispose()
    $muted.Dispose()
}

$backendLines = @(
    "PS C:\\Sem6\\LLM\\sql_agent> c:/Sem6/LLM/sql_agent/.venv/Scripts/python.exe -m uvicorn web_api:app --host 127.0.0.1 --port 8000",
    "INFO:     Started server process [2540]",
    "INFO:     Waiting for application startup.",
    "INFO:     Application startup complete.",
    "INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)",
    'INFO:     127.0.0.1:53754 - "GET /api/capabilities HTTP/1.1" 200 OK'
)

$frontendLines = @(
    "PS C:\\Sem6\\LLM\\sql_agent\\frontend> npm run dev -- --host 127.0.0.1 --port 5173",
    "> sql-agent-frontend@1.0.0 dev",
    "> vite --host 127.0.0.1 --port 5173",
    "VITE v5.4.21  ready in 2205 ms",
    "Local:   http://127.0.0.1:5173/",
    "press h + enter to show help"
)

New-TextPng -Path "docs/screenshots/backend-output.png" -Lines $backendLines -Title "Backend Output Snapshot"
New-TextPng -Path "docs/screenshots/frontend-output.png" -Lines $frontendLines -Title "Frontend Output Snapshot"
Write-Host "Created docs/screenshots/backend-output.png"
Write-Host "Created docs/screenshots/frontend-output.png"
