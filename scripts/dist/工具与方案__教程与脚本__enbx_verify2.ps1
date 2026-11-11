# =====================================================================
# enbx_verify2.ps1  --  Seewo EasiNote courseware screenshot verifier (v2.2)
# Replaces enbx_verify.ps1.  KEY DIFFERENCE: it NEVER kills EasiNote.
# It reuses the already-logged-in instance, opens the courseware copy as a
# new tab, turns pages and captures PrintWindow PNGs.
#
# WHY THIS FILE IS PURE ASCII:
#   Windows PowerShell 5.1 reads a .ps1 without a BOM as the system ANSI
#   code page (GBK here), which corrupts any Chinese literal.  Every
#   Chinese string this script needs is rebuilt from Unicode code points
#   at runtime (see the U function).  Do not paste Chinese into this file.
#
# NAVIGATION FACTS (probed 2026-09-29 on EasiNote 5.2.4.9838):
#   EDIT mode   : page indicator = Text with AutomationId=SlideIndexTextBlock,
#                 Name like "courseware page 31 of 35" (Chinese);
#                 left slide list = ListItem, Name "page N" (exact jump).
#   PRESENT mode: a separate fullscreen top-level window with
#                 NextButton(Chinese label) / PreviousButton, and an "n / N"
#                 page indicator in the bottom toolbar.
#
# RED LINES: read-only use of EasiNote.  No Stop-Process, no sync/save.
# =====================================================================
param(
  [Parameter(Mandatory=$true)][string]$Enbx,
  [string]$OutDir = "",
  [string]$Pages = "30,31",
  [int]$AnimPerPage = 0,
  [int]$LoadWait = 120,
  [int]$ClickWaitMs = 900,
  [int]$AssumeStartPage = 1,
  [string]$Exe = "D:\app\work\seewo\EasiNote5\EasiNote5_5.2.4.9838\Main\EasiNote.exe",
  [string]$OnlyHwnd = "",
  [switch]$NoLaunch,
  [switch]$NoPreviewClick,
  [switch]$Present
)
$ErrorActionPreference = "Continue"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$TAB = [string][char]9

# --- Chinese literals rebuilt from code points (ASCII-safe source) ---
function U([int[]]$c) { -join ($c | ForEach-Object { [char]$_ }) }
$T_NEXT    = U @(0x4E0B,0x4E00,0x9875)
$T_PREV    = U @(0x4E0A,0x4E00,0x9875)
$T_PREVIEW = U @(0x76F4,0x63A5,0x9884,0x89C8)
$T_DI      = U @(0x7B2C)
$T_YE      = U @(0x9875)
$RX_PAGENUM  = '^\s*(\d+)\s*/\s*(\d+)\s*$'
$RX_LISTITEM = ('^' + $T_DI + '\s*(\d+)\s*' + $T_YE + '$')
$RX_PAGE_CN  = ($T_DI + '\s*(\d+)\s*' + $T_YE)

# --- native helpers: capture + send Esc ---
$cs = @'
using System;
using System.Runtime.InteropServices;
using System.Drawing;
public class WinCap2 {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  public static int Cap(IntPtr hwnd, string path, uint flags) {
    RECT r; GetWindowRect(hwnd, out r);
    int w = r.Right - r.Left, h = r.Bottom - r.Top;
    if (w <= 0 || h <= 0) return -1;
    using (Bitmap bmp = new Bitmap(w, h)) {
      using (Graphics g = Graphics.FromImage(bmp)) {
        IntPtr hdc = g.GetHdc();
        PrintWindow(hwnd, hdc, flags);
        g.ReleaseHdc(hdc);
      }
      long dark = 0, total = 0;
      for (int y = 0; y < h; y += 7) {
        for (int x = 0; x < w; x += 7) {
          Color c = bmp.GetPixel(x, y); total++;
          if (c.R < 16 && c.G < 16 && c.B < 16) dark++;
        }
      }
      bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png);
      return (int)(dark * 100 / (total == 0 ? 1 : total));
    }
  }
  public static void SendEsc(IntPtr h) {
    ShowWindow(h, 5); SetForegroundWindow(h); System.Threading.Thread.Sleep(400);
    keybd_event(0x1B, 0, 0, UIntPtr.Zero); keybd_event(0x1B, 0, 2, UIntPtr.Zero);
  }
}
'@
Add-Type -TypeDefinition $cs -ReferencedAssemblies System.Drawing

