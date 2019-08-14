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
import datetime
import syslog
import threading

from dateutil import parser
from pytz import timezone



# Silence warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

##### From here to the end of recordAnswer is not used, but I left it so we can later re-add an answerfile if so desired 
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
##### END of the answerfile section

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
	syslog.syslog(syslog.LOG_INFO, "Authenticating "+drsessurl+" with "+username+" result: "+str(drtokenresponse.text))
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

# Get Snapshot for a VM - Currently returns the latest snapshot
def getSnapshot(vmid):
	snapurl = basedrurl+"v1/vmware/vm/"+vmid+"/snapshot"
	snapresponse = drsession.get(url=snapurl)
	snapjson = snapresponse.json()
	latestsnap = snapjson['data'][0]['id']
	return latestsnap

# Function for waiting for Active threads to reduce below maxThreads
def waitForThreads():
	slowDown = True
	while slowDown:
		if threading.active_count() > maxThreadCount:
			print("Max Threads of "+str(maxThreadCount)+" reached, waiting for threads to complete")
			time.sleep(5)
		else:
			slowDown = False		
	
# SLA Object Count -- Calculate total objects connected to an SLA
def getObjectCount(slaJson):
	total = slaJson['numDbs']+slaJson['numFileset']+slaJson['numHypervVms']+slaJson['numNutanixVms']+slaJson['numManagedVolumes']+slaJson['numLinuxHosts']+slaJson['numShares']+slaJson['numWindowsHosts']+slaJson['numVms']
	return total

# Get Newest Archive Snapshot Reverse sorts a JSON list of all snapshtos by date and iterates from the newest snapshot looking for archived snaps.
# CloudState identifies if there is an archive. Setting above 0 means an archive sanp exists, even if it has been downloaded or is also local
def getArchiveSnap(snapjson):
	sortsnaps = sorted(snapjson, key=lambda x: datetime.datetime.strptime(x['date'], '%Y-%m-%dT%H:%M:%S.%fZ'), reverse=True)
	for snap in sortsnaps:
		if snap['cloudState'] > 0:
			#syslog.syslog(syslog.LOG_INFO, snap['id']+": latest Cloud Snap")
			return snap['date']
	return "No Snap"


