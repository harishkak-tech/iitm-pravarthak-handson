param(
    [string]$SourceDir = (Join-Path $PSScriptRoot "..\docs\corpus"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\docs\corpus_pdf")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Escape-PdfText([string]$Text) {
    return $Text.Replace('\', '\\').Replace('(', '\(').Replace(')', '\)')
}

function New-Pdf([string[]]$Lines) {
    $ascii = [System.Text.Encoding]::ASCII
    $pageLines = 48
    $pages = @()

    for ($start = 0; $start -lt $Lines.Count; $start += $pageLines) {
        $end = [Math]::Min($start + $pageLines, $Lines.Count)
        $pages += ,($Lines[$start..($end - 1)])
    }

    $objects = @()
    $objects += "<< /Type /Catalog /Pages 2 0 R >>"

    $pageObjectStart = 4
    $contentObjectStart = $pageObjectStart + $pages.Count
    $kids = ((0..($pages.Count - 1)) | ForEach-Object { "$(($pageObjectStart + $_)) 0 R" }) -join ' '
    $objects += "<< /Type /Pages /Kids [$kids] /Count $($pages.Count) >>"
    $objects += "<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"

    $streams = @()
    for ($pageIndex = 0; $pageIndex -lt $pages.Count; $pageIndex++) {
        $contentNumber = $contentObjectStart + $pageIndex
        $objects += "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents $contentNumber 0 R >>"

        $commands = @("BT", "/F1 9 Tf", "50 750 Td")
        foreach ($line in $pages[$pageIndex]) {
            $safeLine = Escape-PdfText ([string]$line)
            $commands += "($safeLine) Tj"
            $commands += "0 -14 Td"
        }
        $commands += "ET"
        $stream = ($commands -join "`n")
        $streams += $stream
    }

    foreach ($stream in $streams) {
        $length = $ascii.GetByteCount($stream)
        $objects += "<< /Length $length >>`nstream`n$stream`nendstream"
    }

    $pdf = "%PDF-1.4`n"
    $offsets = @(0)
    for ($index = 0; $index -lt $objects.Count; $index++) {
        $offsets += $ascii.GetByteCount($pdf)
        $pdf += "$($index + 1) 0 obj`n$($objects[$index])`nendobj`n"
    }

    $xrefOffset = $ascii.GetByteCount($pdf)
    $pdf += "xref`n0 $($objects.Count + 1)`n"
    $pdf += "0000000000 65535 f `n"
    for ($index = 1; $index -lt $offsets.Count; $index++) {
        $pdf += ("{0:D10} 00000 n `n" -f $offsets[$index])
    }
    $pdf += "trailer`n<< /Size $($objects.Count + 1) /Root 1 0 R >>`nstartxref`n$xrefOffset`n%%EOF`n"
    return $ascii.GetBytes($pdf)
}

Get-ChildItem -LiteralPath $SourceDir -Filter "*.txt" | Sort-Object Name | ForEach-Object {
    $rawLines = Get-Content -LiteralPath $_.FullName
    $wrapped = @()
    foreach ($line in $rawLines) {
        if ($line.Length -le 92) {
            $wrapped += $line
            continue
        }

        $remaining = $line
        while ($remaining.Length -gt 92) {
            $breakAt = $remaining.LastIndexOf(' ', 92)
            if ($breakAt -lt 1) { $breakAt = 92 }
            $wrapped += $remaining.Substring(0, $breakAt)
            $remaining = $remaining.Substring($breakAt).TrimStart()
        }
        $wrapped += $remaining
    }

    $target = Join-Path $OutputDir ($_.BaseName + ".pdf")
    [System.IO.File]::WriteAllBytes($target, (New-Pdf $wrapped))
    Write-Output "Created $target"
}
