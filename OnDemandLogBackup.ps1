## Performs On Demand backup of Log files for database

# Import Rubrik Powershell Module
Import-Module Rubrik

# Declare local variables. Can use credential file instead of "Get-Credential"
$creds = Get-Credential
$dbname = "TestDataNew002"
$rubrik = "10.51.23.240"

# Connect to Rubrik
Connect-Rubrik -s $rubrik -Credential $creds

# Get the Database Unique ID
$DB = Get-RubrikDatabase -Name $dbname

# Execute Job
$LOGJOB = New-RubrikLogBackup -id $DB.id

# Monitor Job until it completes
do {
    start-sleep -seconds 5
    $job_status = Get-RubrikRequest -id $LOGJOB.id -type mssql
    write-host $job_status
} until($job_status.status -eq "SUCCEEDED") 