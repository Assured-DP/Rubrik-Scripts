#!/bin/python
# Python
# Recover Specific file from source VM and write it to a specific target path
# Written by Andrew Eva: andrew.eva@assured-dp.com

# Required Modules
import json
import requests
import urllib3
import getpass
import os
import time
import shutil

# Silence warning messages
requests.packages.urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Function for Opening the Rubrik Session
def connectRubrik(dripaddress,username,password):
	#tempsess = requests.Session()
	#tempsess.verify = False
	drrbksess = requests.Session()
	drrbksess.verify = False
	baseurl = "https://"+dripaddress+"/api/"
	#tempsess.auth = (username, password)
	drsessurl = baseurl + "v1/session"
	#print "Generating Token"
	drtokenresponse = requests.request('POST', url=drsessurl, auth=(username,password), verify=False)
	#print "Token Reponse: "+str(drtokenresponse)
	drtokenjson = drtokenresponse.json()
	drtoken = drtokenjson['token']
	drbearer = "Bearer " + drtoken
	drheader = {'Authorization': drbearer}
	#print "Header Assembled: "+str(drheader)
	drrbksess.headers = drheader
	testurl = baseurl + "v1/cluster/me"
	drtestconnect = drrbksess.get(url=testurl)
	drtestresponse = drtestconnect.status_code
	#print "Token Auth Test: "+str(drtestresponse)
	return drrbksess, drbearer;
	
# Get Snapshot for a VM - Requires customer to choose the snapshot
def getSnapshot(vmid):
	snapurl = basedrurl+"v1/vmware/vm/"+vmid+"/snapshot"
	snapresponse = drsession.get(url=snapurl)
	snapjson = snapresponse.json()
	samesame = True
	showcount = 10
	while samesame:
		print ("Select Available Snap: ")
		for n in xrange(showcount):
			print str(n+1)+") "+str(snapjson['data'][n]['date'])

# VMID	
def getVMID():
	vmurl = basedrurl+"v1/vmware/vm"
	entername = raw_input("Enter VM Name: ")
	vmsearchurl = vmurl+"?name="+str(entername)
	vmresponse = drsession.get(url=vmsearchurl)
	vmjson = vmresponse.json()
	samesame = True
	while samesame:
		if vmjson['total'] == 1:
			return vmjson['data'][0]['id']
		if vmjson['total'] == 0:
			print (entername+" Not Found")
			entername = raw_input("Enter VM Name: ")
			vmsearchurl = vmurl+"?name="+str(entername)
			vmresponse = drsession.get(url=vmsearchurl)
			vmjson = vmresponse.json()
		if vmjson['total'] > 1:
			print ("Multiple Matches: ")
			vmcount = 0
			for vm in vmjson['data']:
				print (str(vmcount+1)+") "+vm['name'])
				vmcount = vmcount + 1
			selection = raw_input("Enter Correct Number or X to re-enter: ")
			if selection.lower() == "x":
				entername = raw_input("Enter VM Name: ")
				vmsearchurl = vmurl+"?name="+str(entername)
				vmresponse = drsession.get(url=vmsearchurl)
				vmjson = vmresponse.json()
			else:
				intselect = int(selection)-1
				return vmjson['data'][intselect]['id']

