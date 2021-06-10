###
###
### Pulls Network Information of Hyper-V environments.
### Requirements:
### Must be from a machine with the following things installed:
### 1) Powershell 5.1+
### 2) Rubrik Module (run powershell as administrator install-module Rubrik)
### 3) Account running it needs access to Hyper-V for Hyper-V without SCVMM
### 4) Server needs SCVMM console installed for SCVMM environments
###
### Script connects to the rubrik specified here:
$rubrikhost = "rbkcluster2"
###
### Script will prompt for the user credentials of the Rubrik, then use the logged-in user for all other calls.
### 
### Script will output a file called "networkdata.json" in the directory the script runs from.
### 
### Script workflow: Checks Rubrik for SCVMM, if it is found, it will pull all infor from SCVMM
### If SCVMM is now found, all hyper-V hosts are pulled and the script cycles through the hosts and pulls all the data.
###
###


Import-Module Rubrik

Connect-Rubrik -Server $rubrikhost -Credential (Get-Credential)

$scvmmlist = Get-RubrikScvmm | where-object {$_.PrimaryClusterId -eq (Get-RubrikClusterInfo).id}
write-host $scvmmlist

$jsonout = @"
{
 "vmlist": []
}
"@ | ConvertFrom-JSON

if ($scvmmlist.length -eq 0)
{
 write-host No SCVMM
 $scvmmexist = $false
} else
{
 write-host SCVMM Found
 $scvmmexist = $true
}

$hostlist = ""

if ($scvmmexist)
{
 Import-Module virtualmachinemanager
 Foreach ($scvmm in $scvmmlist)
 {
 $vmlist = Get-SCVirtualMachine -VMMServer $scvmm.Name | where-object {$_.VirtualizationPlatform -notlike "VMWareESX"}
 Foreach ($vm in $vmlist)
{
  Write-Host $vm.Name
  $buildjson = @"
{
 "nics" : [],
 "host" : "$($targetHost)",
 "vmname" : ""
}
"@ | ConvertFrom-JSON
    $buildjson.vmname = "$($vm.Name)"
    $niclist = Get-SCVirtualMachine -VMMServer $scvmm.Name -Name $vm.name | Get-SCVirtualNetworkAdapter
    Foreach ($nic in $niclist)
    {
     $buildnic = @"
{
  "virtualswitch": "$($nic.SwitchName)",
 "vmnetwork": "$($nic.VMNetwork)",
 "vlan": "$($nic.VLanID)",
 "mac_address": "$($nic.MacAddress)",
 "ipaddresses": "$($nic.IPv4Addresses)"
}
"@ | ConvertFrom-Json
     $buildjson.nics += $buildnic | ConvertTo-Json | ConvertFrom-Json
    }
    $jsonout.vmlist += $buildjson
}
}
} else
{
 $rubrikHyperVlist = Get-RubrikHyperVHost | Where-Object {$_.PrimaryClusterID -eq (Get-RubrikClusterInfo).id} | Select Name
 Foreach ($hypvhost in $rubrikHyperVlist)
 {
    $hostlist += "$($hypvhost.Name)"
 }

 Foreach ($targetHost in $hostList)
 {
  $vmlist = Get-VM -ComputerName $targetHost 
  Write-Host Loading $targetHost

  Foreach ($vm in $vmlist)
  {
   $buildjson = @"
{
 "nics" : [],
 "host" : "$($targetHost)",
 "vmname" : ""
}
"@ | ConvertFrom-JSON
    $buildjson.vmname = "$($vm.Name)"
    $niclist = Get-VM -ComputerName $targetHost -Name $vm.name | Get-VMNetworkAdapter
    Foreach ($nic in $niclist)
    {
     $buildnic = @"
{
 "virtualswitch": "$($nic.SwitchName)",
 "vmnetwork": "$($nic.VMNetwork)",
 "vlan": "$($nic.VLanID)",
 "mac_address": "$($nic.MacAddress)",
 "ipaddresses": "$($nic.IPAddres)"
}
"@ | ConvertFrom-Json
     $buildjson.nics += $buildnic | ConvertTo-Json | ConvertFrom-Json
    }
    $jsonout.vmlist += $buildjson
}

}

}


Write-Host ($jsonout | ConvertTo-Json -Depth 5)
$jsonout | ConvertTo-Json -Depth 5 | Out-File "networkdata.json"
