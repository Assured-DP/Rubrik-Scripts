<#

To prepare to use this script complete the following steps:
1) Download the Rubrik Powershell module from Github or the Powershell Library.
  a) Install-Module Rubrik
  b) Import-Module Rubrik
  c) Get-Command -Module Rubrik
  d) Get-Command -Module Rubrik *RubrikDatabase*
  e) Get-Help Get-RubrikVM -ShowWindow
  f) Get-Help New-RubrikMount -ShowWindow
  g) Get-Help Get-RubrikRequest -ShowWindow

2) Create a credentials file for the Rubrik Powershell Module with your administrative Rubrik username and password.
  a) $cred = Get-Credential
    i) Enter the Rubrik Administrator credentials to use for this script.
  b) $cred | Export-Clixml C:\temp\RubrikCred.xml -Force
3) Create a target SLA which will capture, retain and archive snapshots using the desired retention.
4) Invoke this script to create on demand snapshots from SLAs.

This script requires:
- Powershell 5.1
- Rubrik PowerShell Module
- Rubrik PowerShell Credentials File

#>

# Rubrik Node and Load Credentials
$credfile = "C:\Temp\RubrikClus1Cred.xml"
$rubrikNode = "10.51.21.108"

# On Demand SLA and Target Object Type
$targetslaname = "test"
$objecttype = "mssql" ## Currently supported Types: fileset, mssql, vmware/vm

# What is the Target object you are backing up? (Enter the VM Name, SQL DB name, or FileSet Name)
$targetobject = "TestDataNew002"

# Set these options for Fileset backups
$filesetHostName = "10.51.25.104" # Name of Server Hosting Fileset (as it appears in Rubrik)

# Set MSSQL Host Name HERE
$mssqlhostname = "10.51.25.104" # Name of Server Hosting SQL (as it appears in Rubrik)

# Setup the Rubrik Module
Import-Module Rubrik

# Connect to the Rubrik Cluster
Connect-Rubrik -Server $rubrikNode -Credential (Import-Clixml $credfile)
    
If ($objecttype -eq "fileset") {
    $bakupjob = Get-RubrikFileset -Name $filesetname -HostName $targetobject | New-RubrikSnapshot -SLA $targetslaname -Confirm:$false
    } ElseIf ($objecttype -eq "vmware/vm") {
    $backupjob = Get-RubrikVM -Name $targetobject | New-RubrikSnapshot -SLA $targetslaname -Confirm:$false
    } ElseIf ($objecttype -eq "mssql") {
    $backupjob = Get-RubrikDatabase -Name $targetobject -HostName $mssqlhostname | New-RubrikSnapshot -SLA $targetslaname -Confirm:$false
    } 

do{
	start-sleep -seconds 5
	$backupjob = $backupjob | Get-RubrikRequest -Type $objecttype -ErrorAction SilentlyContinue
	Write-Host ($backupjob | Format-List | Out-String )
} until(($backupjob | Where-Object {@('QUEUED','RUNNING','FINISHING') -contains $_.status} | Measure-Object).Count -eq 0)