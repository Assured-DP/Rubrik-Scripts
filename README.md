# Rubrik-Scripts
Assured DP Public Rubrik Scripts

Assured Data Protection is a Rubrik as a Service and Disaster Recovery as a Service provider. As part of our management and delivery of services we end up building customer scripting on behalf of our customers. This GitHub repository is provided without warranty or guarantee, but as a collection of tools to be incorporated as needed for those administering Rubrik systems.

This README acts as a file and function list of the scripts in the repository.

Filename: create_oranfstab.py
Summary: Generates the oranfstab and mtab files for oracle systems that are leveraging oranfs and RMAN writing to managed volumes
Requires: requests
Notes: Assumes a single source IP address from each node in the RAC cluster. This IP address is specified in the "local ip" variable. There would be a scenario where a customer has many IPs on a single node of a RAC cluster they want to load balance over. This would require modification of the script to list all source IPs as associated with the target paths.


Filename: filerecovery.py
Summary: Recovers a file or a folder from a vmware virtual machine and restores it to a target folder after download. This is useful when recovering from a different source VM than the target and also when traversing a windows system can cause unintended consequences (UTF Changes, as an example).
Requires: requests
Notes: Assumes that the target path is mounted locally to the system running the script. Will not connect to remote UNC or NFS paths on demand.