# List SLA Object Replication Status
def getSLAArchives(sla_obj,objtyped,clusuuid,node): 
	global missingcount
	sla = sla_obj['id']
	snapcount = 0
	outputjsonstring = ""
	# Build out URLs for all the different object types.
	# Volume Groups aren't in this list but tend to get covered by Fileset below. Need to double check this theory
	if objtyped == "Vms":
		listurl = "https://"+cluster['nodes'][node]['ip']+"/api/v1/vmware/vm?effective_sla_domain_id="+sla
		objtype = "VMWare VM"
		snappath = "v1/vmware/vm/"
		snapend = "/snapshot"
		reversesort = False
	if objtyped == "Dbs":
		listurl = "https://"+cluster['nodes'][node]['ip']+"/api/v1/mssql/db?effective_sla_domain_id="+sla
		objtype = "MSSQL DB"
		snappath = "v1/mssql/db/"
		snapend = "/snapshot"
		reversesort = True
	if objtyped == "NutanixVms":
		listurl = "https://"+cluster['nodes'][node]['ip']+"/api/internal/nutanix/vm?effective_sla_domain_id="+sla
		objtype = "Nutanix VM"
		snappath = "internal/nutanix/vm/"
		snapend = "/snapshot"
		reversesort = True
	if objtyped == "HypervVms":
		listurl = "https://"+cluster['nodes'][node]['ip']+"/api/internal/hyperv/vm?effective_sla_domain_id="+sla
		objtype = "Hyper-V VM"
		snappath = "internal/hyperv/vm/"
		snapend = "/snapshot"
		reversesort = True
	if objtyped == "Filesets":
		listurl = "https://"+cluster['nodes'][node]['ip']+"/api/v1/fileset?effective_sla_domain_id="+sla
		objtype = "Fileset"
		snappath = "v1/fileset/"
		filesetresponse = cluster['nodes'][node]['session'].get(url=listurl)
		try:
			filesetjson = filesetresponse.json()
		except:
			syslog.syslog(syslog.LOG_ERR, listurl+": failure. Line 157. Response: "+str(filesetresponse))
			tempsess, temptoken = refreshRubrik(cluster['nodes'][node]['ip'])
			cluster['nodes'][node]['session'] = tempsess
			filesetresponse = cluster['nodes'][node]['session'].get(url=listurl)
			filesetjson = filesetresponse.json()
		snapcount = 0
		# Special Handling for Filesets
		for fset in filesetjson['data']:
			fseturl = "https://"+cluster['nodes'][node]['ip']+"/api/"+snappath+fset['id']
			fsetresponse = cluster['nodes'][node]['session'].get(url=fseturl)
			try:
				fsetsnaps = fsetresponse.json()
			except:
				syslog.syslog(syslog.LOG_ERR, listurl+": failure. Line 170. Response: "+str(fsetresponse))
				tempsess, temptoken = refreshRubrik(cluster['nodes'][node]['ip'])
				cluster['nodes'][node]['session'] = tempsess
				fsetresponse = cluster['nodes'][node]['session'].get(url=fseturl)
				fsetsnaps = fsetresponse.json()
			snapindex = fsetsnaps['snapshotCount']-1
			#print fseturl
			if snapindex >= 0:
				snapdate = parser.parse(fsetsnaps['snapshots'][snapindex]['date'])
				if fsetsnaps['snapshots'][snapindex]['cloudState'] > 0:
					archivesnapdate = getArchiveSnap(fsetsnaps['snapshots'])
				else:
					archivesnapdate = getArchiveSnap(fsetsnaps['snapshots'])
				today = datetime.datetime.now(timezone('UTC'))
				naiveday = etc.localize(today.replace(tzinfo=None))
				naivesnap = etc.localize(snapdate.replace(tzinfo=None))
				datediff = abs((naiveday-naivesnap))
				showtime = "%dD, %dh:%dm" % (datediff.days, datediff.seconds//3600, (datediff.seconds//60)%60)
				if snapcount > 0:
					outputjsonstring = outputjsonstring + ", "
				outputjsonstring = "{ \"cluster\": \""+cluster['name']+"\", \"Obj Name\": \""+fset['name']+"\", \"SLA\": \""+sla_obj['name']+"\", \"Latest Local Snap\": \""+fsetsnaps['snapshots'][snapindex]['date']+"\", \"Latest Archive Date\" : \""+archivesnapdate+"\"}"
				globaloutput.append(json.loads(outputjsonstring))
				snapcount = snapcount + 1 
		return 0
	# End of FileSet Handling. Moving on to handling of all other object types
	listresponse = cluster['nodes'][node]['session'].get(url=listurl)
	syslog.syslog(syslog.LOG_INFO, listurl+" response: "+str(listresponse))
	#print listurl
	try:
		listjson = listresponse.json()
	except:
		syslog.syslog(syslog.LOG_ERR, "FAILED JSON: "+str(listresponse.text))
		tempsess, temptoken = refreshRubrik(cluster['nodes'][node]['ip'])
		cluster['nodes'][node]['session'] = tempsess
		listresponse = cluster['nodes'][node]['session'].get(url=listurl)
		listjson = listresponse.json()
	#print listjson['total']
	#print str(listjson['hasMore'])
	snapcount = 0
	for objid in listjson['data']:
			snapurl = "https://"+cluster['nodes'][node]['ip']+"/api/"+snappath+objid['id']+snapend
			#print snapurl+" 2ndLoop SLA"
			snapresponse = cluster['nodes'][node]['session'].get(url=snapurl)
			try:
				snapjson = snapresponse.json()
			except:
				syslog.syslog(syslog.LOG_ERR, listurl+": failure. Line 216. Reponse: "+str(snapresponse))
				tempsess, temptoken = refreshRubrik(cluster['nodes'][node]['ip'])
				cluster['nodes'][node]['session'] = tempsess
				snapresponse = cluster['nodes'][node]['session'].get(url=listurl)
				try:
					snapjson = snapresponse.json()
				except:
					syslog.syslog(syslog.LOG_ERR, listurl+": 2nd failure, line 223. Response: "+str(snapresonse))
					syslog.syslog(syslog.LOG_ERR, listurl+": response text: "+str(snapresponse.text))
			objreport = objtype
			if snapjson['total']>0:
				if reversesort:
					snapindex = snapjson['total']-1
				else:
					snapindex = 0
				try:
					snapdate = snapjson['data'][snapindex]['date']
				except:
					syslog.syslog(syslog.LOG_ERR, "JSON Error: "+objid['name']+" line 234: snap: "+str(snapjson['data'][snapindex]))
					continue
				archivesnapdate = getArchiveSnap(snapjson['data'])
			else:
				outputjsonstring = "{ \"cluster\": \""+cluster['name']+"\", \"Obj Name\": \""+objid['name']+"\", \"SLA\": \""+sla_obj['name']+"\", \"Latest Local Snap\": \"NO SNAPS\", \"Latest Archive Date\" : \"NO SNAPS\"}"
				globaloutput.append(json.loads(outputjsonstring))
				missingcount = missingcount + 1
				snapcount = snapcount +1
				continue
			if objtype == "MSSQL DB":
				objreport = objtype +" "+objid['rootProperties']['rootName']
				dburl = "https://"+cluster['nodes'][node]['ip']+"/v1/mssql/db/"+objid['id']+"/recoverable_range"
				dbresponse = cluster['nodes'][node]['session'].get(url=dburl)
				try:
					dbjson = dbresponse.json()
				except:
					syslog.syslog(syslog.LOG_ERR, dburl+" failed with response "+str(dbresponse))
					tempsess, temptoken = refreshRubrik(cluster['nodes'][node]['ip'])
					cluster['nodes'][node]['session'] = tempsess
					dbresponse = cluster['nodes'][node]['session'].get(url=dburl)
					try:
						dbjson = dbresponse.json()
					except:
						syslog.syslog(syslog.LOG_ERR, objid['name']+" failed JSON on recoverable_range line 257. Response: "+str(dbresponse))
						syslog.syslog(syslog.LOG_ERR, objid['name']+" response text: "+str(dbresponse.text))
						continue
				dbsnapdate = dbjson['data'][dbjson['total']-1]['endTime']
				if dbsnapdate > snapdate:
					snapdate = dbsnapdate
			outputjsonstring = "{ \"cluster\": \""+cluster['name']+"\", \"Obj Name\": \""+objid['name']+"\", \"SLA\": \""+sla_obj['name']+"\", \"Latest Local Snap\": \""+snapjson['data'][snapindex]['date']+"\", \"Latest Archive Date\": \""+archivesnapdate+"\"}"
			globaloutput.append(json.loads(outputjsonstring))
			snapcount = snapcount + 1

# If the Rubrik session goes stale, this will recreate it using the existing user and password
def refreshRubrik(rubrikip):
	session, token = connectRubrik(rubrikip,rubrikuser,rubrikpass)
	syslog.syslog(syslog.LOG_INFO, "Refreshed Session for "+str(rubrikip))
	return session, token 

# Build out a JSON of the cluster information that includes the version information and the nodes
def genClusterJson(rubrik,host):
	clusterdata = {}
	url = "https://"+host+"/api/v1/cluster/me"
	clusresponse = rubrik.get(url=url)
	clusjson = clusresponse.json()
	url = "https://"+host+"/api/internal/node"
	clusresponse = rubrik.get(url=url)
	nodejson = clusresponse.json()
	nodes = []
	for node in nodejson['data']:
		nodedata = {
			"id": node['id'],
			"ip": node['ipAddress'],
			"status": node['status']
			}
		nodes.append(nodedata)
	clusterdata = {
		"name": clusjson['name'],
		"id": clusjson['id'],
		"version": clusjson['version'],
		"vermajor": int(clusjson['version'][0]),
		"verminor": int(clusjson['version'][2]),
		"verfix": int(clusjson['version'][4]),
		"nodes": nodes
		}
	return clusterdata

######################## GLOBAL VARIABLES
etc = timezone('US/Eastern')
storepath = "./" # CSV TARGET PATH
missingcount = 0 
maxThreadCount = 15 # Maximum number of Python Threads
maxSessions = 9 # Maximum number of Rubrik Sessions. Script will use the greater of the node count or the session count
globaloutput = [] # Establish the output container
threadlist = [] # Establish the list of threads

# Collect user inputs to setup authentication
rubrikip = raw_input("Rubrik IP: ")
rubrikuser = raw_input("Rubrik user: ")
rubrikpass = getpass.getpass("Rubrik Pass: ")
tokenUrl = "https://"+rubrikip+"/api/v1/session"
username = rubrikuser
password = rubrikpass
# Generate initial token
rubriksession, token = connectRubrik(rubrikip, rubrikuser, rubrikpass)
bearertoken = 'Bearer ' + token

# Pull cluster data into master JSON
cluster = genClusterJson(rubriksession,rubrikip)
# Establish file name for CSV
now = datetime.datetime.now()
timestamp = str(now.strftime("%Y-%m-%d--%H.%M-"))
print (timestamp)
sourcepath = storepath+timestamp+cluster['name']+".csv"

count = 0
for node in cluster['nodes']:
	print(node['ip']+": Building Session")
	tempsess, token = connectRubrik(node['ip'], rubrikuser, rubrikpass)
	node['session'] = tempsess
	if count == maxSessions-1:
		break
	else:
		count = count + 1
#print cluster

nodecount = 0
if len(cluster['nodes']) > maxSessions:
	maxNodes = maxSessions
	syslog.syslog(syslog.LOG_INFO, "Max Sessions Reached, limiting to "+str(maxNodes)+" login sessions")
else:
	maxNodes = len(cluster['nodes'])
	syslog.syslog(syslog.LOG_INFO, "Max Sessions Reached, limiting to "+str(maxNodes)+" login sessions")

slaurl = "https://"+cluster['nodes'][0]['ip']+"/api/v1/sla_domain?primary_cluster_id="+cluster['id']
syslog.syslog(syslog.LOG_INFO, slaurl+": Connecting")
response = cluster['nodes'][0]['session'].get(url=slaurl)
try:
	slajson = response.json()
except:
	syslog.syslog(syslog.LOG_ERR, 'SLA REQ failed. URL: '+slaurl)
	syslog.syslog(syslog.LOG_ERR, 'SLA REQ failed. Response: '+response.text)
	tempsess, token = refreshRubrik(cluster['nodes'][0]['ip'])
	cluster['nodes'][0]['session'] = tempsess
	response = cluster['nodes'][0]['session'].get(url=slaurl)
	slajson = response.json()
	

for sla in slajson['data']:	
	print ("Working SLA: "+sla['name'])
	syslog.syslog(syslog.LOG_INFO, "Working SLA: "+sla['name'])
	loopslaurl = "https://"+cluster['nodes'][nodecount]['ip']+"/api/v2/sla_domain/"+sla['id']
	loopresponse = cluster['nodes'][nodecount]['session'].get(url=loopslaurl)
	syslog.syslog(syslog.LOG_INFO, loopslaurl+" Response: "+str(response))
	try:
		loopslajson = loopresponse.json()
	except:
		syslog.syslog(syslog.LOG_ERR, loopslaurl+" failed with response "+str(loopresponse))
		print(sla['name']+": Bad Snap Data")
		tempsess, temptoken = refreshRubrik(cluster['nodes'][nodecount]['ip'])
		cluster['nodes'][nodecount]['session'] = tempsess
		loopresponse = cluster['nodes'][nodecount]['session'].get(url=loopslaurl)
		loopslajson = loopresponse.json()
	#print loopslajson
	if loopslajson['numVms'] > 0:
		vmthread = threading.Thread(target=getSLAArchives, args=(sla.copy(),"Vms",cluster['id'],nodecount))
		if nodecount == maxNodes-1:
			nodecount = 0
		else:
			nodecount = nodecount + 1
		waitForThreads()
		vmthread.start()
		threadlist.append(vmthread)
	if loopslajson['numDbs'] > 0:
		dbthread = threading.Thread(target=getSLAArchives, args=(sla.copy(),"Dbs",cluster['id'],nodecount))
		if nodecount == maxNodes-1:
			nodecount = 0
		else:
			nodecount = nodecount + 1
		waitForThreads()
		dbthread.start()
		threadlist.append(dbthread)
	if loopslajson['numFilesets'] > 0:
		filethread = threading.Thread(target=getSLAArchives, args=(sla.copy(),"Filesets",cluster['id'],nodecount))
		if nodecount == maxNodes-1:
			nodecount = 0
		else:
			nodecount = nodecount + 1
		waitForThreads()
		filethread.start()
		threadlist.append(filethread)
	if loopslajson['numNutanixVms'] > 0:
		nutthread = threading.Thread(target=getSLAArchives, args=(sla.copy(),"NutanixVms",cluster['id'],nodecount))
		if nodecount == maxNodes-1:
			nodecount = 0
		else:
			nodecount = nodecount + 1
		waitForThreads()
		nutthread.start()
		threadlist.append(nutthread)
	if loopslajson['numHypervVms'] > 0:
		hyperthread = threading.Thread(target=getSLAArchives, args=(sla.copy(),"HypervVms",cluster['id'],nodecount))
		if nodecount == maxNodes-1:
			nodecount = 0
		else:
			nodecount = nodecount + 1
		waitForThreads()
		hyperthread.start()
		threadlist.append(hyperthread)


#print output
threadsrunning = True
while threadsrunning:
	thrcount = threading.active_count()
	if thrcount > 1:
		print("Waiting for threads to complete. "+str(thrcount-1)+" running...")
		time.sleep(5)
		threadsrunning = True
	else:
		threadsrunning = False
print ("Script completed")
#print json.dumps(globaloutput)
print ("Writing "+sourcepath)
with open(sourcepath, 'w') as outfile:
	tablehead = "Cluster, Obj Name, SLA, Latest Local Snap, Latest Archive Date"
	outfile.write(tablehead+'\n')
	for line in globaloutput:
		lineout = line['cluster']+", "+line['Obj Name']+", "+line['SLA']+", "+line['Latest Local Snap']+", "+line['Latest Archive Date']
		outfile.write(lineout+'\n')
