# Instala una versión de Velbrum que el navegador ya bajó y verificó
# (marca/actualizador-velbrum.sys.mjs): lo corre Velbrum al cerrarse, desde
# <datos>\actualizacion. Para Windows (como aplicar.sh en Linux y macOS).
#
#   -Modo carpeta     -Destino es la carpeta del Velbrum portable: se
#                     reemplaza todo menos «datos» y «portable»;
#         instalador  -Nueva es el instalador nuevo: se corre sin preguntas.
#   -Proceso   el proceso de Velbrum: se espera a que termine (y a que se
#              cierre todo lo que corre desde -Destino, como la ventana con Tor).
#   -Relanzar  1 para volver a abrir Velbrum al terminar.
#
# Si algo falla, se vuelve a dejar la versión anterior. Cómo terminó queda en
# «resultado» («ok» o «error: …»), que lee Velbrum al abrir; los detalles, en
# registro.txt. (Este archivo va en UTF-8 con BOM: si no, Windows PowerShell
# lo lee como ANSI.)
param(
  [Parameter(Mandatory)][string]$Modo,
  [Parameter(Mandatory)][int]$Proceso,
  [Parameter(Mandatory)][string]$Nueva,
  [Parameter(Mandatory)][string]$Destino,
  [string]$Relanzar = "0"
)
$ErrorActionPreference = "Stop"
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$vieja = Join-Path $aqui "vieja"

function Anotar([string]$texto) {
  $linea = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") + " " + $texto
  Add-Content -LiteralPath (Join-Path $aqui "registro.txt") -Value $linea -Encoding UTF8
}

function Terminar([string]$texto) {
  Set-Content -LiteralPath (Join-Path $aqui "resultado") -Value $texto -Encoding UTF8
  Anotar $texto
  if ($Relanzar -eq "1") {
    Start-Process -FilePath (Join-Path $Destino "velbrum.exe") -WorkingDirectory $Destino
  }
  exit 0
}

function Corriendo {
  $prefijo = $Destino.TrimEnd("\") + "\"
  @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
      try { $_.Path -and $_.Path.StartsWith($prefijo, [StringComparison]::OrdinalIgnoreCase) } catch { $false }
    })
}

Anotar "${Modo}: $Nueva -> $Destino"
try {
  # Hasta 10 minutos para que se cierre Velbrum y lo que corre desde su carpeta.
  $limite = (Get-Date).AddMinutes(10)
  while (Get-Process -Id $Proceso -ErrorAction SilentlyContinue) {
    if ((Get-Date) -gt $limite) { Terminar "error: Velbrum no se cerró" }
    Start-Sleep -Milliseconds 500
  }
  while ((Corriendo).Count -gt 0) {
    if ((Get-Date) -gt $limite) {
      Terminar ("error: todavía hay programas de Velbrum abiertos: " + ((Corriendo | ForEach-Object { $_.Name }) -join ", "))
    }
    Start-Sleep -Milliseconds 500
  }

  if ($Modo -eq "instalador") {
    $p = Start-Process -FilePath $Nueva -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-" -Wait -PassThru
    if ($p.ExitCode -ne 0) { Terminar "error: el instalador salió con $($p.ExitCode)" }
    Remove-Item -LiteralPath $Nueva -Force -ErrorAction SilentlyContinue
    Terminar "ok"
  }
  if ($Modo -ne "carpeta") { Terminar "error: modo desconocido: $Modo" }

  if (Test-Path -LiteralPath $vieja) { Remove-Item -LiteralPath $vieja -Recurse -Force }
  New-Item -ItemType Directory -Path $vieja | Out-Null
  $quedan = @("datos", "portable")
  function Volver {
    Get-ChildItem -LiteralPath $Destino -Force | Where-Object { $quedan -notcontains $_.Name } |
      ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination $Nueva -ErrorAction SilentlyContinue }
    Get-ChildItem -LiteralPath $vieja -Force |
      ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination $Destino -ErrorAction SilentlyContinue }
  }
  try {
    Get-ChildItem -LiteralPath $Destino -Force | Where-Object { $quedan -notcontains $_.Name } |
      ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination $vieja }
    Get-ChildItem -LiteralPath $Nueva -Force | Where-Object { $quedan -notcontains $_.Name } |
      ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination $Destino }
  } catch {
    Anotar $_.Exception.Message
    Volver
    Terminar ("error: no pude reemplazar los archivos: " + $_.Exception.Message)
  }
  Remove-Item -LiteralPath $vieja -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $aqui "nueva") -Recurse -Force -ErrorAction SilentlyContinue
  Terminar "ok"
} catch {
  Anotar $_.Exception.Message
  Terminar ("error: " + $_.Exception.Message)
}
