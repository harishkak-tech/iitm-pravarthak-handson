param(
    [string]$SourceDir = (Join-Path $PSScriptRoot "..\docs\corpus"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\docs\corpus_pdf_styled")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$ascii = [System.Text.Encoding]::ASCII

function Escape-PdfText([string]$Text) {
    return $Text.Replace('\', '\\').Replace('(', '\(').Replace(')', '\)')
}

function Wrap-Paragraph([string]$Text, [int]$Width = 92) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return @('') }

    $words = $Text.Trim() -split '\s+'
    $lines = @()
    $current = ''
    foreach ($word in $words) {
        if ($current.Length -eq 0) {
            $current = $word
        } elseif (($current.Length + 1 + $word.Length) -le $Width) {
            $current += " $word"
        } else {
            $lines += $current
            $current = $word
        }
    }
    if ($current.Length -gt 0) { $lines += $current }
    return $lines
}

function New-Records([string[]]$RawLines) {
    $records = @()
    $headingSeen = $false
    for ($index = 0; $index -lt $RawLines.Count; $index++) {
        $line = [string]$RawLines[$index]

        if ($line -match '^[-=]{3,}$') { continue }
        if ([string]::IsNullOrWhiteSpace($line)) {
            $records += [PSCustomObject]@{ Text = ''; Style = 'spacer' }
            continue
        }

        $nextIsRule = $false
        if ($index + 1 -lt $RawLines.Count) {
            $nextIsRule = ([string]$RawLines[$index + 1]) -match '^[-=]{3,}$'
        }

        if ($nextIsRule) {
            $style = if ($headingSeen) { 'heading' } else { 'title' }
            $records += [PSCustomObject]@{ Text = $line.Trim(); Style = $style }
            $headingSeen = $true
            continue
        }

        foreach ($wrappedLine in (Wrap-Paragraph $line)) {
            $records += [PSCustomObject]@{ Text = $wrappedLine; Style = 'body' }
        }
    }
    return $records
}

function New-Pdf([object[]]$Records) {
    $pages = @()
    $current = @()
    $remaining = 742

    foreach ($record in $Records) {
        $height = switch ($record.Style) {
            'title' { 28 }
            'heading' { 22 }
            'spacer' { 9 }
            default { 14 }
        }

        if ($current.Count -gt 0 -and ($remaining - $height) -lt 45) {
            $pages += ,$current
            $current = @()
            $remaining = 742
        }
        $current += $record
        $remaining -= $height
    }
    if ($current.Count -gt 0) { $pages += ,$current }

    $objects = @()
    $objects += '<< /Type /Catalog /Pages 2 0 R >>'
    $pageObjectStart = 5
    $contentObjectStart = $pageObjectStart + $pages.Count
    $kids = ((0..($pages.Count - 1)) | ForEach-Object { "$($pageObjectStart + $_) 0 R" }) -join ' '
    $objects += "<< /Type /Pages /Kids [$kids] /Count $($pages.Count) >>"
    $objects += '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
    $objects += '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>'

    $streams = @()
    for ($pageIndex = 0; $pageIndex -lt $pages.Count; $pageIndex++) {
        $contentNumber = $contentObjectStart + $pageIndex
        $objects += "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents $contentNumber 0 R >>"

        $commands = @()
        $y = 742
        foreach ($record in $pages[$pageIndex]) {
            switch ($record.Style) {
                'title' {
                    $commands += "BT /F2 18 Tf 50 $y Td ($(Escape-PdfText $record.Text)) Tj ET"
                    $y -= 28
                }
                'heading' {
                    $y -= 5
                    $commands += "BT /F2 12 Tf 50 $y Td ($(Escape-PdfText $record.Text)) Tj ET"
                    $y -= 22
                }
                'spacer' { $y -= 9 }
                default {
                    $commands += "BT /F1 10 Tf 50 $y Td ($(Escape-PdfText $record.Text)) Tj ET"
                    $y -= 14
                }
            }
        }
        $pageLabel = "Page $($pageIndex + 1) of $($pages.Count)"
        $commands += "BT /F1 8 Tf 500 25 Td ($(Escape-PdfText $pageLabel)) Tj ET"
        $streams += ($commands -join "`n")
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

Get-ChildItem -LiteralPath $SourceDir -Filter '*.txt' | Sort-Object Name | ForEach-Object {
    $rawLines = Get-Content -LiteralPath $_.FullName
    $records = New-Records $rawLines
    $target = Join-Path $OutputDir ($_.BaseName + '.pdf')
    [System.IO.File]::WriteAllBytes($target, (New-Pdf $records))
    Write-Output "Created $target"
}
