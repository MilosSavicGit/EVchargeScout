# ocm_survey.ps1
# ---------------------------------------------------------------------------
# Asks Open Charge Map how much it actually knows about each candidate country,
# before committing any of them to build_ev.py.
#
#   200 POIs  = the sample hit the cap. Real coverage, worth pulling properly.
#   under 200 = that IS the whole country. China returned 15.
#
# Also reports the connector mix, because a country full of chargers your car
# cannot physically plug into is worse than no coverage at all - it plans a
# route that looks fine and isn't.
#
#   Run:  powershell -ExecutionPolicy Bypass -File .\ocm_survey.ps1
# ---------------------------------------------------------------------------

$key = [Environment]::GetEnvironmentVariable('OCM_API_KEY','User')
if (-not $key) { $key = [Environment]::GetEnvironmentVariable('OCM_API_KEY','Machine') }
if (-not $key) { Write-Error "OCM_API_KEY not found in the environment."; exit 1 }

# Candidates. Europe is already covered - these are the ones being considered.
# CN is included as the control: we know it returns 15, so if it ever returns
# something else, this script is measuring the wrong thing.
$countries = @(
  @{ cc='JP'; name='Japan'          },
  @{ cc='KR'; name='South Korea'    },
  @{ cc='TH'; name='Thailand'       },
  @{ cc='VN'; name='Vietnam'        },
  @{ cc='MY'; name='Malaysia'       },
  @{ cc='SG'; name='Singapore'      },
  @{ cc='ID'; name='Indonesia'      },
  @{ cc='IN'; name='India'          },
  @{ cc='BR'; name='Brazil'         },
  @{ cc='AR'; name='Argentina'      },
  @{ cc='CL'; name='Chile'          },
  @{ cc='CO'; name='Colombia'       },
  @{ cc='PE'; name='Peru'           },
  @{ cc='UY'; name='Uruguay'        },
  @{ cc='CN'; name='China (control)'}
)

$hdr = @{ 'X-API-Key' = $key }

# --- connector type names, fetched once from /referencedata -----------------
# Same endpoint build_ev.py already calls for operator hydration. Fetching the
# names beats hardcoding my reading of the ID numbers.
Write-Host "Fetching connection type reference data..." -ForegroundColor DarkGray
$connName = @{}
try {
  $ref = Invoke-RestMethod -Uri "https://api.openchargemap.io/v3/referencedata/" -Headers $hdr
  foreach ($t in $ref.ConnectionTypes) { $connName[[int]$t.ID] = $t.Title }
  Write-Host "  $($connName.Count) connection types known.`n" -ForegroundColor DarkGray
} catch {
  Write-Warning "Could not fetch reference data - IDs will be shown raw. $($_.Exception.Message)"
}

function Show-Conn([int]$id, [int]$n) {
  $nm = if ($connName.ContainsKey($id)) { $connName[$id] } else { "type $id" }
  if ($id -eq 0) { $nm = 'UNKNOWN' }
  "$nm ($n)"
}

$results = @()

foreach ($c in $countries) {
  $u = "https://api.openchargemap.io/v3/poi/?countrycode=$($c.cc)" +
       "&maxresults=200&compact=true&output=json"
  try {
    $r = Invoke-RestMethod -Uri $u -Headers $hdr -ErrorAction Stop
    $poi = @($r).Count

    $conns = @($r.Connections | Where-Object { $_ })
    $groups = $conns | Group-Object ConnectionTypeID | Sort-Object Count -Descending
    $top3 = ($groups | Select-Object -First 3 |
             ForEach-Object { Show-Conn ([int]$_.Name) $_.Count }) -join ', '
    $unknown = ($conns | Where-Object { [int]$_.ConnectionTypeID -eq 0 }).Count
    $unkPct  = if ($conns.Count) { [math]::Round(100 * $unknown / $conns.Count, 1) } else { 0 }

    # DC matters more than the exact plug: an AC-only country cannot support
    # road-trip planning however many points it has.
    $dc = ($conns | Where-Object { [double]$_.PowerKW -ge 50 }).Count

    $results += [PSCustomObject]@{
      CC       = $c.cc
      Country  = $c.name
      POIs     = $poi
      Capped   = if ($poi -ge 200) { 'YES' } else { '-' }
      DC50plus = $dc
      UnkPct   = $unkPct
      TopConnectors = $top3
    }
  } catch {
    $results += [PSCustomObject]@{
      CC=$c.cc; Country=$c.name; POIs=-1; Capped='ERR'; DC50plus=0; UnkPct=0
      TopConnectors = $_.Exception.Message
    }
  }
  # OCM run on donated infrastructure and ask callers not to hammer the API.
  Start-Sleep -Milliseconds 500
}

Write-Host ""
$results | Sort-Object POIs -Descending |
  Format-Table CC, Country, POIs, Capped, DC50plus, UnkPct, TopConnectors -AutoSize

Write-Host @"

READING THIS
  Capped = YES   the sample ran out of room, not out of data. Pull it properly
                 with build_ev.py --country <CC> to get the real number.
  Capped = -     that number IS the country. China returns 15 against a real
                 network of 300,000+, because domestic operators do not
                 publish to OCM.
  DC50plus       connections at 50 kW or more in the sample. Road-trip planning
                 needs these; a country of 7 kW AC points cannot support it.
  UnkPct         share with ConnectionTypeID 0. Germany runs ~16%, Japan ~1.5%.
                 High values mean connector filtering will not be reliable there.

"@ -ForegroundColor DarkGray
