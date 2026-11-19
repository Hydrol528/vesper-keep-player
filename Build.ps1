param([string]$WixPath,[string]$Python='python')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$build=Join-Path $root 'build'
New-Item -ItemType Directory -Force -Path (Join-Path $build 'temp') | Out-Null
$env:TEMP=Join-Path $build 'temp';$env:TMP=$env:TEMP
$env:PYINSTALLER_CONFIG_DIR=Join-Path $build 'pyinstaller-cache'
if(-not (Test-Path (Join-Path $WixPath 'candle.exe'))){throw 'Pass -WixPath with the extracted WiX 3.14.1 folder.'}
$args=@('-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','VesperService','--icon',(Join-Path $root 'src\vesper.ico'),'--paths',(Join-Path $root 'src'),'--distpath',(Join-Path $root 'dist'),'--workpath',(Join-Path $build 'pyinstaller'),'--specpath',$build)
foreach($file in @('login.html','index.html','login.js','app.js','style.css','vesper-logo.png')){$args+=@('--add-data',((Join-Path $root ('src\'+$file))+':.'))}
$args+=@('--add-data',((Join-Path $root 'src\fonts')+':fonts'),(Join-Path $root 'src\service_entry.py'))
& $Python @args
if($LASTEXITCODE -ne 0){throw 'Service build failed'}
$dist=Join-Path $root 'dist\VesperService'
foreach($file in @('vesper.ico','vesper-logo.png','vesper-app-icon.png','Start here.html')){Copy-Item -LiteralPath (Join-Path $root ('src\'+$file)) -Destination $dist -Force}
Copy-Item -LiteralPath (Join-Path $root 'Licenses') -Destination $dist -Recurse -Force
$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $csc /nologo /target:winexe /platform:x64 /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll ('/win32icon:'+(Join-Path $root 'src\vesper.ico')) ('/out:'+(Join-Path $dist 'Vesper Keep Player.exe')) (Join-Path $root 'src\Player.cs')
if($LASTEXITCODE -ne 0){throw 'Launcher build failed'}
$p=Start-Process -FilePath (Join-Path $dist 'Vesper Keep Player.exe') -ArgumentList '--self-test' -PassThru -WindowStyle Hidden
if(-not $p.WaitForExit(40000)){throw 'Packaged self-test timed out'}
if($p.ExitCode -ne 0){throw ('Packaged self-test failed: '+$p.ExitCode)}
& $Python (Join-Path $root 'build-installer.py')
if($LASTEXITCODE -ne 0){throw 'Installer source failed'}
$out=Join-Path $build 'installer'
& (Join-Path $WixPath 'candle.exe') -nologo -ext WixUtilExtension -out (Join-Path $out 'Player.wixobj') (Join-Path $out 'Player.wxs')
if($LASTEXITCODE -ne 0){throw 'Installer compilation failed'}
$release=Join-Path $root 'dist\release';New-Item -ItemType Directory -Force -Path $release | Out-Null
& (Join-Path $WixPath 'light.exe') -nologo -ext WixUIExtension -ext WixUtilExtension -sice:ICE91 -out (Join-Path $release 'VesperKeepPlayer-0.1.2-preview.msi') (Join-Path $out 'Player.wixobj')
if($LASTEXITCODE -ne 0){throw 'Installer validation failed'}
# ICE91 only concerns per-machine installs; this package is explicitly per-user.
Get-ChildItem $release -Filter '*.msi' | ForEach-Object {('{0}  {1}' -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(),$_.Name)} | Set-Content (Join-Path $release 'SHA256SUMS.txt') -Encoding ascii