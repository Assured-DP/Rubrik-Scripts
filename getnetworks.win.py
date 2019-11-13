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
# import time
# import datetime

from requests.auth import HTTPBasicAuth
# from dateutil import parser

# Global Variables
# drbrikip = "rbkcluster1"
# basedrurl = "https://"+drbrikip+"/api/"
# urlclusterid = basedrurl+"v1/cluster/me"
# urlvmcall = basedrurl+"v1/vmware/vm"

# Silence warnings
# requests.packages.urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def establishAnswers():
	answerstring = "{ \"nutanixhostname\": \"\", \"nutanixuser\": \"\", \"vcenter\": \"\", \"vcenteruser\": \"\", \"custnumber\": \"\"}"
	answerjson = json.load(answerstring)
	return answerjson

def manageAnswerFile(answerfile):
	answerpath = 'C:\Windows\Temp\.answerfile.json'
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

# Walkthrough the New Answer Process
def recordAnswer(userinput, answerreference):
	global answerjson
	if userinput =="":
		return answerjson[answerreference]
	else:
		answerjson[answerreference] = userinput
		answerjson = manageAnswerFile(answerjson)
		return userinput

def get_server_session(self, username, password):
    #Creating REST client session for server connection, after globally setting
    #Authorization, content type, and character set for the session.
    session = requests.Session()
    session.auth = (username, password)
    session.verify = False
    session.headers.update(
        {'Content-Type': 'application/json; charset=utf-8'})
    return session

#Prints the cluster information and loads JSON objects to be formatted.

def getClusterInformation(self):
    #This sets up 'pretty print' for the object.
    pp = pprint.PrettyPrinter(indent=2)
    clusterURL = self.base_url + "/cluster"
    print("Getting cluster information for cluster %s" % self.serverIpAddress)
    serverResponse = self.session.get(clusterURL)
    print("Response code: %s" % serverResponse.status_code)
    return serverResponse.status_code, json.loads(serverResponse.text)		
		

# Function for Opening the nutanix Session
def connectNutanix(nutanixhost,username,password):
	#tempsess = requests.Session()
	#tempsess.verify = False
	nutsess = requests.Session()
	nutsess.verify = False
	baseurl = "https://"+nutanixhost+":9440/api/nutanix/"
	#nutsess.headers.update({'Content-Type': 'application/json; charset=utf-8'})
	nutsess.auth = (username,password)
	testurl = baseurl + "v2.0/cluster"
	#print "URL = "+testurl
	#print "user = "+username
	nutresponse = nutsess.get(url=testurl)
	#print nutresponse
	#print nutsess
	return nutsess

# Function to create Network UUID List
def buildNetworkJson(nutsess):
	networkurl = basenuturl+"v2.0/networks"
	nutnetresponse = nutsess.get(url=networkurl)
	nutnetjson = nutnetresponse.json()
	total = nutnetjson['metadata']['total_entities']
	loopcount = 0
	networkstring = "{ \"networks\": [ "
	for network in nutnetjson['entities']:
		networkstring = networkstring+"{ \"uuid\": \""+network['uuid']+"\", "
		networkstring = networkstring+"\"name\": \""+network['name']+"\" }"
		loopcount = loopcount + 1
		if loopcount < total:
			networkstring = networkstring + ", "
	networkstring = networkstring+"] }"
	networkjson = json.loads(networkstring)
	return networkjson

def convertNetUUID(uuid):
	for net in nutnetjson['networks']:
		if net['uuid'] == uuid:
			return net['name']
	
def buildVMNetworkJson(nutnetjson,nutanixsess):
	vmurl = basenuturl+"v2.0/vms"
	vmresponse = nutanixsess.get(url=vmurl)
	vmlistjson = vmresponse.json()
	total = vmlistjson['metadata']['count']
	netjsonstring = "{ \"vmlist\": [ "
	vmloop = 0
	for vm in vmlistjson['entities']:
		netjsonstring = netjsonstring + "{ \"vmname\": \""+vm['name']+"\", \"nics\": ["
		networkurl = basenuturl+"v2.0/vms/"+vm['uuid']+"/nics"
		niclistresponse = nutanixsess.get(url=networkurl)
		niclistjson = niclistresponse.json()
		nictotal = niclistjson['metadata']['total_entities']
		nicloop = 0
		for nic in niclistjson['entities']:
			netjsonstring = netjsonstring+"{ \"mac_address\": \""+nic['mac_address']+"\", "
			netjsonstring = netjsonstring+"\"network_uuid\": \""+nic['network_uuid']+"\", "
			netjsonstring = netjsonstring+"\"name\": \""+convertNetUUID(nic['network_uuid'])+"\"}"
			nicloop = nicloop + 1
			if nicloop < nictotal:
				netjsonstring = netjsonstring+", "
		vmloop = vmloop + 1
		if vmloop < total:
			netjsonstring = netjsonstring+"]}, "
		else:
			netjsonstring = netjsonstring+"]}]"
	netjsonstring = netjsonstring+"}"
	#print netjsonstring
	completejson = json.loads(netjsonstring)
	return completejson

def convertandwrite(bkjson,name):
	filepath = name + "_backup.json"
	print("Creating " + filepath)
	with open(filepath, 'w') as dmpfile:
		json.dump(bkjson, dmpfile)
	
# Main Body of Code Starts Here
passone = "one"
passtwo = "two"

# Setup Answer File
answerpath = 'C:\Windows\Temp\.answerfile.json'
answerjson = { "nutanixhostname": "a", "nutanixuser": "b", "vcenter": "c", "vcenteruser": "d", "custnumber": "e"}
if os.path.exists(answerpath):
	answerjson = json.load(open(answerpath))
else:
	with open(answerpath, 'w') as dmpfile:
		json.dump(answerjson, dmpfile)

# Collect User Information
os.system('clear')
nutanixip = input("Enter Nutanix Cluster IP or Hostname [{0}]: ".format(answerjson['nutanixhostname']))
nutanixip = recordAnswer(nutanixip, "nutanixhostname")
drusername = input("Enter Nutanix username [{0}]: ".format(answerjson['nutanixuser']))
drusername = recordAnswer(drusername, "nutanixuser")
while passone != passtwo:
	passone = getpass.getpass('Enter Password: ')
	passtwo = getpass.getpass('Re-Enter Password: ')
	if passone != passtwo:
		print("Passwords do not match")
nutanixpassword = passone
passone = "blank"
passtwo = "blank"
basenuturl = "https://"+nutanixip+":9440/api/nutanix/"

# Create Nutanix Session
print("Connecting to Nutanix at "+basenuturl)
nutanixsess = connectNutanix(nutanixip, drusername, nutanixpassword)
clusterurl = basenuturl+"v2.0/cluster"
clusresponse = nutanixsess.get(url=clusterurl)
clusjson = clusresponse.json()

# Setup Network JSON list
nutnetjson = buildNetworkJson(nutanixsess)

# Create VM Network JSON Output
vmnetworkjson = buildVMNetworkJson(nutnetjson,nutanixsess)

convertandwrite(vmnetworkjson,clusjson['name'])