# --- UIA helpers ---
function Get-EasiNoteRoots {
  $procs = @(Get-Process EasiNote -ErrorAction SilentlyContinue)
  if ($procs.Count -eq 0) { return @() }
  $pids = @($procs | ForEach-Object { $_.Id })
  $res = @()
  $kids = [System.Windows.Automation.AutomationElement]::RootElement.FindAll(
    [System.Windows.Automation.TreeScope]::Children,
    [System.Windows.Automation.Condition]::TrueCondition)
  for ($i = 0; $i -lt $kids.Count; $i++) {
    $w = $kids.Item($i)
    try { if ($pids -contains $w.Current.ProcessId) { $res += $w } } catch {}
  }
  return $res
}
function Desc($el) {
  try { return $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition) }
  catch { return $null }
}
function Invoke-El($el) {
  if ($el -eq $null) { return $false }
  try { $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); return $true } catch {}
  try { $el.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select(); return $true } catch {}
  try { $el.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern).DoDefaultAction(); return $true } catch {}
  return $false
}
function Select-El($el) {
  if ($el -eq $null) { return $false }
  try { $el.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select(); return $true } catch {}
  try { $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); return $true } catch {}
  try { $el.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern).DoDefaultAction(); return $true } catch {}
  return $false
}
function Find-ByNames($rt, $names, $aids) {
  $all = Desc $rt
  if ($all -eq $null) { return $null }
  for ($i = 0; $i -lt $all.Count; $i++) {
    $e = $null
    try { $e = $all.Item($i) } catch { continue }
    try {
      if ($names -contains $e.Current.Name) { return $e }
      if ($aids -contains $e.Current.AutomationId) { return $e }
    } catch {}
  }
  return $null
}
function Find-Next($rt) { return Find-ByNames $rt @($T_NEXT) @('NextButton','PageRight') }
function Find-Prev($rt) { return Find-ByNames $rt @($T_PREV) @('PageLeft','PrevButton') }
function Find-Display($rt) { return Find-ByNames $rt @() @('DisplayButton') }
function Find-Preview($rt) {
  $all = Desc $rt
  if ($all -eq $null) { return $null }
  for ($i = 0; $i -lt $all.Count; $i++) {
    $e = $null
    try { $e = $all.Item($i) } catch { continue }
    try {
      if ($e.Current.ControlType.ProgrammaticName -eq 'ControlType.Button' -and $e.Current.Name -like ('*' + $T_PREVIEW + '*')) { return $e }
    } catch {}
  }
  return $null
}
function Get-PageNum($rt) {
  $all = Desc $rt
  if ($all -eq $null) { return -1 }
  $best = -1
  for ($i = 0; $i -lt $all.Count; $i++) {
    $e = $null
    try { $e = $all.Item($i) } catch { continue }
    try {
      $n = $e.Current.Name
      $aid = $e.Current.AutomationId
      $ct = $e.Current.ControlType.ProgrammaticName
      if ($aid -eq 'SlideIndexTextBlock' -and $n -match $RX_PAGE_CN) { return [int]$Matches[1] }
      if ($best -lt 0 -and $n -match $RX_PAGENUM) { $best = [int]$Matches[1] }
      if ($best -lt 0 -and $ct -ne 'ControlType.ListItem' -and $n -match $RX_PAGE_CN) { $best = [int]$Matches[1] }
    } catch {}
  }
  return $best
}
function Find-PageListItem($rt, [int]$pg) {
  $all = Desc $rt
  if ($all -eq $null) { return $null }
  for ($i = 0; $i -lt $all.Count; $i++) {
    $e = $null
    try { $e = $all.Item($i) } catch { continue }
    try {
      if ($e.Current.ControlType.ProgrammaticName -ne 'ControlType.ListItem') { continue }
      $n = $e.Current.Name
      if ($n -match $RX_LISTITEM -and [int]$Matches[1] -eq $pg) { return $e }
      if ($n -match ('^\s*' + $pg + '\s*$')) { return $e }
    } catch {}
  }
  return $null
}
function Find-EditWindow {
  foreach ($w in @(Get-EasiNoteRoots)) {
    $all = Desc $w
    if ($all -eq $null) { continue }
    for ($i = 0; $i -lt $all.Count; $i++) {
      try {
        $e = $all.Item($i)
        if ($e.Current.AutomationId -eq 'SlideIndexTextBlock') { return $w }
      } catch {}
    }
  }
  return $null
}
function Find-PresentWindow {
  foreach ($w in @(Get-EasiNoteRoots)) {
    $nx = Find-ByNames $w @($T_NEXT) @('NextButton')
    if ($nx -ne $null) {
      $aid = ''
      try { $aid = $nx.Current.AutomationId } catch {}
      if ($aid -eq 'NextButton') { return $w }
    }
  }
  return $null
}
function Shoot([string]$path) {
  $d = [WinCap2]::Cap($hwnd, $path, 2)
  if ($d -lt 0) { return 'BAD_RECT' }
  if ($d -gt 98) {
    $d2 = [WinCap2]::Cap($hwnd, $path, 0)
    if ($d2 -ge 0 -and $d2 -le 98) { return 'OK_PW0' }
    return 'BLACK'
  }
  return 'OK'
}
function Go-Page([int]$pg) {
  $cur = Get-PageNum $root
  if ($cur -eq $pg) { return 'already' }
  $li = Find-PageListItem $root $pg
  if ($li -ne $null) {
    try { $li.GetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern).ScrollIntoView() } catch {}
    Start-Sleep -Milliseconds 250
    Select-El $li | Out-Null
    for ($k = 0; $k -lt 4; $k++) {
      Start-Sleep -Milliseconds 500
      if ((Get-PageNum $root) -eq $pg) { return 'list' }
    }
  }
  if ($cur -gt $pg -and $prev -ne $null) {
    for ($g = 0; $g -lt 400; $g++) {
      if ((Get-PageNum $root) -eq $pg) { return 'prev' }
      Invoke-El $prev | Out-Null; Start-Sleep -Milliseconds 300
    }
    return 'miss'
  }
  $g = 0
  $blind = [Math]::Max(0, $pg - $AssumeStartPage)
  while ($g -lt 400) {
    $c = Get-PageNum $root
    if ($c -eq $pg) { if ($blind -gt 0 -and $g -le $blind) { return 'blind+next' }; return 'next' }
    if ($c -lt 0 -and $g -ge $blind) { return 'blind' }
    Invoke-El $next | Out-Null; Start-Sleep -Milliseconds 300; $g++
  }
  return 'miss'
}

