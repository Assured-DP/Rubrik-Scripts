#!/bin/python3
# Simple Version of getting live mount servers

import rubrikSDK # Importing andrew's Rubrik SDK
import json # Importing JSON tools
import getpass # Importing tool for osbscuring passwords


hostname = input("Enter Target Rubrik: ") #Get Rubrik Hostname
username = input("Enter Username: ") #Get Rubrik Username
password = getpass.getpass('Enter Password: ') #inputting password
totpcode = input("Enter Rubrik TOTP: ") #Input TOTP

rubrik = rubrikSDK.getSession(hostname, username, password, totpcode) # Use SDK to authenticate

nodes = rubrikSDK.getNodes() # Get the Nodes from the SDK and store in variable
for each in nodes['data']:
    each['mounts'] = []

allLiveMounts = [] # Create List (Array) variable to hold all live mount information

# Establish all the object types that can have livemounts
objectTypes = ["VirtualMachine", "NutanixVirtualMachine", "HypervVirtualMachine", "WindowsVolumeGroup", "MssqlDatabase"]

# Iterate through the list of object types and collect all their livemount data
for each in objectTypes:
    print("Loading "+each+"...")
    # First gather all of the live mounts
    liveMounts = rubrikSDK.getLivemount(each, refreshCache=True)
    print("Iterating "+str(len(liveMounts['data']))+" livemounts")
    # Now iterate through them and pull detailed LM information for each mount
    for obj in liveMounts['data']:
        detailData = rubrikSDK.getLivemount(each, objId=obj['id'])
        obj['detail'] = detailData
        obj['objType'] = each
        allLiveMounts.append(obj) # Append the basic and detailed LM info to the Established List to merge all types

# Iterate through the full list of all livemounts of all types
print("Building reference information...")
for each in allLiveMounts:
    if each['objType'] == "VirtualMachine": # get node references for vmware types
        for node in nodes['data']:
            try:
                if each['detail']['nasIp'] == node['ipAddress']:
                    vmdata = rubrikSDK.getVm(each['vmId'])
                    each['name'] = vmdata['name']
                    node['mounts'].append(each) # Append the LM data to the node entry to make counting easier
            except:
                print("Failed to append detail")
                print(json.dumps(each['detail'], indent=4))
                try:
                    each['detail'] = rubrikSDK.getLivemount("VirtualMachine", objId=each['detail']['vmId'])
                    vmdata = rubrikSDK.getVm(each['vmId'])
                    each['name'] = vmdata['name']
                    node['mounts'].append(each)
                    print("retry attempt to populate succeeded and data appended")
                except:
                    print("retry attempt to populate failed")
    if each['objType'] == "WindowsVolumeGroup": # Volume Groups...
        for node in nodes['data']:
            ipAddress = each['detail']['mountedVolumes'][0]['smbPath'].split('\\')[2]
            if ipAddress == node['ipAddress']:
                node['mounts'].append(each) # Append the LM data to the node entry to make counting easier
    if each['objType'] == "MssqlDatabase": # SQL Databases
        for node in nodes['data']:
            each['name'] = node['sourceDatabaseName']
            ipAddress = each['detail']['links']['sourceDatabase']['href'].split('/')[2]
            if ipAddress == node['ipAddress']:
                node['mounts'].append(each) # Append the LM data to the node entry to make counting easier

# Output what nodes have LMs that are of supported types.
print("Node LM Counts:")
knownCount = 0
for node in nodes['data']:
    knownCount = knownCount + len(node['mounts'])
    print(node['hostname']+" has "+str(len(node['mounts']))+" Live Mounts")
    for mount in node['mounts']:
        try:
            print("    "+mount['name'])
        except:
            continue

print(str(knownCount)+" accounted for out of "+str(len(allLiveMounts))+" total Live Mounts")