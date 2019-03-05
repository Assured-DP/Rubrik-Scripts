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
import time
import getpass

from dateutil import parser


# Declaring all Global variables
targetjsonlist = "./targetlist.json"

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

def enableTunnel(rubrik, hostname):	
	print ("Enabling: "+hostname)
	tunnelurl = "https://"+hostname+"/api/internal/node/me/support_tunnel"
	payload = "{ \"isTunnelEnabled\": true }"
	response = rubrik.patch(url=tunnelurl, data=payload)
	thatjson = response.json()
	if response.status_code == 422:
		if "enabled" in thatjson['message']:
			response = rubrik.get(url=tunnelurl)
			thatjson = response.json()
			try:
				print ("Existing Port: "+str(thatjson['port']))
				return thatjson['port']
			except:
				print ("Failed to enable tunnel.")
		else:
			print ("Credentials issue")
			return 0
	else:
		try:
			print ("Enabled port: "+str(thatjson['port']))
			return thatjson['port']
		except:
			print ("Failed to enable tunnel.")
			return 0
	
# Main Body of Code
os.system('clear')

# Load the Connection Data
print("Loading the Cluster Connection data from: "+targetjsonlist)
try:
	clusterdata = json.load(open(targetjsonlist))
except:
	print("Billing path file failed to load")

# Select Target Cluster(s)a
print("Search Target Cluster(s)")
destination = getCluster(clusterdata, "destination")

print("Destination(s): "+str(destination))

for target in destination:
	destcluster = getClusterInfo(clusterdata, target)
	destsession, desttoken = connectRubrik(destcluster['hostname'], "admin", base64.b64decode(destcluster['password']))
	enableTunnel(destsession,destcluster['hostname'])
	
	
	
	
	
	
	
	
	
	