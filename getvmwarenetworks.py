#!/bin/python
# Python 
# Executing customer runbook script

# Modules
import json
import requests
import urllib3
import sys
import os
import getpass
import time
import re
import atexit
import pyVim
import pyVmomi
import datetime
import threading
import syslog
from pyVim import connect
from pyVmomi import vim
from dateutil import parser


## Global Variables
answerpath = '.getvmwarenetworks.json'
answerjson = { "vcenter": "c", "vcenteruser": "d" }
vcenterpassword = ""

def establishAnswers():
    answerstring = "{ \"vcenter\": \"\", \"vcenteruser\": \"\"}"
    answerjson = json.load(answerstring)
    return answerjson

def manageAnswerFile(answerfile):
    answerpath = '/home/adpengineer/DR/.getvmwarenetworks.json'
    if os.path.exists(answerpath):
        loadedanswers = json.load(open(answerpath))
        if loadedanswers == answerfile:
            return answerfile
        else:
            with open(answerpath, 'w') as dmpfile:
                json.dump(answerfile, dmpfile)
            return answerfile
    else:
        answerfile = establishAnswers()
        with open(answerpath, 'w') as dmpfile:
            json.dump(answerfile, dmpfile)
    return answerfile

def recordAnswer(userinput, answerreference):
    global answerjson
    if userinput =="":
        return answerjson[answerreference]
    else:
        answerjson[answerreference] = userinput
        answerjson = manageAnswerFile(answerjson)
        return userinput

# Get Object Function for pyVmomi
def get_obj(content, vimtype, name):
    """
    Get the vsphere object associated with a given text name    
    """
    obj = "No Match"
    container = content.viewManager.CreateContainerView(content.rootFolder,vimtype, True)
    for view in container.view:
        if view.name == name:
            obj = view
            break
        #print str(name)+" in "+str(view.summary.network)
        #print str(view.summary)
        if str(name) in str(view.summary.network):
            print ("name found: "+str(view.summary.name))
    return obj

# Function for Connecting to vCenter
def ConnectVcenter():
    print (" ")
    passone = "one"
    passtwo = "two"
    global answerjson
    global vcenterpassword
    vCenterHost = input("Enter vCenter IP or Hostname [{0}]: ".format(answerjson['vcenter']))
    vCenterHost = recordAnswer(vCenterHost, "vcenter")
    vCenterUsername = input("Enter vCenter username [{0}]: ".format(answerjson['vcenteruser']))
    vCenterUsername = recordAnswer(vCenterUsername, "vcenteruser")
    while passone != passtwo:
        passone = getpass.getpass('Enter vCenter Password: ')
        passtwo = getpass.getpass('Re-Enter vCenter Password: ')
        if passone != passtwo:
            print("Passwords do not match")
    connection = connect.ConnectNoSSL(vCenterHost, 443, vCenterUsername, passone)
    vcenterpassword = passone
    return connection

def refreshVcenter():
    print ("Refreshing vCenter session...")
    connection = connect.ConnectNoSSL(answerjson['vcenter'], 443, answerjson['vcenteruser'], vcenterpassword)
    return connection   

def getNetworkName(backing):
    global vcenter
    try:
        vcstuff = vcenter.RetrieveContent()
    except:
        vcenter = refreshVcenter()
        vcstuff = vcenter.RetrieveContent()
    print("getNetworkName: "+backing.port.portgroupKey)
    network_name = get_obj(vcstuff, [vim.Network], str(backing.port.portgroupKey))
    return network_name
    
    
    

