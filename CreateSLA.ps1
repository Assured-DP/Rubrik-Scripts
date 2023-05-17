## Script to create SLA Domain

Import-Module rubrik

$rubrikTarget = "se-rubrik.cust02.local"

$token = "<your-api-token>"


Connect-Rubrik -Server $rubrikTarget -Token $token

Write-Host "Pre-SLA Creation"
Get-RubrikSLA | Format-Table


$slaConfigJson = @"
{
"Name": "Testing API SLA",
"DailyFrequency": 1,
"DailyRetention": 30,
"WeeklyFrequency": 1,
"WeeklyRetention": 6,
"DayOfWeek": "Sunday",
"MonthlyFrequency": 1,
"MonthlyRetention": 12,
"DayOfMonth": "LastDay",
"YearlyFrequency": 1,
"YearlyRetention": 3,
"DayOfYear": "LastDay"
}
"@

$slaConfig = $slaConfigJson | ConvertFrom-Json

New-RubrikSLA -Name $slaConfig.Name -DailyFrequency $slaConfig.DailyFrequency -DailyRetention $slaConfig.DailyRetention -WeeklyFrequency $slaConfig.WeeklyFrequency -WeeklyRetention $slaConfig.WeeklyRetention -DayOfWeek $slaConfig.DayOfWeek -MonthlyFrequency $slaConfig.MonthlyFrequency -MonthlyRetention $slaConfig.MonthlyRetention -DayOfMonth $slaConfig.DayOfMonth -YearlyFrequency $slaConfig.YearlyFrequency -YearlyRetention $slaConfig.YearlyRetention -DayOfYear $slaConfig.DayOfYear

Write-Host "Post SLA Creation"
Get-RubrikSLA | Format-Table