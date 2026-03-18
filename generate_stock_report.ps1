$ErrorActionPreference = 'Stop'

function Escape-XmlText([string]$text) {
  if ($null -eq $text) { return '' }
  $escaped = [System.Security.SecurityElement]::Escape($text)
  return $escaped -replace "`r?`n", '</w:t></w:r></w:p><w:p><w:r><w:t xml:space="preserve">'
}

function New-Docx([string]$outputPath, [string[]]$paragraphs) {
  Add-Type -AssemblyName System.IO.Compression.FileSystem

  $tempRoot = Join-Path $env:TEMP ("stock_report_" + [guid]::NewGuid().ToString('N'))
  $null = New-Item -ItemType Directory -Path $tempRoot
  $null = New-Item -ItemType Directory -Path (Join-Path $tempRoot '_rels')
  $null = New-Item -ItemType Directory -Path (Join-Path $tempRoot 'word')

  @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'@ | Out-File -LiteralPath (Join-Path $tempRoot '[Content_Types].xml') -Encoding utf8

  @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'@ | Out-File -LiteralPath (Join-Path $tempRoot '_rels\.rels') -Encoding utf8

  $body = foreach ($paragraph in $paragraphs) {
    $escaped = Escape-XmlText $paragraph
    "<w:p><w:r><w:t xml:space=`"preserve`">$escaped</w:t></w:r></w:p>"
  }

  $documentXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
 xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
 xmlns:wne="http://schemas.microsoft.com/office/2006/wordml"
 xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
 mc:Ignorable="w14 wp14">
  <w:body>
    $($body -join "`n    ")
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"@
  $documentXml | Out-File -LiteralPath (Join-Path $tempRoot 'word\document.xml') -Encoding utf8

  if (Test-Path $outputPath) {
    Remove-Item $outputPath -Force
  }
  [System.IO.Compression.ZipFile]::CreateFromDirectory($tempRoot, $outputPath)
  Remove-Item $tempRoot -Recurse -Force
}

$analysisPath = 'C:\Users\qinso\Desktop\Codex\watch_analysis.json'
$rows = Get-Content $analysisPath -Raw | ConvertFrom-Json

$names = @{
  '601211' = 'GTHT'; '601108' = 'CAITONG'; '601208' = 'DONGCAI'; '301132' = 'MANKUN'
  '688428' = 'INNOCARE'; '000823' = 'ULTRASONIC'; '000758' = 'NONFERROUS'; '300376' = 'EAST'
  '300303' = 'JUFY'; '002324' = 'PULITE'; '300566' = 'JIZHI'; '300115' = 'EWPT'
  '002463' = 'WUS'; '300442' = 'RUNZE'; '002350' = 'BJKR'; '002600' = 'LINGYI'
  '600522' = 'ZTT'; '300360' = 'YUHUA'; '300319' = 'MAXSCEND'; '300328' = 'YIAN'
  '300433' = 'LENS'; '600577' = 'JINGDA'; '002236' = 'DAHUA'; '600392' = 'SHENGHE'
  '131810' = 'R-131810'; '204001' = 'GC001'; '300456' = 'SILEX'; '300149' = 'RZMED'
  '000858' = 'WULIANGYE'; '301358' = 'HNYN'; '600526' = 'FEIDA'; '002402' = 'HETAI'
  '001280' = 'CNU'; '002085' = 'WFOV'; '688137' = 'NOVOPRO'; '002606' = 'DLDC'
  '600900' = 'CYPC'; '600089' = 'TBEA'; '000060' = 'CMLN'; '600312' = 'PINGGAO'
}

$sectorNotes = @{
  '601211' = 'Broker theme; watch capital-market activity and wealth-management beta.'
  '601108' = 'Regional broker; earnings are sensitive to turnover and proprietary book.'
  '601208' = 'Electronic materials and new-energy materials.'
  '301132' = 'Public-web checks focus on PCB and auto-electronics exposure.'
  '688428' = 'Innovative-drug / biotech pipeline progression remains the key driver.'
  '000823' = 'PCB and electronic-component cycle recovery.'
  '000758' = 'Non-ferrous resources and overseas mining projects.'
  '300376' = 'Data-center power, storage and energy-equipment theme.'
  '300303' = 'MLED / display / vehicle-display theme remains active.'
  '002324' = 'Modified plastics and new materials.'
  '300566' = 'Optical film and functional-film demand.'
  '300115' = 'Precision structures and consumer electronics.'
  '002463' = 'High-end PCB, AI server and networking demand.'
  '300442' = 'IDC and computing infrastructure.'
  '002350' = 'Public-web checks highlight the planned control acquisition of Pride.'
  '002600' = 'Precision manufacturing for consumer electronics and AI terminals.'
  '600522' = 'Submarine cable, optical products and power-supply chain.'
  '300360' = 'Smart-meter and grid-upgrade direction.'
  '300319' = 'Inductors and RF devices.'
  '300328' = 'Magnesium-aluminum lightweight materials.'
  '300433' = 'Cover glass and structural parts.'
  '600577' = 'Magnet wire and copper processing.'
  '002236' = 'Security and digital solutions.'
  '600392' = 'Rare-earth resource and material beta.'
  '131810' = 'Reverse repo tool; driven mainly by short-end funding rates.'
  '204001' = 'One-day reverse repo tool; focus on money-market yield.'
  '300456' = 'MEMS and semiconductor devices.'
  '300149' = 'CRO / AI-for-drug-discovery topic adds event-driven volatility.'
  '000858' = 'High-end baijiu demand, channel inventory and wholesale-price trend.'
  '301358' = 'LFP cathode materials.'
  '600526' = 'Environmental equipment and project-driven orders.'
  '002402' = 'Intelligent controllers for appliance / auto / storage.'
  '001280' = 'Nuclear-power and uranium-resource theme.'
  '002085' = 'Auto parts and low-altitude-economy theme.'
  '688137' = 'Recombinant protein and life-science reagents.'
  '002606' = 'UHV and grid-investment beneficiary.'
  '600900' = 'Hydropower utility with dividend stability.'
  '600089' = 'Renewable energy, transformers and overseas EPC.'
  '000060' = 'Lead, zinc and copper resource beta.'
  '600312' = 'UHV switchgear and grid tender activity.'
}

$today = [datetime]'2026-03-12'

function Get-Score($row) {
  $score = [int]$row.Strength
  if ($row.Ret20 -gt 20) { $score += 2 }
  elseif ($row.Ret20 -gt 10) { $score += 1 }
  if ($row.Close -gt $row.MA20) { $score += 1 }
  if ($row.Close -lt $row.MA20 -and $row.Ret20 -lt 0) { $score -= 1 }
  return $score
}

function Get-Level($score, [int]$daysOld, [string]$trend) {
  if ($daysOld -gt 20) { return 'C-Observe' }
  if ($score -ge 7 -and $trend -eq '多头排列') { return 'A-HighConviction' }
  if ($score -ge 5) { return 'B-PositiveWatch' }
  if ($score -ge 3) { return 'C-Observe' }
  return 'D-Cautious'
}

$enriched = foreach ($row in $rows) {
  if (-not $row.HasData) { continue }
  $dateText = [string]$row.Date
  $dateValue = [datetime]::ParseExact($dateText, 'yyyyMMdd', $null)
  $daysOld = ($today - $dateValue).Days
  $score = Get-Score $row
  $level = Get-Level $score $daysOld $row.Trend
  [PSCustomObject]@{
    Code = $row.Code
    Name = $names[$row.Code]
    Date = $dateValue
    DaysOld = $daysOld
    Close = [double]$row.Close
    MA5 = [double]$row.MA5
    MA10 = [double]$row.MA10
    MA20 = [double]$row.MA20
    MA60 = [double]$row.MA60
    Ret20 = [double]$row.Ret20
    Ret60 = [double]$row.Ret60
    Trend = $row.Trend
    Score = $score
    Level = $level
    Note = $sectorNotes[$row.Code]
  }
}

$sorted = $enriched | Sort-Object `
  @{Expression = { switch -Wildcard ($_.Level) { 'A*' { 1 } 'B*' { 2 } 'C*' { 3 } default { 4 } } }}, `
  @{Expression = 'Score'; Descending = $true}, `
  @{Expression = 'Ret20'; Descending = $true}

$paragraphs = New-Object System.Collections.Generic.List[string]
$paragraphs.Add('Watchlist Analysis Report')
$paragraphs.Add('Generated on: 2026-03-12')
$paragraphs.Add('Technical metrics come from local cached daily bars in the China Merchants Securities client. Internet notes are based on quick public-web checks plus sector summaries. Some cached series are not updated to 2026-03-12, so same-day trading decisions still need a live re-check.')
$paragraphs.Add('Sorting rule: recommendation tier first, then composite score and 20-day return.')
$paragraphs.Add('')
$paragraphs.Add('1. Key conclusions')

$topLines = $sorted | Select-Object -First 8 | ForEach-Object {
  "{0} {1}({2}): {3}, close {4}, 20d {5}%, MA5/10/20 = {6}/{7}/{8}." -f $_.Level, $_.Name, $_.Code, $_.Trend, $_.Close, $_.Ret20, $_.MA5, $_.MA10, $_.MA20
}
foreach ($line in $topLines) { $paragraphs.Add($line) }

$paragraphs.Add('')
$paragraphs.Add('2. Ranked stock details')

$index = 1
foreach ($item in $sorted) {
  $freshness = if ($item.DaysOld -le 3) { 'fresh data' } elseif ($item.DaysOld -le 10) { 'slightly stale' } else { 'stale data' }
  $summary = '{0}. {1} | {2}({3}) | close {4} | trend {5} | MA5/10/20/60 {6}/{7}/{8}/{9} | 20d {10}% | 60d {11}% | {12}' -f `
    $index, $item.Level, $item.Name, $item.Code, $item.Close, $item.Trend, $item.MA5, $item.MA10, $item.MA20, $item.MA60, $item.Ret20, $item.Ret60, $freshness
  $paragraphs.Add($summary)

  $action = switch -Wildcard ($item.Level) {
    'A*' { 'Action: keep on the priority list; prefer pullback-hold or fresh breakout confirmation.' }
    'B*' { 'Action: active watch; wait for a breakout above prior high or a successful retest of key moving averages.' }
    'C*' { 'Action: observation only; avoid chasing until trend alignment improves.' }
    default { 'Action: cautious; only reconsider if a new catalyst or clear reversal appears.' }
  }
  $paragraphs.Add($action)
  $paragraphs.Add('Internet / sector note: ' + $item.Note)
  $paragraphs.Add('')
  $index++
}

$paragraphs.Add('3. Notes')
$paragraphs.Add('1. Reverse-repo instruments (131810 and 204001) are cash-management tools, so they are evaluated differently from equities.')
$paragraphs.Add('2. Before any live trade, re-check A and B names inside the broker client for intraday tape, turnover ratio, order book and latest announcements.')
$paragraphs.Add('3. This report is best used as a first-pass ranking of the watchlist rather than a direct trading instruction.')

$desktop = [Environment]::GetFolderPath('Desktop')
$outputPath = Join-Path $desktop 'watchlist_analysis_report.docx'
New-Docx -outputPath $outputPath -paragraphs $paragraphs
Write-Output $outputPath