# --- resolve output directory ---
$base = [System.IO.Path]::GetFileNameWithoutExtension($Enbx)
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path 'C:\Users\XYX80\Downloads\enbx-verify' $base }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$shotsPath = Join-Path $OutDir 'shots.txt'
$infoPath  = Join-Path $OutDir 'run_info.txt'

# --- snapshot existing EasiNote windows, then launch WITHOUT killing ---
$pre = @()
foreach ($w in @(Get-EasiNoteRoots)) { $h = $w.Current.NativeWindowHandle; if ($h -ne 0) { $pre += [int]$h } }
Write-Output ('PRE_HWNDS ' + ($pre -join ','))
if (-not $NoLaunch) {
  try {
    Start-Process -FilePath $Exe -ArgumentList ('"{0}"' -f $Enbx) | Out-Null
    Write-Output 'LAUNCHED (no process killed)'
  } catch { Write-Output ('LAUNCH_FAIL ' + $_.Exception.Message) }
}

# --- poll for the edit window (page indicator, or a Next control) ---
$root = $null; $hwnd = $null; $next = $null; $prev = $null
$previewDone = $false
$deadline = (Get-Date).AddSeconds($LoadWait)
while ((Get-Date) -lt $deadline) {
  $roots = @(Get-EasiNoteRoots)
  if (-not $NoPreviewClick -and -not $previewDone) {
    foreach ($w in $roots) {
      $pb = Find-Preview $w
      if ($pb -ne $null) { if (Invoke-El $pb) { Write-Output 'CLICK_PREVIEW'; $previewDone = $true; Start-Sleep -Seconds 2 } }
    }
  }
  $ew = Find-EditWindow
  if ($ew -ne $null) { $root = $ew }
  elseif ($OnlyHwnd -ne '') {
    foreach ($w in $roots) { if ([int]$w.Current.NativeWindowHandle -eq [int]$OnlyHwnd) { $root = $w } }
  } else {
    foreach ($w in $roots) { if ((Find-Next $w) -ne $null -and (Find-Display $w) -ne $null) { $root = $w; break } }
  }
  if ($root -ne $null) {
    $hwnd = [IntPtr]$root.Current.NativeWindowHandle
    $next = Find-Next $root; $prev = Find-Prev $root
    Write-Output ('GOT_EDIT_WINDOW hwnd=' + $hwnd + ' page=' + (Get-PageNum $root) + ' title=' + $root.Current.Name)
    break
  }
  Start-Sleep -Seconds 3
}

if ($root -eq $null) {
  Write-Output 'NO_EDIT_WINDOW'
  $diag = @()
  $diag += 'No EasiNote editor window was found within ' + $LoadWait + ' s.'
  $diag += 'pre-existing hwnds: ' + ($pre -join ',')
  foreach ($w in @(Get-EasiNoteRoots)) {
    $diag += ('window hwnd=' + $w.Current.NativeWindowHandle + ' name=' + $w.Current.Name)
  }
  $diag | Out-File -LiteralPath (Join-Path $OutDir 'no_window.txt') -Encoding UTF8
  $diag | ForEach-Object { Write-Output ('DIAG ' + $_) }
  exit 3
}

