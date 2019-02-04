#!/bin/python
# Python


# Modules
import datetime
import json
import requests
import urllib3
import sys
import os
import base64
import elasticsearch
import time
import threading
import getpass

from dateutil import parser


# Declaring all Global variables
billingpath = "targetlist.json"

# Disabling Certificate Warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Function for connecting to a Rubrik
def connectRubrik(hostname, username, password):
	session = requests.Session()
	session.verify = False
	sessurl = "https://"+hostname+"/api/v1/session"
	sessionTokenResponse = requests.request('POST', url=sessurl, auth=(username,password), verify=False)
	try:
		sessionJson = sessionTokenResponse.json()
	except:
		print "Unable to generate token for "+hostname+": "+str(sessionTokenResponse)
		quit()
	try:
		sessionToken = sessionJson['token']
		sessionBearer = "Bearer "+sessionToken
        	sessionHeader = {'Authorization': sessionBearer}
        	session.headers = sessionHeader
	except:
		sessionToken = "Bad Login"
	return session, sessionToken

def getJson(url, session):
    try:
        response = session.get(url=url)
    except requests.exceptions.RequestException as e:
        print "Error "+ e
    try:
	jsonresponse = response.json()
    except:
	print "Failed to Parse JSON"
    return jsonresponse

def getCluster(conjson,type):
	invalidrunbook = True
	nearmatch = []
	selected = []
	source = raw_input("Enter Cluster Hostname: ")
	for customer in conjson['customers']:
		for cluster in customer['clusters']:
			if source == cluster['hostname']:
				nearmatch.append(cluster['hostname'])
				return nearmatch
			if source.lower() in cluster['hostname'].lower():
				nearmatch.append(cluster['hostname'])
	while invalidrunbook:
		print " "
		if len(nearmatch) == 1:
			print("Matched "+source+" to "+nearmatch[0])
			return nearmatch
		if len(nearmatch) > 1:
			count = 0
			os.system('clear')
			print("Near "+type+ " matches: ")
			for clus in nearmatch:
				if clus in selected:
					print("* "+str(count+1)+") "+clus)
				else:
					print(str(count+1)+") "+clus)
				count = count + 1
			print(str(count+1)+") Start Over")
			if type == "destination":
				print(str(count+2)+") Select All")
			if (type == "destination") and (len(selected)>0):
				print(str(count+3)+") Finish")
			selection = raw_input("Enter Selection Number: ")
			if int(selection) == count+1:
				source = raw_input("Please Enter Cluster Hostname: ")
				nearmatch = []
				for customer in conjson['customers']:
					for cluster in customer['clusters']:
						if source == cluster['hostname']:
							nearmatch.append(cluster['hostname'])
							return nearmatch
						if source.lower() in cluster['hostname'].lower():
							nearmatch.append(cluster['hostname'])
				continue
			if int(selection) == count+2:
				return nearmatch
			elif int(selection) == count+3:
				return selected
			else:
				if nearmatch[int(selection)-1] in selected:
					selected.remove(nearmatch[int(selection)-1])
				else:
					selected.append(nearmatch[int(selection)-1])
				if type == "source":
					return selected
			count = 0
		else:
			print("No match. Looking for the hostname ADP would enter in a jump server, such as uscust002mon001")
			source = raw_input("Please Enter Cluster Hostname: ")
			for customer in conjson['customers']:
				for cluster in customer['clusters']:
					if source == cluster['hostname']:
						nearmatch.append(cluster['hostname'])
						return nearmatch
					if source.lower() in cluster['hostname'].lower():
						nearmatch.append(cluster['hostname'])

# Get Cluster Info
def getClusterInfo(clusterdata, hostname):
	for customer in clusterdata['customers']:
		for cluster in customer['clusters']:
			if cluster['hostname'] == hostname:
				return cluster

def getUserList(cluster, hostname):
	userurl = "https://"+hostname+"/api/internal/user"
	userjson = getJson(cluster, userurl)
	return userjson

