# Delete Empty SLA Domains
# Requires Two Person Rule (TPR) to be disabled

Import-Module Rubrik

$rubrikTarget = "se-rubrik.cust02.local"

$token = "<your-api-token>"

Connect-Rubrik -Server $rubrikTarget -Token $token

$slaList = Get-RubrikSLA | Where-Object {$_.numProtectedObjects -eq 0}

foreach ($sla in $slaList) { Remove-RubrikSla $sla.id }