#from cassandra.cluster import Cluster
import requests
import urllib3
import getpass
import time
#requests.packages.urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

global billingSize

rubrikip = raw_input("Rubrik IP: ")
rubrikuser = raw_input("Rubrik user: ")
rubrikpass = getpass.getpass("Rubrik Pass: ")
localip = raw_input("Enter IP of Oracle Host (Separate Multiple with commas): ")

oracleip = []
if "," in localip:
	oracleip = localip.split(",")
else:
	oracleip.append(localip)

tokenUrl = "https://"+rubrikip+"/api/v1/session"
username = rubrikuser
password = rubrikpass
session = requests.post(tokenUrl, verify=False, auth=(username, password))
session = session.json()
token = 'Bearer ' + session['token']

#localip = "172.20.160.100"

voljson = {}

print "#############################"
print "oranfstab begins here"
print "#############################"

def buildVolumeList():
	floatipurl = "https://"+rubrikip+"/api/internal/cluster/me/floating_ip"
	floatresponse = requests.get(floatipurl, headers= { 'Accept': 'application/json', 'Authorization': token },verify=False, stream=True)
	floatipjson = floatresponse.json()
	vmurl = "https://"+rubrikip+"/api/internal/managed_volume"
	volsresponse = requests.get(vmurl, headers= { 'Accept': 'application/json', 'Authorization': token },verify=False, stream=True)
	print vmurl
	global voljson
	voljson = volsresponse.json()
	count = 1
	if voljson['total'] > 0:
		for node in floatipjson['data']:
			print ("server: "+node['nodeId'])
			for oraip in oracleip:
				print("local: "+oraip+" path: "+node['ip'])
			mntcount = 0
			for volume in voljson['data']:
				for channel in volume['mainExport']['channels']:
					if channel['ipAddress'] == node['ip']:
						mntname = volume['name']+"-ch"+str(mntcount)
						mntcount = mntcount+1
						print("export: "+channel['mountPoint']+" mount: /mnt/rubrik/"+mntname)
			print("nfs_version: nfsv3")
			print("")

def buildTab():
    #vmurl = "https://uscust008mon001.us.assured.local/api/internal/managed_volume"
    #volsresponse = requests.get(vmurl, headers= { 'Accept': 'application/json', 'Authorization': token },verify=False, stream=True)
    #print volsresponse.text
    #voljson = volsresponse.json()
    nfs_path = "/mnt/rubrik/"
    nfs_settings = " nfs rw,noatime,bg,hard,nointr,rsize=1048576,wsize=1048576,tcp,actimeo=0,vers=3,timeo=600,addr="
    nfs_close = " 0 0"
    if voljson['total'] > 0:
        for volume in voljson['data']:
            # Print Paths
            mountcount = 0
            for path in volume['mainExport']['channels']:
                print (path['ipAddress']+":"+path['mountPoint']+" "+nfs_path+volume['name']+"-ch"+str(mountcount)+nfs_settings+path['ipAddress']+nfs_close)
		mountcount = mountcount + 1

buildVolumeList()
print("")
print("########################")
print("mtab information below")
print("########################")
time.sleep(1)
buildTab()
