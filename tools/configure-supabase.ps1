$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$secretPath = Join-Path $projectRoot 'server/App_Data/saas/supabase-connection.xml'
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Plans to Space - Database connection'
$form.Width = 650
$form.Height = 230
$form.StartPosition = 'CenterScreen'
$label = New-Object System.Windows.Forms.Label
$label.Text = 'Paste the full postgresql:// connection URI below. It stays hidden.'
$label.SetBounds(15,15,600,30)
$inputBox = New-Object System.Windows.Forms.TextBox
$inputBox.SetBounds(15,50,600,28)
$inputBox.UseSystemPasswordChar = $true
$inputBox.ShortcutsEnabled = $true
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.SetBounds(15,85,600,40)
$saveButton = New-Object System.Windows.Forms.Button
$saveButton.Text = 'Validate and save'
$saveButton.SetBounds(15,135,160,30)
$inputBox.Add_TextChanged({ $statusLabel.Text = "Characters entered: $($inputBox.Text.Length)" })
$saveButton.Add_Click({
    $candidate = $inputBox.Text.Trim()
    $uri = $null
    $valid = [Uri]::TryCreate($candidate, [UriKind]::Absolute, [ref]$uri)
    if (-not $valid -or $uri.Scheme -notin @('postgresql','postgres') -or -not $uri.Host -or $uri.UserInfo -notmatch '.+:.+' -or $candidate -match 'YOUR.?PASSWORD') {
        $statusLabel.Text = 'Not a complete URI. Copy the full connection string and replace its password placeholder.'
        return
    }
    $form.Tag = ConvertTo-SecureString $candidate -AsPlainText -Force
    $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $form.Close()
})
$form.Controls.AddRange(@($label,$inputBox,$statusLabel,$saveButton))
$form.AcceptButton = $saveButton
$result = $form.ShowDialog()
$secret = $form.Tag
$inputBox.Clear()
$form.Dispose()
if ($result -ne [System.Windows.Forms.DialogResult]::OK) { throw 'Setup cancelled. Existing configuration was not changed.' }
New-Item -ItemType Directory -Force -Path (Split-Path $secretPath -Parent) | Out-Null
$secret | Export-Clixml -LiteralPath $secretPath
Write-Host 'URI format validated and saved encrypted. Database connectivity has not yet been tested. No credential was printed.'
