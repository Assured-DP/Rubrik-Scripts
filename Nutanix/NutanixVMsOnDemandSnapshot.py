#!/usr/bin/env python3

"""
NutanixVMsOnDemandSnapshot.py

Author: Rob Vary
Email: robert.vary@assured-dp.com
Date: 2025-04-22

Description:
This script connects to a Rubrik cluster and triggers on-demand snapshots
for specified Nutanix VMs by name. The script uses the Rubrik CDM Python SDK
to interact with the Rubrik cluster via API.

Usage Example:
    python NutanixVMsOnDemandSnapshot.py --cluster ukcu0001rcl0001 --token idcmykntouabtxeegaarokmn --vms VM1,VM2,VM3
"""

import rubrik_cdm
import argparse
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def take_on_demand_snapshots(cluster_name, api_token, vm_names_csv):
    rubrik = rubrik_cdm.Connect(node_ip=cluster_name, api_token=api_token)

    vm_names = [name.strip() for name in vm_names_csv.split(',')]

    for vm_name in vm_names:
        print(f"\nProcessing VM: {vm_name}")

        # Search for the VM
        search_result = rubrik.get(api_endpoint=f"/nutanix/vm?name={vm_name}", api_version="internal")
        vm_id = None
        sla_id = None

        for obj in search_result['data']:
            if 'NutanixVirtualMachine' in obj.get('id'):
                vm_id = obj['id']
                sla_id = obj['effectiveSlaDomainId']
                break

        if not vm_id:
            print(f"Could not find VM '{vm_name}' in cluster '{cluster_name}'")
            continue

        if not sla_id:
            print(f"Could not find SLA Domain ID for VM '{vm_name}'")
            continue

        body = json.dumps({
            "slaId": sla_id
            })

        # Take snapshot
        try:
            print(f"Taking on-demand snapshot for VM '{vm_name}' (ID: {vm_id})")
            result = rubrik.post(api_endpoint=f'/nutanix/vm/{vm_id}/snapshot', api_version='internal', config=body, timeout=30)
            print(f"Snapshot job started for '{vm_name}': {result.get('id', 'No job ID returned')}")
        except Exception as e:
            print(f"Error taking snapshot for VM '{vm_name}': {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", required=True, help="Nutanix cluster name")
    parser.add_argument("--token", required=True, help="Rubrik API token")
    parser.add_argument("--vms", required=True, help="Comma-separated list of VM names")
    args = parser.parse_args()

    take_on_demand_snapshots(args.cluster, args.token, args.vms)
