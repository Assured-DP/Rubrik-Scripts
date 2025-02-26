﻿<#
.SYNOPSIS
    Script will read a JSON file that contains database information to restore a database from one instance to another. 
.DESCRIPTION
    Script will read a JSON file that contains database information to restore a database from one instance to another. 
    You can also provide your own JSON file as long as it has the information required to do a restore. 
.EXAMPLE
    PS C:\> .\Export-RubrikDatabaseJob.ps1 -JobFile .\JobFile.json
    
.NOTES
    Name:       Export Rubrik Databases Job 
    Created:    7/1/2019
    Author:     Chris Lumnah
    Updated:    6/5/2020
        Removed requirement for FailoverClusters Powershell Module. This has been moved to the Prepare script only
        
    Execution Process:
    You should run .\Prepare-ExportDatabaseJobFile.ps1 with appropriate values to create the JSON file. Once you have the file created, you can modify values based on the the below directions. 
    Modify the JSON file to include the appropriate values. 
        RubrikCluster                   Values in this section are free to be changed as you see fit
            Server:                     IP Address to the Rubrik Cluster
            Credential:                 Should contain the full path and file name to a credential file
            Token:                      API Token that is generated inside Rubrik UI
        Databases  
            Source                     Values in this sectionm should not be changed!
                DatabaseName                Database name on the Source SQL Server Instance or in an Availability Group    
                Databaseid                  Rubrik assigned value that represents the Source Database
                ServerInstance              Source SQL Server Instance. 
                AvailabilityGroupName       Source SQL Availability Group
                instanceId                  Rubrik assinged value that represents the Source location of the database
            Target                      
                DatabaseName    Can be user changed. Represents the what the database name should be set to on the target SQL Server
                ServerInstance  Here as a human readable representation of instanceID
                instanceId      Rubrik assigned value representing the target SQL Server Instance
                RecoveryPoint   Can be user changed. A time  to which the database should be restored to. There are a few different possibilities
                                latest:         This will tell Rubrik to export the database to the latest recovery point Rubrik knows about
                                                This will include the last full and any logs to get to the latest recovery point
                                last full:      This will tell Rubrik to restore back to the last full backup it has
                                Format:         (HH:MM:SS.mmm) or (HH:MM:SS.mmmZ) - Restores the database back to the local or UTC time (respectively) at the point in time specified within the last 24 hours
                                Format:         Any valid <value> that PS Get-Date supports in: "Get-Date -Date <Value>"
                                                Example: "2018-08-01T02:00:00.000Z" restores back to 2AM on August 1, 2018 UTC.
                Files           Can be user changed. An array representing the logical name, physical path and file name of a database on the target SQL Server
                FinishRecovery  Can be user changed. Should be set to $true is the database should be brought online or set to $false if the database 
                                should remain in RESTORING state 
#>
param(
    $JobFile = ".\SQLJobsFile.json"
)
Import-Module Rubrik -Force
#region FUNCTIONS
#$Path = ".\Functions"
#Get-ChildItem -Path $Path -Filter *.ps1 | Where-Object { $_.FullName -ne $PSCommandPath } |ForEach-Object {
#    . $_.FullName
#}

'''function Get-TargetFiles{
    param(
        [PSCustomObject]$Files
    )
    #Create a hash table containing all of the files for the database. 
    $TargetFiles = @()
    foreach ($File in $Files){
        $TargetFiles += @{logicalName=$File.logicalName;exportPath=$File.exportPath;newFilename=$File.newFilename}       
    }
    return $TargetFiles
}'''
#endregion

if (!(Test-Path -Path $JobFile)){exit}

$JobFile = (Get-Content $JobFile) -join "`n"  | ConvertFrom-Json

#region Connect to Rubrik
Write-Host("Connecting to Rubrik cluster node $($JobFile.RubrikCluster.Server)...")
switch($true){
    {$JobFile.RubrikCluster.Token}{
        $ConnectRubrik = @{
            Server  = $JobFile.RubrikCluster.Server
            Token   = $JobFile.RubrikCluster.Token
        }
    }
    {$Jobfile.RubrikCluster.Credential}{
        $ConnectRubrik = @{
            Server      = $JobFile.RubrikCluster.Server
            Credential  = Import-CliXml -Path $JobFIle.RubrikCluster.Credential
        }
    }
    default{
        $ConnectRubrik = @{
            Server = $JobFile.RubrikCluster.Server
            #Credential = $Credentials.RangerLab
        }
    }
}

Connect-Rubrik @ConnectRubrik #| Out-Null
#endregion
$JobsToMonitor = @()
foreach ($Database in $JobFile.Databases) {
	$lmResponse = Invoke-RubrikRESTCall -api '1' -Endpoint "mssql/db/mount" -Method GET
	
	foreach ($db in $lmResponse.data){
		if($Database.Source.Databaseid -eq $db.sourceDatabaseId) {
			$Endpoint = "mssql/db/mount/$($db.id)?force=true"
			$remove = Invoke-RubrikRESTCall -api '1' -Endpoint $Endpoint -Method "DELETE"
			Start-Sleep -Seconds 4
		}
	}
}
