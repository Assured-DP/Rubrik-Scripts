# Rubrik-Scripts
Assured DP Public Rubrik Scripts

Assured Data Protection is a Rubrik as a Service and Disaster Recovery as a Service provider. As part of our management and delivery of services we end up building customer scripting on behalf of our customers. This GitHub repository is provided without warranty or guarantee, but as a collection of tools to be incorporated as needed for those administering Rubrik systems.

This README acts as a file and function list of the scripts in the repository.

orannfstab.py | Create oranfstab and mtab
------ | -----
Filename: | create_oranfstab.py
Summary: | Generates the oranfstab and mtab files for oracle systems that are leveraging oranfs and RMAN writing to managed volumes
Requires: | requests, urllib3, time
Notes: | Allows for comma-separated list or oracle node source IPs. Each rubrik node is considered an NFS server and the floating IP is the path. Script will consolidate managed volume exports to a single rubrik node entry in the script.



filerecovery.py | Single File Recovery Tool
------- | -------
Filename: | filerecovery.py
Summary: | Recovers a file or a folder from a vmware virtual machine and restores it to a target folder after download. This is useful when recovering from a different source VM than the target and also when traversing a windows system can cause unintended consequences (UTF Changes, as an example).
Requires: | requests
Notes: | Assumes that the target path is mounted locally to the system running the script. Will not connect to remote UNC or NFS paths on demand.


setup_users.py | Setup identical users across many Rubrik clusters
------- | -------
Filename(s): | setup_users.py, targetlist.json, users.json
Summary: | Allows the user to enter a list of users via the keyboard or load a JSON list of users (users.json example). Once the users are loaded, the script then pulls a list of available target clusters by leveraging targetlist.json with clusters and b64encoded passwords for the admin account. Currently the script is hardcoded to use admin account and hardcoded to require the b64encoded password lives in the targetlist.
Requires: | requests
Notes: | requires the targetlist.json is in the same folder and preconfigured. Allows operator to enter the location of the users.json path as an absolute link. Script has been tested in Python 2.7. would need modifications for 3.x


getnetworks... | Gets all VMs with their network adapters and MAC addresses from a Nutanix cluster
------- | -------
Filename(s): | getnetworks.py (Linux Python 2.7), getnetworks.win.py (Windows python 3.6), getnetworks.win27.py (windows Python 2.7)
Summary: | Creates a JSON file that has all the VMs in a nutanix cluster, along with their associated NIC, MAC, and Network name
Requires: | requests
Notes: | Assumes Prism is on the default ports, would need modification for different ports.


archivereport.py | Polls all objects assigned to an SLA and returns the most recent snap date and most recent archive snap date
------- | -------
Filename(s): | archivereport.py (2.7 python)
Summary: | Creates a CSV file formatted as date-time-clustername.csv containing clustername, object name, SLA name, latest snap, and latest archived snap
Requires: | requests, pytz, json, sys, datetime, syslog, threading
Notes: | Variable maxSessions can be configured for how many nodes you want to run this against. The scripts will thread the jobs by object type within an SLA. For example, an SLA with VMs and MSSQL will have two threads, one for VMs and one for SQL. You can set maxThreads to limit the number of python threads or expand them. Rubrik has a limitation of 10 sessions so any setting above 10 for maxSessions will have a performance penalty as the script will reauthenticate any dropped sessions due to excessive sessions.