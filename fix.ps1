$count = 0
$files = Get-ChildItem -Path site_payload/content/posts -Filter *.md

foreach ($f in $files) {
    $content = [System.IO.File]::ReadAllText($f.FullName)
    
    $newContent = [regex]::Replace($content, '(?s)```.*?```', {
        param($m)
        $m.Value.Replace('{{< ad300 >}}', '')
    })
    
    $newContent = [regex]::Replace($newContent, '(?s)`[^`]*?`', {
        param($m)
        $m.Value.Replace('{{< ad300 >}}', '')
    })
    
    # Also check HTML blocks (e.g., <pre>...</pre>)
    $newContent = [regex]::Replace($newContent, '(?s)<pre>.*?</pre>', {
        param($m)
        $m.Value.Replace('{{< ad300 >}}', '')
    })
    
    if ($content -ne $newContent) {
        [System.IO.File]::WriteAllText($f.FullName, $newContent)
        $count++
        Write-Host "Fixed $($f.Name)"
    }
}

Write-Host "Total files fixed: $count"