def enterUserData():
	newUserLoop = True
	builduserstring = "{ \"users\": ["
	adduser = "y"
	count = 0
	while newUserLoop:
		if adduser == "y":
			username = raw_input("Enter username: ")
			emailaddy = raw_input("Enter email address: ")
			passloop = True
			while passloop:
				passone = getpass.getpass('Enter Rubrik Password: ')
				passtwo = getpass.getpass('Re-Enter Rubrik Password: ')
				if passone == passtwo:
					password = passone
					passloop = False
				else:
					print("Passwords do not match...")
			if count > 0:
				builduserstring = builduserstring + ","
			builduserstring = builduserstring + "{ \"username\": \""+username+"\", \"emailAddress\": \""+emailaddy+"\", \"password\": \""+password+"\" }"
			count = count+1
			#print builduserstring
			adduser = raw_input("Add another user? ")
		if adduser == "n":
			newUserLoop = False
	builduserstring = builduserstring + "]}"
	#print builduserstring
	builduserjson = json.loads(builduserstring)
	#print builduserjson
	return builduserjson

def loadUserData():
	getfileloop = True
	while getfileloop:
		sourcefile = raw_input("Enter Source File (full path): ")
		if os.path.exists(sourcefile):
			try:
				filejson = json.load(open(sourcefile))
				getfileloop = False
				return filejson
			except:
				print("File is not JSON format")
				continue
		else:
			print("File does not exist")

def getLocalAuthDomainId(userlist):
	for user in userlist:
		if (user['username'] == "admin") and (user['firstName'] == "Admin") and (user['lastName'] == "User"):
			return user['authDomainId']

def createUser(rubrik, hostname, userdata):
	userurl = "https://"+hostname+"/api/internal/user"
	payload = userdata
	createresponse = rubrik.post(url=userurl, data=json.dumps(payload), verify=False)
	createjson = createresponse.json()
	return createjson['id']
	
def patchUser(rubrik, hostname, userdata, userid):
	userurl = "https://"+hostname+"/api/internal/user/"+userid
	payload = userdata
	patchresponse = rubrik.patch(url=userurl, data=json.dumps(payload), verify=False)
	createjson = patchresponse.json()
	return createjson['id']

def changeRoleAdmin(rubrik, hostname, userid):
	authurl = "https://"+hostname+"/api/internal/authorization/role/admin"
	payload = {"principals":[userid],"privileges":{"fullAdmin":["Global:::All"]}}
	postreponse = rubrik.post(url=authurl, data=json.dumps(payload))
	

# Main Body of Code
os.system('clear')

# Load the Connection Data
print("Loading the Cluster Connection data from: "+billingpath)
try:
	clusterdata = json.load(open(billingpath))
except:
	print("Billing path file failed to load")

# Create User List
dataentryloop = True
while dataentryloop:
	os.system('clear')
	print("Select Option:")
	print("1) Enter Users")
	print("2) Load from file")
	choice = raw_input("Select number: ")
	if choice == "1":
		userjson = enterUserData()
		dataentryloop = False
	elif choice == "2":
		userjson = loadUserData()
		dataentryloop = False
	else:
		print("Bad Selection")

# Select Target Cluster(s)a
print("Search Target Cluster(s)")
destination = getCluster(clusterdata, "destination")

print("Destination(s): "+str(destination))

for target in destination:
	destcluster = getClusterInfo(clusterdata, target)
	destsession, desttoken = connectRubrik(destcluster['hostname'], "admin", base64.b64decode(destcluster['password']))
	userurl = "https://"+destcluster['hostname']+"/api/internal/user"
	destusers = getJson(userurl, destsession)
	authDomainId = getLocalAuthDomainId(destusers)
	for user in userjson['users']:
		current = {}
		current['id'] = "none"
		for existuser in destusers:
			if existuser['username'].lower() == user['username'].lower():
				current['id'] = existuser['id']
		if current['id'] == "none":
			print("Creating user "+user['username']+" on "+destcluster['hostname'])
			newuserid = createUser(destsession, destcluster['hostname'], user)
		else:
			updateuser = raw_input("User "+user['username']+" Exists, update? (y/n): ")
			if updateuser == "y":
				print("Updating user "+user['username']+" on "+destcluster['hostname'])
				newuserid = patchUser(destsession, destcluster['hostname'], user, current['id'])
			else:
				print("User "+user['username']+" remains unchanged.")
				continue
		print("Setting user "+user['username']+" to administrator role")
		changeRoleAdmin(destsession, destcluster['hostname'], newuserid)
	
	
	
	
	
	
	
	
	
	
	