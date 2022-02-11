<#
.SYNOPSIS
    Script will Restore Source Files to Target System Folder
.DESCRIPTION
    Script performs a fileset Export of the specified folder and all subfolders.
.EXAMPLE
    PS C:\> .\Export-Files.ps1 
    optionally declare variables:
    PS C:\> .\Export-Files.ps1 -rubrik "10.1.1.1" -srcPath "G:\\MSSQL\\Daily"
 
#>
param(
    $srcHost = "10.240.43.51",
    $srcFileset = "SQL Daily 6pm",
    $srcPath = "G:\MSSQL\Daily\6pm",
    $dstPath = "G:\Backups for DB Restore\",
    $dstHost = "192.168.110.51",
    $rubrik = "uscust048mon001"
)
Import-Module Rubrik -Force

$rubrikCreds = Get-Credential

# Or Pull from credential file:
# $rubrikCreds = Import-CliXml -Path 'C:\My\Path\Cred.xml'

Connect-Rubrik -Credential $rubrikCreds -Server $rubrik

#$srcHostObj = Get-RubrikHost | Where-Object {$_.Name -eq $srcHost}

$srcFilesetObj = Get-RubrikFileset | Where-Object {$_.Name -eq $srcFileset} | Where-Object {$_.HostName -eq $srcHost}

$dstHostObj = Get-RubrikHost | Where-Object {$_.Name -eq $dstHost}

$hostId = $dstHostObj.id

$latestSnapshot = Get-RubrikSnapshot -Latest -id $srcFilesetObj.id

$invokebody = @{}
$invokebody.Add("sourceDir",$srcPath)
$invokebody.Add("destinationDir",$dstPath)
$invokebody.Add("hostId",$hostId)
$invokebody.Add("ignoreErrors",$false)

$endpoint = "fileset/snapshot/$($latestSnapshot.id)/export_file"

$status = Invoke-RubrikRESTCall -api '1' -Endpoint $endpoint -Method 'POST' -Body $invokebody

Write-Host $status