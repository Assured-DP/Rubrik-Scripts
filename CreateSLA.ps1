## Script to create SLA Domain

Import-Module rubrik

$rubrikTarget = "se-rubrik.cust02.local"

$token = "<your-api-token>"

Connect-Rubrik -Server $rubrikTarget -Token $token

Write-Host "Pre-SLA Creation"
Get-RubrikSLA | Format-Table


$slaConfigJson = @"
{
  "name": "Testing API SLA",
  "frequencies": {
    "daily": {
      "frequency": 1,
      "retention": 3 
       }
     },
  "logConfigs": {
    "Mssql": {
      "slaLogFrequencyConfig": {
        "retention": 2880,
        "logFrequencyType": "Minute",
        "frequency": 15
        }
       }
      },
  "allowedBackupWindows": [
      {
       "startTimeAttributes": {
         "minutes": 0,
         "hour": 17
         },
        "durationInHours": 14
       }
    ]
}
"@


$slaConfig = $slaConfigJson | ConvertFrom-Json

#New-RubrikSLA -Name $slaConfig.Name -DailyFrequency $slaConfig.DailyFrequency -DailyRetention $slaConfig.DailyRetention -AdvancedConfig -BackupStartHour $slaConfig.SLAStartHour -BackupStartMinute $slaConfig.SLAStartMinute -BackupWindowDuration $slaConfig.SLADuration 

Invoke-RubrikRESTCall -api 2 -Endpoint sla_domain -Method POST -body $slaConfig

Write-Host "Post SLA Creation"
Get-RubrikSLA | Format-Table