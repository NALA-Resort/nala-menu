# NALA key-card helper. Runs on the front-desk PC, next to CardEncoder.dll.
#
# What it is: the machine half of /cardjobs. The Front Desk page queues a
# villa's cards; this watches the queue, drives the E3 encoder through
# TTLock's own CardEncoder.dll, and writes back state, written and note -
# the states the boards read through cardCell (tests/card_cases.json):
# queued -> writing -> done, or failed.
#
# What it holds: ONE key for the Worker's card relays, and the encoder
# staff account for Firebase - a role that can touch /cardjobs and nothing
# else (rules.json). The TTLock secrets live in the Cloudflare dashboard;
# this PC never sees them. hotelInfo arrives minted and dies in minutes.
#
# Install (see ENCODER.md for the long form):
#   1. Put this file in the kit's dll\64 folder, beside CardEncoder.dll.
#   2. Fill in the CONFIG block below.
#   3. Run it:  powershell -ExecutionPolicy Bypass -File nala-encoder.ps1
#   4. It says what it is doing, one line at a time. Ctrl+C stops it.
#
# PowerShell rather than a compiled program on purpose: every Windows box
# runs it, there is nothing to install, and the code the desk PC executes
# is the code anybody can read in this repo.

# ── CONFIG ──────────────────────────────────────────────────────────
$WORKER      = "https://nala-mews-sync.<account>.workers.dev"  # the mews-sync Worker's URL
$HELPER_KEY  = "PASTE-THE-HELPER-KEY"       # matches HELPER_KEY in the Worker
$FB_API_KEY  = "AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI"  # public by design; rules protect the data
$FB_DB       = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app"
$ENC_EMAIL   = "000000@staff.nala"          # the encoder staff account (role: encoder)
$ENC_PASS    = "000000"                     # its six digits
$COM_PORT    = ""                           # "COM3" if known; empty scans COM1..COM20
$ALLOW_LOCKOUT = $false   # a guest card does not open a double-locked door
# ────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# The DLL's doors, exactly as the manual states them (Card Encoder User
# Manual v1.6.1). 64-bit process against dll\64: on x64 there is only one
# calling convention, which is why bitness was the only question.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CE {
  [DllImport("CardEncoder.dll", CharSet=CharSet.Unicode)]
  public static extern int CE_ConnectComm(string portName);
  [DllImport("CardEncoder.dll")]
  public static extern int CE_DisconnectComm();
  [DllImport("CardEncoder.dll", CharSet=CharSet.Ansi)]
  public static extern int CE_InitCardEncoder(string hotelInfo);
  [DllImport("CardEncoder.dll", CharSet=CharSet.Ansi)]
  public static extern int CE_InitCard(string hotelInfo);
  [DllImport("CardEncoder.dll", CharSet=CharSet.Ansi)]
  public static extern int CE_WriteCard(string hotelInfo, int buildNo, int floorNo,
                                        string mac, uint timestamp, bool allowLockOut);
  [DllImport("CardEncoder.dll")]
  public static extern int CE_Beep(int voiceLen, int interval, int voiceCount);
}
"@

# The manual's error table, so a code lands at the desk as a sentence.
$CE_ERR = @{
  0="ok"; 1="failed"; 2="bad parameter"; 3="encoder not answering (re-plug the USB)";
  4="communication error (re-plug the USB)"; 5="device returned an error";
  10="no server configured"; 11="could not reach TTLock"; 12="TTLock refused";
  13="bad hotelInfo (it expires in minutes - will fetch a fresh one)";
  14="not this hotel's encoder"; 15="encoder not initialised";
  16="cannot connect to the encoder"; 21="not an IC card";
  102="timed out waiting for a card"; 104="card memory full";
  105="cannot decrypt this card"; 106="card belongs to another hotel or was never initialised";
  109="no hotel id configured"
}
function CE-Msg([int]$code){ if ($CE_ERR.ContainsKey($code)) { $CE_ERR[$code] } else { "code $code" } }

function Log([string]$m){ Write-Host ("{0:HH:mm:ss}  {1}" -f (Get-Date), $m) }

