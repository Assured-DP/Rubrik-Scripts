#!/bin/python
# Python 
# Executing customer runbook script

# Modules
import json
import requests
import urllib3
import urllib
import sys
import os
import getpass
import time
import datetime
import syslog
import threading
import logging

from dateutil import parser
from pytz import timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

"""
## Remove Quotes for detailed Requests logging
try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client
http_client.HTTPConnection.debuglevel = 1
"""

def establishAnswers():
    answerstring = "{ \"rubrikip\": \"\", \"rubrikuser\": \"\", \"vcenter\": \"\", \"vcenteruser\": \"\", \"custnumber\": \"\"}"
    answerjson = json.load(answerstring)
    return answerjson

def manageAnswerFile(answerfile):
    answerpath = '/home/adpengineer/DR/.runbookanswerfile.json'
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
    
# Get current SLA size
def getEventSeries(rubrik, startingpoint, hours):
    endpoint = startingpoint + datetime.timedelta(hours=hours)
    startstring = startingpoint.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    endstring = endpoint.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = { 'after_date': startstring, 'before_date': endstring, 'status': 'Success', 'event_type': 'Replication' }
    notifyurl = basedrurl+"internal/event_series"
    param = urllib.urlencode(payload)
    eventresponse = rubrik.get(url=notifyurl,params=param)
    try:
        eventjson = eventresponse.json()
    except:
        print("failed to get URL: "+notifyurl)
        print("response: "+str(eventresponse))
    return eventjson

# Get current SLA size
def continueEventSeries(rubrik, startingpoint, hours, lastevent):
    endpoint = startingpoint + datetime.timedelta(hours=hours)
    startstring = startingpoint.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    endstring = endpoint.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = { 'after_id': lastevent, 'before_date': endstring, 'status': 'Success', 'event_type': 'Replication' }
    notifyurl = basedrurl+"internal/event_series"
    param = urllib.urlencode(payload)
    eventresponse = rubrik.get(url=notifyurl,params=param)
    try:
        eventjson = eventresponse.json()
    except:
        print("failed to get URL: "+notifyurl)
        print("response: "+str(eventresponse))
    return eventjson

#### MAIN BODY OF CODE
passone = "one"
passtwo = "two"

# Setup Answer File
answerpath = '/home/adpengineer/DR/.runbookanswerfile.json'
answerjson = { "rubrikip": "a", "rubrikuser": "b", "vcenter": "c", "vcenteruser": "d", "custnumber": "e"}
if os.path.exists(answerpath):
    answerjson = json.load(open(answerpath))
else:
    with open(answerpath, 'w') as dmpfile:
        json.dump(answerjson, dmpfile)

# Collect User Information
os.system('clear')
drclusterip = raw_input("Enter Rubrik Cluster IP or Hostname [{0}]: ".format(answerjson['rubrikip']))
drclusterip = recordAnswer(drclusterip, "rubrikip")
drusername = raw_input("Enter Rubrik username [{0}]: ".format(answerjson['rubrikuser']))
drusername = recordAnswer(drusername, "rubrikuser")
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

# Connect to Rubrik
print "Connecting to Rubrik at "+basedrurl
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
    print "Failed to connect to Rubrik"
    print "Response: "+str(response)
    print response.text
    exit()


print("")
print("Enter Start Time for Log Collection (In Eastern Time)")
startstring = raw_input("YYYY-MM-DD HH:MM:SS.sss : ")
starttime = datetime.datetime.strptime(startstring, "%Y-%m-%d %H:%M:%S.%f EST")
print("")
collectperiod = raw_input("Enter Number of hours to collect: ")

hourcount = 0
outputfile = "./eventresult.csv"


print("Pulling Rubrik Event Logs...")
with open(outputfile, 'w+') as dmp:
    dmp.write("Object Name, Start Time, End Time, Data Transferred, Logical Size\n")
eventjson = getEventSeries(drsession, starttime, int(collectperiod))
#print(eventjson)
for event in eventjson['data']:
#    print(event['status'])
    if event['status'] == "Success":
        csvline = event['objectInfo']['objectName']+","+str(event['startTime'])+","+str(event['endTime'])+","+str(event['dataTransferred'])+","+str(event['logicalSize'])+"\n"
        print(csvline)
        with open(outputfile, 'a') as outfile:
            outfile.write(csvline)

while eventjson['hasMore']:
    lastid = eventjson['data'][len(eventjson['data'])-1]['eventId']
    print("Loading More...")
    eventjson = continueEventSeries(drsession, starttime, int(collectperiod), lastid)
    #print(eventjson)
    for event in eventjson['data']:
        if event['status'] == "Success":
            csvline = event['objectInfo']['objectName']+","+str(event['startTime'])+","+str(event['endTime'])+","+str(event['dataTransferred'])+","+str(event['logicalSize'])+"\n"
            print(csvline)
            with open(outputfile, 'a') as outfile:
                outfile.write(csvline)