Write-Output ('PAGE_NOW ' + (Get-PageNum $root))
$rows = New-Object System.Collections.ArrayList
$fail = $false
$want = @()
foreach ($p in ($Pages -split ',')) { if (([string]$p).Trim() -ne '') { $want += [int](([string]$p).Trim()) } }

foreach ($pg in $want) {
  # make sure we are in the editor
  $ew = Find-EditWindow
  if ($ew -eq $null -and $hwnd -ne $null) {
    [WinCap2]::SendEsc($hwnd)
    Start-Sleep -Seconds 3
    $ew = Find-EditWindow
  }
  if ($ew -ne $null) {
    $root = $ew; $hwnd = [IntPtr]$ew.Current.NativeWindowHandle
    $next = Find-Next $root; $prev = Find-Prev $root
  }
  $mode = Go-Page $pg
  Start-Sleep -Milliseconds 500
  $editPage = Get-PageNum $root

  if ($Present) {
    $db = Find-Display $root
    if ($db -ne $null) {
      Select-El $db | Out-Null
      Write-Output ('CLICK_PRESENT page=' + $pg)
      Start-Sleep -Seconds 4
      $pw = Find-PresentWindow
      if ($pw -ne $null) {
        $root = $pw; $hwnd = [IntPtr]$pw.Current.NativeWindowHandle
        $next = Find-Next $root; $prev = Find-Prev $root
        Write-Output ('PRESENT_WINDOW hwnd=' + $hwnd + ' page=' + (Get-PageNum $root))
      } else { Write-Output 'PRESENT_WINDOW_NOT_FOUND' }
      Start-Sleep -Milliseconds 800
    } else { Write-Output 'NO_DISPLAY_BUTTON' }
  }

  $cur = Get-PageNum $root
  $f0 = ('p{0}_0.png' -f $pg)
  $r0 = Shoot (Join-Path $OutDir $f0)
  [void]$rows.Add((@($pg, 'before', $f0, $cur, 0) -join $TAB))
  Write-Output ('SHOT page={0} phase=before file={1} pageAtShot={2} result={3} nav={4} editPage={5}' -f $pg, $f0, $cur, $r0, $mode, $editPage)
  if ($r0 -eq 'BLACK' -or $r0 -eq 'BAD_RECT' -or $mode -eq 'miss' -or ($cur -gt 0 -and $cur -ne $pg)) { $fail = $true }
  for ($a = 1; $a -le $AnimPerPage; $a++) {
    $cBefore = Get-PageNum $root
    Invoke-El $next | Out-Null
    Start-Sleep -Milliseconds $ClickWaitMs
    $curA = Get-PageNum $root
    if ($curA -gt 0 -and $curA -ne $pg) { Write-Output ('ANIM_STOP page=' + $pg + ' after_click=' + $a + ' pageNow=' + $curA + ' (click turned the page)'); break }
    $fa = ('p{0}_a{1}.png' -f $pg, $a)
    $ra = Shoot (Join-Path $OutDir $fa)
    [void]$rows.Add((@($pg, ('after' + $a), $fa, $curA, $a) -join $TAB))
    Write-Output ('SHOT page={0} phase=after{1} file={2} pageAtShot={3} result={4}' -f $pg, $a, $fa, $curA, $ra)
    if ($ra -eq 'BLACK' -or $ra -eq 'BAD_RECT') { $fail = $true }
  }
  if ($Present) { [WinCap2]::SendEsc($hwnd); Start-Sleep -Seconds 3 }
}

$out = @()
$out += (@('page', 'phase', 'file', 'pageAtShot', 'clicks') -join $TAB)
foreach ($x in $rows) { $out += $x }
$out | Out-File -LiteralPath $shotsPath -Encoding UTF8

$info = @()
$info += 'when=' + (Get-Date).ToString('s')
$info += 'enbx=' + $Enbx
$info += 'outdir=' + $OutDir
$info += 'pages=' + $Pages
$info += 'animPerPage=' + $AnimPerPage
$info += 'present=' + [bool]$Present
$info += 'shots=' + $rows.Count
$info | Out-File -LiteralPath $infoPath -Encoding UTF8

Write-Output ('SHOTS_FILE ' + $shotsPath)
Write-Output ('SUMMARY shots=' + $rows.Count + ' failed=' + $fail)
if ($fail) { exit 4 }
Write-Output 'DONE'
exit 0
