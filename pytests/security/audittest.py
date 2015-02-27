import json
import time
from threading import Thread, Event
from basetestcase import BaseTestCase
from couchbase_helper.document import DesignDocument, View
from couchbase_helper.documentgenerator import DocumentGenerator
from membase.api.rest_client import RestConnection
from membase.helper.rebalance_helper import RebalanceHelper
from membase.api.exception import ReadDocumentException
from membase.api.exception import DesignDocCreationException
from membase.helper.cluster_helper import ClusterOperationHelper
from remote.remote_util import RemoteMachineShellConnection
from random import randint
from datetime import datetime
import commands
import logger
import urllib
from security.auditmain import audit
log = logger.Logger.get_logger()


class auditTest(BaseTestCase):

    def setUp(self):
        super(auditTest, self).setUp()
        self.ipAddress = self.getLocalIPAddress()
        self.eventID = self.input.param('id', None)

    def tearDown(self):
        super(auditTest, self).tearDown()

    def getLocalIPAddress(self):
        status, ipAddress = commands.getstatusoutput("ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 |awk '{print $1}'")
        return ipAddress

    #Wrapper around auditmain
    def checkConfig(self, eventID, host, expectedResults):
        Audit = audit(eventID=self.eventID, host=host)
        fieldVerification, valueVerification = Audit.validateEvents(expectedResults)
        self.assertTrue(fieldVerification, "One of the fields is not matching")
        self.assertTrue(valueVerification, "Values for one of the fields is not matching")

    #Tests to check for bucket events
    def test_bucketEvents(self):
        ops = self.input.param("ops", None)
        user = self.master.rest_username
        source = 'ns_server'
        rest = RestConnection(self.master)

        if (ops in ['create']):
            expectedResults = {'bucket_name':'TestBucket', 'ram_quota':2147483648, 'num_replicas':1,
                               'replica_index':False, 'eviction_policy':'value_only', 'type':'membase', \
                               'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", \
                                "flush_enabled":False, "num_threads":3, "source":source, \
                               "user":user, "ip":self.ipAddress, "port":57457, 'sessionid':'' }
            rest.create_bucket(expectedResults['bucket_name'], expectedResults['ram_quota'] / 1048576, expectedResults['auth_type'], 'password', expectedResults['num_replicas'], \
                               '11211', 'membase', 0, expectedResults['num_threads'], expectedResults['flush_enabled'], 'valueOnly')

        elif (ops in ['update']):
            expectedResults = {'bucket_name':'TestBucket', 'ram_quota':2147483648, 'num_replicas':1, 'replica_index':False, 'eviction_policy':'value_only', 'type':'membase', \
                               'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", "flush_enabled":'true', "num_threads":3, "source":source, \
                               "user":user, "ip":self.ipAddress, "port":57457 , 'sessionid':''}
            rest.create_bucket(expectedResults['bucket_name'], expectedResults['ram_quota'] / 1048576, expectedResults['auth_type'], 'password', expectedResults['num_replicas'], '11211', 'membase', \
                               0, expectedResults['num_threads'], expectedResults['flush_enabled'], 'valueOnly')
            expectedResults = {'bucket_name':'TestBucket', 'ram_quota':536870912, 'num_replicas':1, 'replica_index':True, 'eviction_policy':'value_only', 'type':'membase', \
                               'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", "flush_enabled":'false', "num_threads":3, "source":source, \
                               "user":user, "ip":self.ipAddress, "port":57457}
            rest.change_bucket_props(expectedResults['bucket_name'], expectedResults['ram_quota'] / 1048576, expectedResults['auth_type'], 'password', expectedResults['num_replicas'], \
                                     '11211', 1, expectedResults['flush_enabled'])

        elif (ops in ['delete']):
            expectedResults = {'bucket_name':'TestBucket', 'ram_quota':536870912, 'num_replicas':1, 'replica_index':True, 'eviction_policy':'value_only', 'type':'membase', \
                               'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", "flush_enabled":'false', "num_threads":3, "source":source, \
                               "user":user, "ip":self.ipAddress, "port":57457}
            rest.create_bucket(expectedResults['bucket_name'], expectedResults['ram_quota'] / 1048576, expectedResults['auth_type'], 'password', expectedResults['num_replicas'], \
                               '11211', 'membase', 1, expectedResults['num_threads'], expectedResults['flush_enabled'], 'valueOnly')
            rest.delete_bucket(expectedResults['bucket_name'])

        elif (ops in ['flush']):
            expectedResults = {'bucket_name':'TestBucket', 'ram_quota':512, 'num_replicas':1, 'replica_index':True, 'eviction_policy':'value_only', 'type':'membase', \
                               'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", "flush_enabled":'true', "num_threads":3, "source":source, \
                               "user":user, "ip":self.ipAddress, "port":57457}
            rest.create_bucket(expectedResults['bucket_name'], expectedResults['ram_quota'], expectedResults['auth_type'], 'password', expectedResults['num_replicas'], \
                               '11211', 'membase', 1, expectedResults['num_threads'], 1, 'valueOnly')
            self.sleep(10)
            rest.flush_bucket(expectedResults['bucket_name'])

        self.checkConfig(self.eventID, self.master, expectedResults)


    def test_clusterOps(self):
        Audit = audit(eventID=self.eventID, host=self.master)
        ops = self.input.param('ops', None)
        servs_inout = self.servers[1:self.nodes_in + 1]
        source = 'ns_server'

        if (ops in ['addNode']):
            self.cluster.rebalance(self.servers, servs_inout, [])
            print servs_inout
            print servs_inout[0].ip
            expectedResults = {"services":['kv'], 'port':8091, 'hostname':servs_inout[0].ip,
                               'groupUUID':"0", 'node':'ns_1@' + servs_inout[0].ip, 'source':source,
                               'user':self.master.rest_username, "ip":self.ipAddress, "remote:port":57457}

        if (ops in ['removeNode']):
            expectedResults = {'node':'ns_1@' + servs_inout[0].ip, 'source':source, 'user':self.master.rest_username, "ip":self.ipAddress, "port":57457}

        if (ops in ['rebalanceIn']):
            self.cluster.rebalance(self.servers, servs_inout, [])
            expectedResults = {"delta_recovery_buckets":"all", 'known_nodes':["ns_1@" + self.master.ip, "ns_1@" + servs_inout[0].ip], 'ejected_nodes':[], 'source':'ns_server', \
                                'source':source, 'user':self.master.rest_username, "ip":self.ipAddress, "port":57457}

        if (ops in ['rebalanceOut']):
            self.cluster.rebalance(self.servers, [], servs_inout)
            expectedResults = {"delta_recovery_buckets":"all", 'known_nodes':["ns_1@" + self.master.ip, "ns_1@" + servs_inout[0].ip], 'ejected_nodes':['ns_1@' + servs_inout[0].ip], 'source':'ns_server', \
                               'source':source, 'user':self.master.rest_username, "ip":self.ipAddress, "port":57457}
        if (ops in ['failover']):
            type = self.input.param('type', None)
            self.cluster.failover(self.servers, servs_inout)
            self.cluster.rebalance(self.servers, [], [])
            expectedResults = {'source':source, 'user':self.master.rest_username, "ip":self.ipAddress, "port":57457, 'type':type, 'node':'ns_1@' + servs_inout[0].ip}

        if (ops == 'nodeRecovery'):
            expectedResults = {'node':'ns_1@' + servs_inout[0].ip, 'type':'delta', 'source':source, 'user':self.master.rest_username, "ip":self.ipAddress, "port":57457}
            self.cluster.failover(self.servers, servs_inout)
            rest = RestConnection(self.master)
            rest.set_recovery_type(expectedResults['node'], 'delta')

        # Pending of failover - soft
        self.checkConfig(self.eventID, self.master, expectedResults)


    def test_settingsCluster(self):
        ops = self.input.param("ops", None)
        source = 'ns_server'
        user = self.master.rest_username
        password = self.master.rest_password
        rest = RestConnection(self.master)

        if (ops == 'memoryQuota'):
            expectedResults = {'quota':512, 'source':source, 'user':user, 'ip':self.ipAddress, 'port':12345}
            rest.init_cluster_memoryQuota(expectedResults['user'], password, expectedResults['quota'])

        elif (ops == 'loadSample'):
            expectedResults = {'name':'gamesim-sample', 'source':source, "user":user, 'ip':self.ipAddress, 'port':12345}
            rest.addSamples()
            #Get a REST Command for loading sample

        elif (ops == 'enableAutoFailover'):
            expectedResults = {'max_nodes':1, "timeout":120, 'source':source, "user":user, 'ip':self.ipAddress, 'port':12345}
            rest.update_autofailover_settings(True, expectedResults['timeout'])

        elif (ops == 'disableAutoFailover'):
            expectedResults = {'max_nodes':1, "timeout":120, 'source':source, "user":user, 'ip':self.ipAddress, 'port':12345}
            rest.update_autofailover_settings(False, expectedResults['timeout'])

        elif (ops == 'resetAutoFailover'):
            expectedResults = {'source':source, "user":user, 'ip':self.ipAddress, 'port':12345}
            rest.reset_autofailover()

        elif (ops == 'enableClusterAlerts'):
            expectedResults = {"encrypt":False, "email_server:port":25, "host":"localhost", "email_server:user":"ritam", "alerts":["auto_failover_node", "auto_failover_maximum_reached"], \
                             "recipients":["ritam@couchbase.com"], "sender":"admin@couchbase.com", "source":"ns_server", "user":"Administrator", 'ip':self.ipAddress, 'port':1234}
            rest.set_alerts_settings('ritam@couchbase.com', 'admin@couchbase.com', 'ritam', 'password',)

        elif (ops == 'disableClusterAlerts'):
            rest.set_alerts_settings('ritam@couchbase.com', 'admin@couchbase.com', 'ritam', 'password',)
            expectedResults = {'source':source, "user":user, 'ip':self.ipAddress, 'port':1234}
            rest.disable_alerts()

        elif (ops == 'modifyCompactionSettingsPercentage'):
            expectedResults = {"parallel_db_and_view_compaction":False,
                               "database_fragmentation_threshold:percentage":50,
                               "view_fragmentation_threshold:percentage":50,
                               "purge_interval":3,
                               "source":"ns_server",
                               "user":"Administrator",
                               'source':source,
                               "user":user,
                               'ip':self.ipAddress,
                               'port':1234}
            rest.set_auto_compaction(dbFragmentThresholdPercentage=50, viewFragmntThresholdPercentage=50)

        elif (ops == 'modifyCompactionSettingsPercentSize'):
            expectedResults = {"parallel_db_and_view_compaction":False,
                               "database_fragmentation_threshold:percentage":50,
                               "database_fragmentation_threshold:size":10,
                               "view_fragmentation_threshold:percentage":50,
                               "view_fragmentation_threshold:size":10,
                               "purge_interval":3,
                               "source":"ns_server",
                               "user":"Administrator",
                               'source':source,
                               "user":user,
                               'ip':self.ipAddress,
                               'port':1234}
            rest.set_auto_compaction(dbFragmentThresholdPercentage=50,
                                     viewFragmntThresholdPercentage=50,
                                     dbFragmentThreshold=10,
                                     viewFragmntThreshold=10)

        elif (ops == 'modifyCompactionSettingsTime'):
            expectedResults = {"parallel_db_and_view_compaction":False,
                               "database_fragmentation_threshold:percentage":50,
                               "database_fragmentation_threshold:size":10,
                               "view_fragmentation_threshold:percentage":50,
                               "view_fragmentation_threshold:size":10,
                               "allowed_time_period:abort_outside":True,
                               "allowed_time_period:to_minute":15,
                               "allowed_time_period:from_minute":12,
                               "allowed_time_period:to_hour":1,
                               "allowed_time_period:from_hour":1,
                               "purge_interval":3,
                               "source":"ns_server",
                               "user":"Administrator",
                               'source':source,
                               "user":user,
                               'ip':self.ipAddress,
                               'port':1234,
                               }
            rest.set_auto_compaction(dbFragmentThresholdPercentage=50,
                                     viewFragmntThresholdPercentage=50,
                                     dbFragmentThreshold=10,
                                     viewFragmntThreshold=10,
                                     allowedTimePeriodFromHour=1,
                                     allowedTimePeriodFromMin=12,
                                     allowedTimePeriodToHour=1,
                                     allowedTimePeriodToMin=15,
                                     allowedTimePeriodAbort='true')

        elif (ops == "AddGroup"):
            expectedResults = {'group_name':'add group', 'source':source, 'user':user, 'ip':self.ipAddress, 'port':1234}
            rest.add_zone(expectedResults['group_name'])
            tempStr = rest.get_zone_uri()[expectedResults['group_name']]
            tempStr = (tempStr.split("/"))[4]
            expectedResults['uuid'] = tempStr

        elif (ops == "UpdateGroup"):
            expectedResults = {'group_name':'upGroup', 'source':source, 'user':user, 'ip':self.ipAddress, 'port':1234, 'nodes':[]}
            rest.add_zone(expectedResults['group_name'])
            rest.rename_zone(expectedResults['group_name'], 'update group')
            expectedResults['group_name'] = 'update group'
            tempStr = rest.get_zone_uri()[expectedResults['group_name']]
            tempStr = (tempStr.split("/"))[4]
            expectedResults['uuid'] = tempStr

        elif (ops == "UpdateGroupAddNodes"):
            sourceGroup = "Group 1"
            destGroup = 'destGroup'
            expectedResults = {'group_name':destGroup, 'source':source, 'user':user, 'ip':self.ipAddress, 'port':1234, 'nodes':['ns_1@' + self.master.ip], 'port':1234}
            #rest.add_zone(sourceGroup)
            rest.add_zone(destGroup)
            self.sleep(20)
            rest.shuffle_nodes_in_zones([self.master.ip], sourceGroup, destGroup)
            tempStr = rest.get_zone_uri()[expectedResults['group_name']]
            tempStr = (tempStr.split("/"))[4]
            expectedResults['uuid'] = tempStr


        elif (ops == "DeleteGroup"):
            expectedResults = {'group_name':'delete group', 'source':source, 'user':user, 'ip':self.ipAddress, 'port':1234}
            rest.add_zone(expectedResults['group_name'])
            tempStr = rest.get_zone_uri()[expectedResults['group_name']]
            tempStr = (tempStr.split("/"))[4]
            expectedResults['uuid'] = tempStr
            rest.delete_zone(expectedResults['group_name'])

        elif (ops == "regenCer"):
            expectedResults = {'source':source, 'user':user, 'ip':self.ipAddress, 'port':1234}
            rest.regenerate_cluster_certificate()

        elif (ops == 'renameNode'):
            rest.rename_node(self.master.ip, user, password)
            expectedResults = {"hostname":self.master.ip, "node":"ns_1@" + self.master.ip, "source":source, "user":user, "ip":self.ipAddress, "port":56845}

        self.checkConfig(self.eventID, self.master, expectedResults)

    def test_cbDiskConf(self):
        ops = self.input.param('ops', None)
        source = 'ns_server'
        user = self.master.rest_username
        rest = RestConnection(self.master)
        currentPath = '/opt/couchbase/var/lib/couchbase/data'
        newPath = "/tmp"

        if (ops == 'indexPath'):
            try:
                expectedResults = {'node': 'ns_1@' + self.master.ip, 'source':source,
                                   'user':user, 'ip':self.ipAddress, 'port':1234,
                                   'index_path':newPath, 'db_path':currentPath}

                rest.set_data_path(index_path=newPath)
                self.checkConfig(self.eventID, self.master, expectedResults)
            finally:
                rest.set_data_path(index_path=currentPath)


    def test_loginEvents(self):
        ops = self.input.param("ops", None)
        role = self.input.param("role", None)
        username = self.input.param('username', None)
        password = self.input.param('password', None)
        source = 'ns_server'
        rest = RestConnection(self.master)
        user = self.master.rest_username

        if (ops in ['loginRoAdmin', 'deleteuser', 'passwordChange']):
                rest.create_ro_user(username, password)

        if (ops in ['loginAdmin', 'loginRoAdmin']):
            status, content = rest.validateLogin(username, password, True, getContent=True)
            sessionID = (((status['set-cookie']).split("="))[1]).split(";")[0]
            expectedResults = {'source':source, 'user':username, 'password':password, 'role':role, 'ip':self.ipAddress, "port":123456, 'sessionid':sessionID}

        elif (ops in ['deleteuser']):
            expectedResults = {"role":role, "real_userid:source":source, 'real_userid:user':user, 'ip':self.ipAddress, "port":123456, 'userid:source':source, 'userid:user':username}
            rest.delete_ro_user()

        elif (ops in ['passwordChange']):
            expectedResults = {'real_userid:source':source, 'real_userid:user':user,
                               'password':password, 'role':role, 'ip':self.ipAddress, "port":123456,
                               'userid:source':source, 'userid:user':username}
            rest.changePass_ro_user(username, password)

        elif (ops in ['invalidlogin']):
            status, content = rest.validateLogin(username, password, True, getContent=True)
            expectedResults = {'source':source, 'user':username, 'password':password, 'role':role, 'ip':self.ipAddress, "port":123456}


        self.checkConfig(self.eventID, self.master, expectedResults)


    def test_checkCreateBucketCluster(self):
        ops = self.input.param("ops", None)
        source = 'ns_server'
        for server in self.servers:
            user = server.rest_username
            rest = RestConnection(server)
            if (ops in ['create']):
                expectedResults = {'bucket_name':'TestBucket' + server.ip, 'ram_quota':536870912, 'num_replicas':1,
                                   'replica_index':False, 'eviction_policy':'value_only', 'type':'membase', \
                                   'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", \
                                    "flush_enabled":False, "num_threads":3, "source":source, \
                                   "user":user, "ip":self.ipAddress, "port":57457, 'sessionid':'' }
                rest.create_bucket(expectedResults['bucket_name'], expectedResults['ram_quota'] / 1048576, expectedResults['auth_type'], 'password', expectedResults['num_replicas'], \
                                   '11211', 'membase', 0, expectedResults['num_threads'], expectedResults['flush_enabled'], 'valueOnly')
                self.log.info ("value of server is {0}".format(server))
                self.checkConfig(self.eventID, server, expectedResults)

    def test_createBucketClusterNodeOut(self):
        ops = self.input.param("ops", None)
        nodesOut = self.input.param("nodes_out", 1)
        source = 'ns_server'
        user = self.master.rest_username

        firstNode = self.servers[0]
        secondNode = self.servers[1]
        auditFirstNode = audit(host=firstNode)
        auditSecondNode = audit(host=secondNode)

        origState = auditFirstNode.getAuditStatus()
        origLogPath = auditFirstNode.getAuditLogPath()
        origRotateInterval = auditFirstNode.getAuditRotateInterval()

        #Remove the node from cluster & check if there are any change to cluster
        self.cluster.rebalance(self.servers, [], self.servers[1:nodesOut + 1])
        self.assertEqual(auditFirstNode.getAuditStatus(), origState, "Issues with audit state after removing node")
        self.assertEqual(auditFirstNode.getAuditLogPath(), origLogPath, "Issues with audit log path after removing node")
        self.assertEqual(auditFirstNode.getAuditRotateInterval(), origRotateInterval, "Issues with audit rotate interval after removing node")

        restFirstNode = RestConnection(firstNode)
        if (ops in ['create']):
            expectedResults = {'bucket_name':'TestBucketRemNode', 'ram_quota':536870912, 'num_replicas':0,
                                'replica_index':False, 'eviction_policy':'value_only', 'type':'membase', \
                                'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", \
                                "flush_enabled":False, "num_threads":3, "source":source, \
                                "user":user, "ip":self.ipAddress, "port":57457, 'sessionid':'' }
            restFirstNode.create_bucket(expectedResults['bucket_name'], expectedResults['ram_quota'] / 1048576, expectedResults['auth_type'], 'password', expectedResults['num_replicas'], \
                                '11211', 'membase', 0, expectedResults['num_threads'], expectedResults['flush_enabled'], 'valueOnly')

            self.checkConfig(self.eventID, firstNode, expectedResults)

        #Add back the Node in Cluster
        self.cluster.rebalance(self.servers, self.servers[1:nodesOut + 1], [])
        self.assertEqual(auditSecondNode.getAuditStatus(), origState, "Issues with audit state after adding node")
        self.assertEqual(auditSecondNode.getAuditLogPath(), origLogPath, "Issues with audit log path after adding node")
        self.assertEqual(auditSecondNode.getAuditRotateInterval(), origRotateInterval, "Issues with audit rotate interval after adding node")

        for server in self.servers:
            user = server.rest_username
            rest = RestConnection(server)
            if (ops in ['create']):
                expectedResults = {'bucket_name':'TestBucket' + server.ip, 'ram_quota':536870912, 'num_replicas':1,
                                   'replica_index':False, 'eviction_policy':'value_only', 'type':'membase', \
                                   'auth_type':'sasl', "autocompaction":'false', "purge_interval":"undefined", \
                                    "flush_enabled":False, "num_threads":3, "source":source, \
                                   "user":user, "ip":self.ipAddress, "port":57457, 'sessionid':'' }
                rest.create_bucket(expectedResults['bucket_name'], expectedResults['ram_quota'] / 1048576, expectedResults['auth_type'], 'password', expectedResults['num_replicas'], \
                                   '11211', 'membase', 0, expectedResults['num_threads'], expectedResults['flush_enabled'], 'valueOnly')

                self.checkConfig(self.eventID, server, expectedResults)