# Change VM Network
def getVMNetwork(vmuuid):
    global vcenter
    try:
        vcstuff = vcenter.RetrieveContent()
    except:
        vcenter = refreshVcenter()
        vcstuff = vcenter.RetrieveContent()
    custvm = vcstuff.searchIndex.FindByUuid(None, vmuuid, True)
    #print custvm.config
    dvs_port_connection = []
    device_change = []
    devcount = 0
    tasklist = []
    netlistsrc = []
    srcnetname = ""
    VM = {}
    NIC = {}
    VM['NIC'] = []
    VM['name'] = str(custvm.config.name)
    #print custvm.config.name
    for device in custvm.config.hardware.device:
        if isinstance(device, vim.vm.device.VirtualEthernetCard):
            #print str(device)
            NIC['mac'] = str(device.macAddress)
            #print "MAC: "+str(device.macAddress)
            #print "Summary: "+str(device.deviceInfo.summary)
            #print "deviceInfo.label: "+str(device.deviceInfo.label)
            #print device
            NIC['label'] = str(device.deviceInfo.label)
            #netname = getNetworkName(device.backing)
            try:
                NIC['portkey'] = str(device.backing.port.portgroupKey)
                dvs = True
            except:
                #print device.backing
                NIC['portkey'] = str(device.backing.network)
                NIC['netname'] = str(device.backing.deviceName)
                dvs = False
            #NIC['netname'] = netname
            if dvs:
                for pkey in dnetworks:
                    if (NIC['portkey'] in pkey['portgroup']) or (pkey['key'] in NIC['portkey']):
                        NIC['netname'] = pkey['name']
            #print str(device.backing.port.portgroupKey)+" and "+netname
            #print "deviceInfo.dynamicProperty.network"+str(custvm.config)
            VM['NIC'].append(NIC.copy())
            #with open(csvfile, 'a') as dmpfile:
            #   dmpfile.write(VM['name']+","+VM['NIC'][devcount]['mac']+","+VM['NIC'][devcount]['netname']+","+VM['NIC'][devcount]['portkey']+", "+VM['NIC'][devcount]['label']+"\n")
            #print json.dumps(VM, indent=4)
            #pause = input("wait stuff")
            devcount = devcount + 1
            #if VM['name'] == "usdc01adpweb001 - Portal v2":
            #   print device.backing
    vmjson['data'].append(VM.copy())


# Setup Answer File
answerpath = '.getvmwarenetworksanswers.json'
answerjson = { "vcenter": "c", "vcenteruser": "d" }
if os.path.exists(answerpath):
    answerjson = json.load(open(answerpath))
else:
    with open(answerpath, 'w') as dmpfile:
        json.dump(answerjson, dmpfile)
        

# Connect to vCenter
vcenterpassword = ""
vcenter = ConnectVcenter()
atexit.register(connect.Disconnect, vcenter)

vcstuff = vcenter.RetrieveContent()
container = vcstuff.rootFolder
vccontainerview = vcstuff.viewManager.CreateContainerView(container, [vim.VirtualMachine], True)
switchcontainer = vcstuff.viewManager.CreateContainerView(container, [vim.Network], True)
netlist = switchcontainer.view
dnetworks = []
netw = {}
for net in netlist:
    name = net.summary.name
    #print name
    netw['name'] = name
    portgroup = str(net.summary.network)
    try:
        key = str(net.config.key)
    except:
        key = "'NoDVS'"
        key = portgroup
    netw['portgroup'] = portgroup.strip("'")
    netw['key'] = key.strip("'")
    dnetworks.append(netw.copy())
vmlist = vccontainerview.view
#csvfile = './niclist.csv'
#with open(csvfile, 'w+') as dmpfile:
#   dmpfile.write("name, mac, netname, portkey, label")

vmjson = {
    "data": []
    }

vmcount = 0 
for vms in vmlist:
    getVMNetwork(vms.config.uuid)
    vmcount = vmcount + 1
    print("Processed "+str(vmcount)+" VMs...", end='\r')
        
outputfile = './vm_network_list.json'
print("Writing Output File...")
with open(outputfile, 'w+') as dumpydump:
	dumpydump.write(json.dumps(vmjson, indent=4))

print("File "+outputfile+ "created")