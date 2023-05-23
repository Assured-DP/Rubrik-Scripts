## Script to create SLA Domain

Import-Module rubrik

$rubrikTarget = "se-rubrik.cust02.local"

$token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZTFjMjllNC04OTQ1LTQzYjAtYTE0OC1iNzdmZTk0NzBiYzYiLCJpc01mYVJlbWVtYmVyVG9rZW4iOmZhbHNlLCJpc3MiOiI1ZmViZmEzMi05NmY0LTRlNzItYjM1OC05NjkzMTg3NDAzMTMiLCJpYXQiOjE2ODQ4NzQ2MTMsImp0aSI6IjkwNTA2ODE5LTdkYTktNDU2My04ZmEzLWVhZGYzYWUxMTI0ZiJ9.sRQHi85FxrPwbgBT2RKtL5MU14rqvUlEtRz5-GHjZ2s"


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