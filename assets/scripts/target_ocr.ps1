$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$StorageFileType = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$RandomAccessStreamType = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage, ContentType = WindowsRuntime]
$BitmapDecoderType = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$SoftwareBitmapType = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$OcrResultType = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]

$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
        $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1
    } | Select-Object -First 1)

function Await($operation, $resultType) {
    $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    return $task.Result
}

try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync([string]$request.path)) $StorageFileType
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) $RandomAccessStreamType
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) $BitmapDecoderType
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) $SoftwareBitmapType
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        @{ ok = $false; reason = 'ocr_language_unavailable'; lines = @() } | ConvertTo-Json -Compress
        exit 0
    }
    $result = Await ($engine.RecognizeAsync($bitmap)) $OcrResultType
    $lines = @($result.Lines | ForEach-Object {
        $words = @($_.Words | ForEach-Object {
            $rect = $_.BoundingRect
            @{ text = [string]$_.Text; left = [double]$rect.X; top = [double]$rect.Y;
               width = [double]$rect.Width; height = [double]$rect.Height }
        })
        @{ text = [string]$_.Text; words = $words }
    })
    @{ ok = $true; reason = 'recognized'; lines = $lines } | ConvertTo-Json -Compress -Depth 8
} catch {
    @{ ok = $false; reason = 'ocr_error'; error = $_.Exception.Message; lines = @() } | ConvertTo-Json -Compress
}
