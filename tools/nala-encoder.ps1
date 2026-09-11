# NALA key-card helper. Runs on the front-desk PC, next to CardEncoder.dll.
#
# What it is: the machine half of the card table. /cards holds ONE ROW PER
# CARD in the world, keyed by the number the encoder reports (the serial
# belongs to the plastic - TTHotel's own behaviour; the owner, 11 Sep).
# This helper is the only thing that moves plastic, and each move is one
# thing done to the table:
#   a card cut      -> a row written at /cards/<no> (a re-cut lands on the
#                      same key, so the old row is shed in the same act)
#   a card wiped    -> its row deleted
# The REQUEST to cut is /cutrun - a short-lived queue the desk switches
# on, this works through, and that ends when the cutting ends. It is
# never stored with the cards. /cancelrun is the wipe session, as before.
#
# What it holds: ONE key for the Worker's card relays, and the encoder
# staff account for Firebase - a role confined by rules.json. The TTLock
# secrets live in the Cloudflare dashboard; this PC never sees them.
# hotelInfo arrives minted and dies in minutes.
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
# The desk's filled-in values live better in nala-config.ps1 beside this
# file: the same lines as above, once. If it exists it wins, so a fresh
# download of this file needs no editing - added 9 Sep, after the desk
# re-copied five values for the third time in one afternoon.
if (Test-Path (Join-Path $PSScriptRoot "nala-config.ps1")) {
  . (Join-Path $PSScriptRoot "nala-config.ps1")
}

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
# Set-Location moves POWERSHELL's location only; the Win32 working
# directory, which is what LoadLibrary probes for CardEncoder.dll, needs
# setting separately. Learned at the desk 8 Sep, lost in the 9 Sep
# rewrite, relearned from "Unable to load DLL" on 10 Sep.
[Environment]::CurrentDirectory = $PSScriptRoot

# The DLL's doors, exactly as the manual states them (Card Encoder User
# Manual v1.6.1). 64-bit process against dll\64: on x64 there is only one
# calling convention, which is why bitness was the only question.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CE {
  [DllImport("CardEncoder.dll", CharSet=CharSet.Ansi)]
  public static extern int CE_ConnectComm(string portName);
  // Ansi, not Unicode: proven on the real E3 at the desk, 9 Sep - the
  // Unicode marshal made every port read as garbage ("no encoder
  // answering" on all 20); Ansi "COM3" connected with rc 0.
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
  [DllImport("CardEncoder.dll")]
  public static extern int CE_GetCardNo(out IntPtr cardNumber);
  [DllImport("CardEncoder.dll", CharSet=CharSet.Ansi)]
  public static extern int CE_ClearCard(string hotelInfo);
}
"@