# Get File Path and Snapshot ID to recover
def getRecoverFile(vmid):
	filename = raw_input("Enter File Name: ")
	filesearchurl = basedrurl+"v1/vmware/vm/"+vmid+"/search?path="+filename
	samesame = True
	while samesame:
		searchresponse = drsession.get(url=filesearchurl)
		searchjson = searchresponse.json()
		if searchjson['total'] == 0:
			filename = raw_input("No Matches. Please Enter File Name: ")
			filesearchurl = basedrurl+"v1/vmware/vm/"+vmid+"/search?path="+filename
		if searchjson['total'] == 1:
			pathchoice = 1
			samesame = False
		if searchjson['total'] > 1:
			if searchjson['total'] > 15:
				maxlist = 15
			else:
				maxlist = searchjson['total']
			listcount = 0
			innerloop = True
			while innerloop:
				for file in searchjson['data']:
					print (str(listcount+1)+") "+file['path'])
					listcount = listcount + 1
					if listcount == maxlist:
						break
				if searchjson['total'] > maxlist:
					print(str(maxlist+1)+") more...")
				pathstr = raw_input("Enter Choice: ")
				pathchoice = int(pathstr)
				if pathchoice < maxlist+1:
					innerloop = False
					samesame = False
				else:
					maxlist = maxlist + 15
	versioncount = 0
	global recfilename
	recfilename = searchjson['data'][pathchoice-1]['filename']
	for v in searchjson['data'][pathchoice-1]['fileVersions']:
		versioncount = versioncount + 1
	loopstart = 0
	samesame = True
	if versioncount > 15:
		maxlist = 15
	else:
		maxlist = versioncount
	while samesame:
		innerloop = True
		print("Select File Version Date: ")
		while innerloop:
			print(str(loopstart+1)+") "+searchjson['data'][pathchoice-1]['fileVersions'][versioncount-loopstart-1]['lastModified'])
			if loopstart == maxlist:
				innerloop = False
			else:
				loopstart = loopstart + 1
		if maxlist < versioncount:
			print(str(loopstart+2)+") Show more ("+str(versioncount-maxlist)+" more available)")
		verchoice = raw_input("Enter Choice: ")
		if verchoice == str(loopstart+2):
			maxlist = maxlist + 15
			if maxlist > versioncount:
				maxlist = versioncount
		else:
			samesame = False
	finalpath = searchjson['data'][pathchoice-1]['path']
	finalsnapid = searchjson['data'][pathchoice-1]['fileVersions'][loopstart-1]['snapshotId']
	return finalpath, finalsnapid

# Starting Rubrik File Recovery
def startFileRecover(snapid, fullpath):
	fileurl = basedrurl+"v1/vmware/vm/snapshot/"+snapid+"/download_file"
	payload = { 'path': fullpath }
	getfileresponse = drsession.post(url=fileurl,json=payload)
	getfilejson = getfileresponse.json()
	print ("")
	print ("Created Job ID: "+getfilejson['id'])
	print ("Generating URL: "+getfilejson['links'][0]['href'])
	samesame = True
	statusurl = basedrurl+"v1/vmware/vm/request/"+getfilejson['id']
	while samesame:
		statusresponse = drsession.get(url=statusurl)
		statusjson = statusresponse.json()
		try:
			print("Progress: "+statusjson['status']+" "+str(statusjson['progress']))
		except:
			print("")
		if statusjson['status'] == "SUCCEEDED":
			samesame = False
			print ("Status: "+statusjson['status'])
		if statusjson['status'] == "FAILED":
			samesame = False
			print ("Status: "+statusjson['status'])
		time.sleep(7)
	return getfilejson['links'][0]['href']
		
def download_file(url,local):
    r = drsession.get(url, stream=True)
    with open(local, 'wb') as f:
        shutil.copyfileobj(r.raw, f)
    return local

# Main Body of Code Starts Here
passone = "one"
passtwo = "two"
recfilename = ""

# Collect User Information
os.system('clear')
drclusterip = raw_input("Enter Rubrik Cluster IP or Hostname: ")
drusername = raw_input("Enter Rubrik Username: ")
while passone != passtwo:
	passone = getpass.getpass('Enter Rubrik Password: ')
	passtwo = getpass.getpass('Re-Enter Rubrik Password: ')
	if passone != passtwo:
		print "Passwords do not match"
drpassword = passone
passone = "blank"
passtwo = "blank"
basedrurl = "https://"+drclusterip+"/api/"
urlclusterid = basedrurl+"v1/cluster/me"
urlvmcall = basedrurl+"v1/vmware/vm"
print " "

# Connect to DR Rubrik
print "Connecting to DR Rubrik at "+basedrurl
drsession, globaltoken = connectRubrik(drclusterip,drusername,drpassword)
response = drsession.get(url=urlclusterid)
if response.status_code == 200:
	clusterjson = response.json()
	drlocalid = clusterjson['id']
	urlclustername = basedrurl+"internal/cluster/"+clusterjson['id']+"/name"
	clsnameresponse = drsession.get(url=urlclustername)
	print " "
	print "Connected to "+clsnameresponse.text
else:
	print "Failed to connect"
	print "Response: "+str(response)
	print response.text
	exit()

vmid = getVMID()

print ("")
print ("VMID: "+vmid)

# Search for the File that you want to recover
path, snapshotid = getRecoverFile(vmid)

print("Path: "+str(path))
print("snapshotID: "+str(snapshotid))
print("")

targetpath = raw_input("Enter Target Path: ")
recfilename = targetpath+"/"+recfilename
print ("Target File: "+recfilename)
downloadlink = startFileRecover(snapshotid, path)
print ("")
print ("Beginning Download")
local = download_file(downloadlink, recfilename)
print ("Download Complete")