# ── Firebase: the encoder account, signed in the way mews-sync signs ──
$script:FbToken = $null; $script:FbAt = Get-Date 0
function Fb-Token {
  if ($script:FbToken -and ((Get-Date) - $script:FbAt).TotalMinutes -lt 50) { return $script:FbToken }
  $r = Invoke-RestMethod -Method Post -ContentType "application/json" `
    -Uri "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$FB_API_KEY" `
    -Body (@{ email=$ENC_EMAIL.Trim(); password=$ENC_PASS.Trim(); returnSecureToken=$true } | ConvertTo-Json)
  $script:FbToken = $r.idToken; $script:FbAt = Get-Date
  return $script:FbToken
}
function Fb-Get([string]$path){
  Invoke-RestMethod -Uri "$FB_DB$path.json?auth=$(Fb-Token)"
}
function Fb-Patch([string]$path, $obj){
  Invoke-RestMethod -Method Patch -ContentType "application/json" `
    -Uri "$FB_DB$path.json?auth=$(Fb-Token)" -Body ($obj | ConvertTo-Json) | Out-Null
}

# ── the Worker's relays: hotelInfo dies in minutes, locks change never ──
$script:HotelInfo = $null; $script:HotelAt = Get-Date 0
function Hotel-Info([switch]$Fresh){
  if (-not $Fresh -and $script:HotelInfo -and ((Get-Date) - $script:HotelAt).TotalMinutes -lt 7) { return $script:HotelInfo }
  $r = Invoke-RestMethod -Uri "$WORKER/cardauth" -Headers @{ "x-nala-helper" = $HELPER_KEY }
  if (-not $r.ok) { throw "cardauth: $($r.error)" }
  $script:HotelInfo = $r.hotelInfo; $script:HotelAt = Get-Date
  return $script:HotelInfo
}
$script:Locks = $null
function Locks {
  if ($script:Locks) { return $script:Locks }
  $r = Invoke-RestMethod -Uri "$WORKER/cardlocks" -Headers @{ "x-nala-helper" = $HELPER_KEY }
  if (-not $r.ok) { throw "cardlocks: $($r.error)" }
  $script:Locks = $r.locks
  Log "lock table: $((@($r.locks.PSObject.Properties)).Count) villas"
  return $script:Locks
}

# ── the encoder ──────────────────────────────────────────────────────
$script:Port = $null
function Connect-Encoder {
  if ($script:Port) { return $true }
  $ports = if ($COM_PORT) { @($COM_PORT) } else { 1..20 | ForEach-Object { "COM$_" } }
  foreach ($p in $ports) {
    if ([CE]::CE_ConnectComm($p) -eq 0) {
      $script:Port = $p; Log "encoder found on $p"
      $null = [CE]::CE_InitCardEncoder((Hotel-Info))
      return $true
    }
  }
  return $false
}

# One card: retry while the pad is empty, fail on anything terminal. The
# desk holds a card to the E3 and the next attempt lands on it - that IS
# the "hold card 1 to the reader" moment the run screen shows.
function Write-One([string]$villa, $lock, [uint32]$expiry){
  for ($try = 0; $try -lt 40; $try++) {
    $rc = [CE]::CE_WriteCard((Hotel-Info), [int]$lock.buildNo, [int]$lock.floorNo,
                             $lock.mac, $expiry, $ALLOW_LOCKOUT)
    if ($rc -eq 0) { $null = [CE]::CE_Beep(80, 60, 1); return $null }
    if ($rc -eq 13) { $null = Hotel-Info -Fresh; continue }          # stale hotelInfo
    if ($rc -in 3,4,102) { Start-Sleep -Milliseconds 1200; continue } # no card yet / hiccup
    return "card write refused: $(CE-Msg $rc)"                        # terminal
  }
  return "no card presented: $(CE-Msg 102)"
}

function Today { (Get-Date).ToString("yyyy-MM-dd") }

Log "NALA encoder helper - watching /cardjobs. Ctrl+C stops it."
while ($true) {
  try {
    $day = Today
    $jobs = Fb-Get "/cardjobs/$day"
    $queued = @()
    if ($jobs) {
      foreach ($p in $jobs.PSObject.Properties) {
        if ($p.Value.state -eq "queued") { $queued += ,@($p.Name, $p.Value) }
      }
    }
    # villa order, the batch promise the run screen makes
    $queued = $queued | Sort-Object { [int]$_[0] }

    foreach ($q in $queued) {
      $villa = $q[0]; $job = $q[1]
      $lock = (Locks).PSObject.Properties[$villa]
      if (-not $lock) {
        Fb-Patch "/cardjobs/$day/$villa" @{ state="failed"; note="no lock named $villa in TTHotel" }
        continue
      }
      if (-not (Connect-Encoder)) {
        Log "no encoder answering - is the E3 plugged in?"
        break   # leave the job queued; the board shows the amber wait
      }
      Log "villa ${villa}: $($job.qty) cards, expiry $([DateTimeOffset]::FromUnixTimeSeconds($job.expiry).LocalDateTime)"
      # at refreshed on the claim and on every card: the boards read a
      # fresh stamp on a writing job as "the encoder is alive", and a
      # stale one as a PC that died mid-write (front-desk.html, cardsAlive)
      Fb-Patch "/cardjobs/$day/$villa" @{ state="writing"; written=0; at=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
      $failed = $null
      for ($i = 1; $i -le [int]$job.qty; $i++) {
        Log "  hold card $i of $($job.qty) to the reader"
        $failed = Write-One $villa $lock.Value ([uint32]$job.expiry)
        if ($failed) { break }
        Fb-Patch "/cardjobs/$day/$villa" @{ written=$i; at=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
        Log "  card $i written"
        if ($i -lt [int]$job.qty) { Start-Sleep -Milliseconds 800 }   # lift-off gap
      }
      if ($failed) {
        Log "  FAILED: $failed"
        Fb-Patch "/cardjobs/$day/$villa" @{ state="failed"; note=$failed }
      } else {
        Fb-Patch "/cardjobs/$day/$villa" @{ state="done" }
        Log "  villa $villa done - envelope its cards"
      }
    }
  } catch {
    # The Worker's refusals carry their reason in the response body - the
    # relay 502s with "getInfo refused: ..." and friends - and the bare
    # exception says only "Bad Gateway". Learned at the first live run,
    # 9 Sep: twenty identical 502 lines and not one said why.
    $m = $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $m += " - " + $_.ErrorDetails.Message }
    Log "trouble: $m"
    $script:Port = $null   # a wedged port reconnects on the next pass
    try { $null = [CE]::CE_DisconnectComm() } catch {}
  }
  Start-Sleep -Seconds 2
}