# The number of whatever card sits on the pad, or null for an empty pad
# (or an encoder that would not say - callers treat unknown as empty).
function Get-CardNo {
  $p = [IntPtr]::Zero
  try {
    if ([CE]::CE_GetCardNo([ref]$p) -eq 0 -and $p -ne [IntPtr]::Zero) {
      return [Runtime.InteropServices.Marshal]::PtrToStringAnsi($p)
    }
  } catch {}
  return $null
}

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
function Fb-Put([string]$path, $obj){
  Invoke-RestMethod -Method Put -ContentType "application/json" `
    -Uri "$FB_DB$path.json?auth=$(Fb-Token)" -Body ($obj | ConvertTo-Json) | Out-Null
}
function Fb-Delete([string]$path){
  Invoke-RestMethod -Method Delete `
    -Uri "$FB_DB$path.json?auth=$(Fb-Token)" | Out-Null
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

# Firebase turns a node whose keys are NUMBERS into a list when the keys
# sit dense enough: villas 4-and-6 come back as a map, villas 1-2-3 come
# back as an array with a null in seat 0, and /cancelrun/done (keyed
# 0,1,2...) comes back as an array almost always. Every keyed read goes
# through this, so both shapes read the same. Found live 11 Sep: the
# queue scan read the ARRAY's own properties and tried to sort villa
# "SyncRoot".
function Node-Pairs($node){
  $out = @()
  if ($null -eq $node) { return ,$out }
  if ($node -is [System.Array]) {
    for ($i = 0; $i -lt $node.Length; $i++) {
      if ($null -ne $node[$i]) {
        $out += [pscustomobject]@{ Name = [string]$i; Value = $node[$i] }
      }
    }
  } else {
    foreach ($p in $node.PSObject.Properties) {
      $out += [pscustomobject]@{ Name = $p.Name; Value = $p.Value }
    }
  }
  ,$out
}

Log "NALA encoder helper - watching the card table. Ctrl+C stops it."
while ($true) {
  try {
    $busy = $false

    # ── the cut run: the desk's short-lived request ──────────────────
    # /cutrun { state, by, at, seen, queue: {villa:{guest,qty,cut,expiry,note?}} }
    # Work it in villa order - the batch promise the run screen makes -
    # and for EVERY card cut, write its row at /cards/<no> in the same
    # breath. The row is the lasting record; the run is not.
    $run = Fb-Get "/cutrun"
    if ($run -and $run.state -eq "on") {
      $busy = $true
      Fb-Patch "/cutrun" @{ seen=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
      $todo = @()
      foreach ($p in (Node-Pairs $run.queue)) {
        if (-not $p.Value.note -and [int]$p.Value.cut -lt [int]$p.Value.qty) {
          $todo += [pscustomobject]@{ villa = $p.Name; q = $p.Value }
        }
      }
      $todo = @($todo | Sort-Object { [int]$_.villa })
      if (-not $todo) {
        # the queue is finished: say so once, and the run screen shows
        # its envelope summary. done, not off, so the desk can tell a
        # finished run from one it stopped.
        Fb-Patch "/cutrun" @{ state="done" }
        Log "cut run finished"
      } elseif (-not (Connect-Encoder)) {
        Log "no encoder answering - is the E3 plugged in?"
        # the run screen's ten-second verdict owns this ending
      } else {
        $stopped = $false
        foreach ($t in $todo) {
          $villa = $t.villa; $q = $t.q
          $lock = (Locks).PSObject.Properties[$villa]
          if (-not $lock) {
            Fb-Patch "/cutrun/queue/$villa" @{ note="no lock named $villa in TTHotel" }
            continue
          }
          Log "villa ${villa}: cards $([int]$q.cut + 1) to $($q.qty), expiry $([DateTimeOffset]::FromUnixTimeSeconds($q.expiry).LocalDateTime)"
          $failed = $null; $lastNo = $null
          for ($i = [int]$q.cut + 1; $i -le [int]$q.qty; $i++) {
            # TTHotel's own dialog waits for the last card to LEAVE before
            # it asks for the next, and it is right: 800ms after a beep the
            # same card is still on the pad, and the first live batch
            # (9 Sep) wrote card 1 twice and called it two cards.
            if ($i -gt 1 -or $lastNo) {
              if ($lastNo) {
                Log "  lift card off the reader"
                while ((Get-CardNo) -eq $lastNo) { Start-Sleep -Milliseconds 700 }
              } elseif ($i -gt 1) { Start-Sleep -Milliseconds 2500 }
            }
            Log "  hold card $i of $($q.qty) to the reader"
            # Wait for a card by POLLING the pad, not inside CE_WriteCard's
            # own blocking wait: while the pad is empty the desk may press
            # Skip (the villa's qty shrinks below $i) or Stop (state off),
            # and both deserve an answer in seconds. The heartbeat keeps
            # the run screen reading the wait as alive.
            $beat = 0
            while (-not (Get-CardNo)) {
              Start-Sleep -Milliseconds 700
              $beat++
              if ($beat % 4 -eq 0) {
                $r2 = $null
                try { $r2 = Fb-Get "/cutrun" } catch {}
                $q2 = $null
                if ($r2 -and $r2.queue) { $q2 = $r2.queue.PSObject.Properties[$villa] }
                if (-not $r2 -or $r2.state -ne "on" -or -not $q2 -or [int]$q2.Value.qty -lt $i) {
                  $stopped = $true
                  Log "  villa ${villa}: the desk skipped or stopped at card $($i-1)"
                  break
                }
              }
              if ($beat % 4 -eq 2) {
                try { Fb-Patch "/cutrun" @{ seen=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() } } catch {}
              }
            }
            if ($stopped) { break }
            $failed = Write-One $villa $lock.Value ([uint32]$q.expiry)
            if ($failed) { break }
            $no = Get-CardNo
            # THE MODEL, at the moment it matters: the cut card is a row,
            # written now, keyed by its own number - so a RE-CUT lands on
            # the same key and sheds the old row in the same act, exactly
            # as TTHotel's own register behaves. A card that kept its
            # number to itself still exists, so it still gets a row, under
            # a u-key only the Keys page's Remove can retire.
            $key = if ($no) { [string]$no } else { "u$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())" }
            $old = $null
            if ($no) { try { $old = Fb-Get "/cards/$key" } catch {} }
            Fb-Put "/cards/$key" @{ villa=[string]$villa; guest=[string]$q.guest;
              cut=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds();
              expiry=[long]$q.expiry; by=[string]$run.by }
            if ($old -and ([string]$old.villa) -ne ([string]$villa)) {
              Log "  (this plastic was villa $($old.villa)'s - its old row shed with the re-cut)"
            }
            $lastNo = $no
            Fb-Patch "/cutrun/queue/$villa" @{ cut=$i }
            Fb-Patch "/cutrun" @{ seen=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
            Log "  card $i written - lift it off"
          }
          if ($stopped) { break }
          if ($failed) {
            Log "  FAILED: $failed"
            Fb-Patch "/cutrun/queue/$villa" @{ note=$failed }
          } else {
            Log "  villa $villa done - envelope its cards"
          }
        }
      }
    }

    # ── the cancel session: the Keys page's reader-side duty ─────────
    # The desk switches /cancelrun on; every card then held to the E3 is
    # read, named by ITS OWN ROW at /cards/<no> - a direct read, never a
    # scan - wiped (CE_ClearCard), and its row deleted: the wipe and the
    # removal are one act. A card with no row (foreign plastic, or one
    # already cancelled) is wiped all the same and reported villa "?" -
    # the page says only "Unknown card", both normal desk business
    # (ruled 11 Sep). The desk's Stop - or the page's offline verdict -
    # switches it off. One encoder, one duty at a time.
    $cr = Fb-Get "/cancelrun"
    if ($cr -and $cr.state -eq "on") {
      $busy = $true
      if (-not (Connect-Encoder)) {
        Log "cancel session waiting - no encoder answering"
      } else {
        Log "cancel session on - hold cards to the reader"
        $n = 0
        if ($cr.done) { $n = @(Node-Pairs $cr.done).Count }
        $wiped = @{}
        while ($true) {
          Fb-Patch "/cancelrun" @{ seen=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
          $cr = Fb-Get "/cancelrun"
          if (-not $cr -or $cr.state -ne "on") { Log "cancel session off"; break }
          $no = Get-CardNo
          if ($no -and -not $wiped.ContainsKey($no)) {
            $villa = "?"; $row = $null
            try { $row = Fb-Get "/cards/$no" } catch {}
            if ($row) { $villa = [string]$row.villa }
            $rc = [CE]::CE_ClearCard((Hotel-Info))
            $wiped[$no] = 1
            if ($rc -eq 0) {
              $null = [CE]::CE_Beep(80, 60, 1)
              if ($row) { Fb-Delete "/cards/$no" }
              Fb-Patch "/cancelrun/done/$n" @{ villa=$villa; no=$no; at=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
              $n++
              Log "  wiped $no - villa $villa"
            } elseif ($rc -ne 102) {
              # a card that will not wipe (another hotel's, unreadable)
              # is still reported, so the desk sees what it held; its
              # row, if any, STAYS - the card was not wiped
              Fb-Patch "/cancelrun/done/$n" @{ villa=$villa; no=$no; note="would not wipe: $(CE-Msg $rc)"; at=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
              $n++
              Log "  $no refused a wipe: $(CE-Msg $rc)"
            }
          }
          Start-Sleep -Milliseconds 700
        }
      }
    }

    # ── one encoder, shared politely ─────────────────────────────────
    # Held only while a run or a session needs it; released the moment
    # both are quiet, so TTLock's own program can use the E3 without
    # anyone touching this window (the owner, 9 Sep).
    if ($script:Port -and -not $busy) {
      try { $null = [CE]::CE_DisconnectComm() } catch {}
      $script:Port = $null
      Log "encoder released - idle"
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
