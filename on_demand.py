## On Demand Snapshots
## on_demand.py <path_to_json_of_objects>
## File format:
"""
{
    "objects" : [
		{
			"type": "vmware",
			"objname": "usdc01adpjmp001",
			"objid": "VirtualMachine:::253b6e6c-fae0-437c-a1ad-85dd76a8bddd-vm-72",
			"slaid": "05840c56-1483-4dea-83b1-6474cf15f60e",
			"slaname": "USDC01 Production"
		}]
}
"""

import json
import base64
import requests
import urllib3
import syslog
import sys
import time

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

## Rubrik Connections
def connectRubrik(hostname, username, password):
    session = requests.Session()
    session.verify = False
    sessurl = "https://"+hostname+"/api/v1/session"
    try:
        sessionTokenResponse = requests.request('POST', url=sessurl, auth=(username,password), verify=False)
    except:
        return "None", "Bad Login"
    try:
        sessionJson = sessionTokenResponse.json()
    except:
        print("Unable to generate token for "+hostname+": "+str(sessionTokenResponse))
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
        syslog.syslog(syslog.LOG_ERR, 'Failed to get JSON from: '+url)
        syslog.syslog(syslog.LOG_ERR, 'Requests Exception: '+string(e))
    try:
        jsonresponse = response.json()
    except:
        syslog.syslog(syslog.LOG_ERR, 'Failed to Parse JSON from: '+url)
        syslog.syslog(syslog.LOG_ERR, 'Response test: '+response.text)
    return jsonresponse

def buildSnapUrl(target, targeturl):
	if target['type'] == "vmware":
		fullurl = targeturl+"v1/vmware/vm/"+target['objid']+"/snapshot"
	return fullurl

def buildJobUrl(jobdata, targeturl):
	if jobdata['type'] == "vmware":
		fullurl = targeturl+"v1/vmware/vm/request/"+jobdata['id']
	return fullurl

def createPayload(target, session):
	payload = {
		"slaId": target['slaid']
		}
	return payload

###
### Main Body of Code

sourcefile = sys.argv[1]
objectjson = json.load(open(sourcefile))
queuedjobs = []

## Setup the Rubrik
collectorfile = "/etc/adp/collector-config.json"
collectorjson = json.load(open(collectorfile))

for cluster in collectorjson['rubrik']['clusters']:
	if cluster['id'] == objectjson['cluster']:
		syslog.syslog(syslog.LOG_INFO, 'Connecting to cluster IP: '+cluster['nodes'][0]['ipAddress'])
		baseurl = "https://"+cluster['nodes'][0]['ipAddress']+"/api/"
		rubrik, rubriktoken = connectRubrik(cluster['nodes'][0]['ipAddress'], cluster['username'], cluster['password'])
		break

## Loop through the objects
getheader = rubrik.headers

for object in objectjson['objects']:
	url = buildSnapUrl(object, baseurl)
	payload = createPayload(object, rubrik)
	response = rubrik.post(url=url, data=json.dumps(payload))
	syslog.syslog(syslog.LOG_INFO, 'Submitted object: '+object['objid']+' Response: '+str(response.status_code))
	respjson = response.json()
	respjson['type'] = object['type']
	respjson['objid'] = object['objid']
	queuedjobs.append(respjson.copy())

jobsrunning = True
jobcount = len(queuedjobs)
successcount = 0


while jobsrunning:
	for jobs in queuedjobs:
		url = buildJobUrl(jobs, baseurl)
		response = rubrik.get(url=url)
		jobstatus = response.json()
		if jobstatus['status'] == "RUNNING":
			syslog.syslog(syslog.LOG_INFO, 'STATUS: '+jobstatus['status']+' at '+str(jobstatus['progress'])+'% for '+jobs['objid'])
		else:
			syslog.syslog(syslog.LOG_INFO, 'STATUS: '+jobstatus['status']+' for '+jobs['objid'])
		if jobstatus['status'] == "SUCCEEDED":
			successcount = successcount + 1
	time.sleep(5)
	if successcount == jobcount:
		jobsrunning = False
