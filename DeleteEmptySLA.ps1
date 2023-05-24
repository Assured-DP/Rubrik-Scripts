# Delete Empty SLA Domains
# Requires Two Person Rule (TPR) to be disabled

Import-Module Rubrik

$rubrikTarget = "se-rubrik.cust02.local"

$token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZTFjMjllNC04OTQ1LTQzYjAtYTE0OC1iNzdmZTk0NzBiYzYiLCJpc01mYVJlbWVtYmVyVG9rZW4iOmZhbHNlLCJpc3MiOiI1ZmViZmEzMi05NmY0LTRlNzItYjM1OC05NjkzMTg3NDAzMTMiLCJpYXQiOjE2ODQ5MzMzMDMsImp0aSI6ImI5OThkMjFiLTEwODAtNGIyNi05OTQ2LTFkNjk2ZDY2NDhlMiJ9.Sd21PTmRgN-VaUKTS5tNqz_ci010aBQLiwhMYxeJ2z8"

Connect-Rubrik -Server $rubrikTarget -Token $token

$slaList = Get-RubrikSLA | Where-Object {$_.numProtectedObjects -eq 0}

foreach ($sla in $slaList) { Remove-RubrikSla $sla.id }