#!/usr/bin/python -u
# -*- coding: utf-8 -*-
##
##test asterisk 13
##!/usr/bin/python2.7/bin/python -u
## -*- coding: utf-8 -*-
##
## -*- coding: iso8859-1 -*-
##NRG
##
##!/usr/local/bin/python -u
## -*- coding: iso8859-1 -*-
##ARG
##
##!/usr/bin/python -u
## -*- coding: iso8859-1 -*-
##Example
##
##!/usr/local/bin/python2.7/bin/python -u
## -*- coding: iso8859-1 -*-
##Example
##
##
## Add chanel_dongle (http://wiki.e1550.mobi/doku.php?id=Main%20page)
## Add chanel PJSIP
##
MONAST_VERSION = "Copyright (c) 2015 - 2018 ver. 0.7.3.30.07 b"
MONAST_UPDATE = "Kivko Wlad mail@kivko.nsk.ru updates https://yadi.sk/d/PVRLfxQXfNnuZ"
##
## Imports
##
import os
import sys
import re
import datetime
import time
import logging
import optparse
import subprocess

from ConfigParser import SafeConfigParser, NoOptionError

try:
	from twisted.python import failure
	from twisted.internet import reactor, task, defer
	from twisted.internet import error as tw_error
	from twisted.web import server as TWebServer
	from twisted.web import resource
except ImportError:
	print "Monast ERROR: Module twisted not found."
	print "You need twisted matrix 10.1+ to run Monast. Get it from http://twistedmatrix.com/"
	sys.exit(1)

try:
	from starpy import manager
	from starpy.error import AMICommandFailure
except ImportError:
	print "Monast ERROR: Module starpy not found."
	print "You need starpy to run Monast. Get it from http://www.vrplumber.com/programming/starpy/"
	sys.exit(1)
	
try:
	import json
except ImportError:
	import simplejson as json

#import warnings
#warnings.filterwarnings("ignore")

##
## Defines
##
HTTP_SESSION_TIMEOUT          = 60
AMI_RECONNECT_INTERVAL        = 10
TASK_CHECK_STATUS_INTERVAL    = 60
#TASK_CHECK_STATUS_INTERVAL   = 10
TIMER_CLEAR_SMS               = 12
MAX_PEER_ALARMCOUT_ALARM      = 4
MODULE_LOAD_TIMER             = .005

MONAST_CALLERID = "MonAst"

AST_DEVICE_STATES = { # copied from include/asterisk/devicestate.h
	'0': 'Unknown',
	'1': 'Not In Use',
	'2': 'In Use',
	'3': 'Busy',
	'4': 'Invalid',
	'5': 'Unavailable',
	'6': 'Ringing',
	'7': 'Ring, In Use',
	'8': 'On Hold'
}

##
## Logging Initialization
##
log                 = None
logging.DUMPOBJECTS = False
logging.FORMAT      = "[%(asctime)s] %(levelname)-8s :: %(message)s" 
logging.NOTICE      = 60
logging.addLevelName(logging.NOTICE, "NOTICE")

class ColorFormatter(logging.Formatter):
	__colors = {
		'black'  : 30,
		'red'    : 31,
		'green'  : 32,
		'yellow' : 33,
		'blue'   : 34,
		'magenta': 35,
		'cyan'   : 36,
		'white'  : 37
	}
	__levelColors = {
		logging.NOTICE   : 'white',
		logging.INFO     : 'yellow',
		logging.ERROR    : 'red',
		logging.WARNING  : 'magenta',
		logging.DEBUG    : 'cyan'
	}
	
	def __init__(self, fmt = None, datefmt = None):
		logging.Formatter.__init__(self, fmt, datefmt)
		self.colored = hasattr(logging, 'COLORED')
	
	def color(self, levelno, msg):
		if self.colored:
			return '\033[%d;1m%s\033[0m' % (self.__colors[self.__levelColors[levelno]], msg)
		else:
			return msg
	
	def formatTime(self, record, datefmt):
		return self.color(logging.NOTICE, logging.Formatter.formatTime(self, record, datefmt))
	
	def format(self, record):
		if record.levelname == 'DEBUG':
			record.msg = record.msg.encode('utf-8').encode('string_escape')
		
		record.name      = self.color(record.levelno, record.name)
		record.module    = self.color(record.levelno, record.module)
		record.msg       = self.color(record.levelno, record.msg)
		record.levelname = self.color(record.levelno, record.levelname)
		if hasattr(record, 'funcName'):
			record.funcName  = self.color(record.levelno, record.funcName)
			
		if record.exc_info:
			record.exc_text = self.color(record.levelno, '>> %s' % self.formatException(record.exc_info).replace('\n', '\n>> '))
		
		return logging.Formatter.format(self, record)

##
## Classes
##
class GenericObject(object):
	def __init__(self, objecttype = "Generic Object"):
		self.objecttype = objecttype
	def __setattr__(self, key, value):
		self.__dict__[key] = value
	def __getattr__(self, key):
		return self.__dict__.get(key)
	def __delattr__(self, key):
		del self.__dict__[key]
	def __str__(self):
		out = [
			"",
			"##################################################",
			"# Object Type: %s" % self.objecttype,
			"##################################################"
		]
		keys = sorted(self.__dict__.keys())
		pad  = sorted([len(k) for k in keys])[-1]
		
		for key in keys:
			format = "%%%ds : %s" % (pad, '%s')
			value  = self.__dict__.get(key)
			out.append(format % (key, value))
		
		out.append("##################################################")
		
		return "\n".join(out)
	
class ServerObject(GenericObject):
	_maxConcurrentTasks = 1
	_runningTasks       = 0
	_queuedTasks        = []
	
	_callid = 0
	_calls  = {}
	
	def __init__(self):
		GenericObject.__init__(self, "Server")
	
	def _getTaskId(self):
		self._callid += 1
		return self._callid
	
	def pushTask(self, task, *args, **kwargs):
		if self._runningTasks < self._maxConcurrentTasks:
			self._runningTasks += 1
			taskid              = self._getTaskId()
			taskdf              = task(*args, **kwargs).addBoth(self._onTaskDone, taskid)
			calltm              = reactor.callLater(5, self._fireTimeout, taskid, taskdf)
			self._calls[taskid] = calltm
			return taskdf
		queuedf = defer.Deferred()
		self._queuedTasks.append((task, args, kwargs, queuedf))
		return queuedf
	
	def _onTaskDone(self, taskdone, taskid):
		self._runningTasks -= 1
		## Remove Call
		calltm = self._calls.get(taskid)
		if calltm:
			del self._calls[taskid]
			calltm.cancel()
		## Call next task if exists
		if self._runningTasks < self._maxConcurrentTasks and self._queuedTasks:
			self._runningTasks         += 1
			task, args, kwargs, queuedf = self._queuedTasks.pop(0)
			taskid                      = self._getTaskId()
			taskdf                      = task(*args, **kwargs).addBoth(self._onTaskDone, taskid)
			taskdf.chainDeferred(queuedf)
			calltm                      = reactor.callLater(5, self._fireTimeout, taskid, taskdf)
			self._calls[taskid]         = calltm
		## Raize Feilure
		if isinstance(taskdone, failure.Failure):
			taskdone.trap()
		return taskdone
	
	def _fireTimeout(self, taskid, taskdf):
		## Remove Call
		calltm = self._calls.get(taskid)
		if calltm:
			del self._calls[taskid]
		## Fire Timeout
		if not taskdf.called:
			defer.timeout(taskdf)
			
	def clearCalls(self):
		## Clear Pending Calls
		for taskid, call in self._calls.items():
			if call:
				call.args[1].errback(failure.Failure(AMICommandFailure("Connection closed")))
		self._calls.clear()
		## Clear Queue
		while self._queuedTasks:
			task, args, kwargs, queuedf = self._queuedTasks.pop(0)
			queuedf.errback(failure.Failure(AMICommandFailure("Connection closed")))

class MyConfigParser(SafeConfigParser):
	def optionxform(self, optionstr):
		return optionstr

##
## Monast HTTP
##
class MonastHTTP(resource.Resource):
	
	isLeaf   = True
	monast   = None
	sessions = {}
	 
	def __init__(self, host, port):
		log.info('Initializing Monast HTTP Server at %s:%s...' % (host, port))
		self.handlers = {
			'/isAuthenticated' : self.isAuthenticated,
			'/doAuthentication': self.doAuthentication,
			'/doLogout'        : self.doLogout,
			'/getStatus'       : self.getStatus,
			'/listServers'     : self.listServers,
			'/getUpdates'      : self.getUpdates,
			'/doAction'        : self.doAction
		}
	
	def _expireSession(self):
		expired = [sessid for sessid, session in self.sessions.items() if not self.monast.site.sessions.has_key(sessid)]
		for sessid in expired:
			log.info("Removing Expired Client Session: %s" % sessid)
			del self.sessions[sessid]
	
	def _addUpdate(self, **kw):
		session = self.sessions.get(kw.get('sessid'))
		if session:
			session.updates.append(kw)
		else:
			for sessid, session in self.sessions.items():
				session.updates.append(kw)
				
	def _onRequestFailure(self, reason, request):
		session = request.getSession()
		log.error("HTTP Request from %s:%s (%s) to %s failed: %s", request.client.host, request.client.port, session.uid, request.uri, reason.getErrorMessage())
		log.exception("Unhandled Exception on HTTP Request to %s" % request.uri)
		request.setResponseCode(500)
		request.write("ERROR :: Internal Server Error");
		request.finish()
	
	def render_GET(self, request):
		session = request.getSession()
		session.touch()
		log.debug("HTTP Request from %s:%s (%s) to %s", request.client.host, request.client.port, session.uid, request.uri)

		if not self.sessions.has_key(session.uid):
			log.info("New Client Session: %s" % session.uid)
			session._expireCall.cancel()
			session.sessionTimeout = HTTP_SESSION_TIMEOUT
			session.startCheckingExpiration()
			session.notifyOnExpire(self._expireSession)
			session.updates            = []
			session.isAuthenticated    = not self.monast.authRequired
			session.username           = None
			self.sessions[session.uid] = session
		
		if not session.isAuthenticated and request.path != "/doAuthentication":
			return "ERROR :: Authentication Required"
		
		handler = self.handlers.get(request.path)
		if handler:
			d = task.deferLater(reactor, 0.1, lambda: request)
			d.addCallback(handler)
			d.addErrback(self._onRequestFailure, request)
			return TWebServer.NOT_DONE_YET
		
		return "ERROR :: Request Not Found"
	
	def isAuthenticated(self, request):
		request.write(["ERROR :: Authentication Required", "OK"][request.getSession().isAuthenticated])
		request.finish()
	
	def doAuthentication(self, request):
		session  = request.getSession()
		username = request.args.get('username', [None])[0]
		secret   = request.args.get('secret', [None])[0]
		success  = False
		
		if username != None and secret != None:
			authUser = self.monast.authUsers.get(username)
			if authUser:
				if authUser.secret == secret:
					session.isAuthenticated = True
					session.username        = username
					success = True
				else:
					success = False
			else:
				success = False
		else:
			success = False
		
		output = ""
		if success:
			log.log(logging.NOTICE, "User \"%s\" Successful Authenticated with Session \"%s\"" % (username, session.uid))
			request.write("OK :: Authentication Success")
		else:
			log.error("User \"%s\" Failed to Authenticate with session \"%s\"" % (username, session.uid))
			request.write("ERROR :: Invalid Username/Secret")
		request.finish()
	
	def doLogout(self, request):
		session = request.getSession()
		log.log(logging.NOTICE, "User \"%s\" Successful Logout with Session \"%s\"" % (session.username, session.uid))
		session.isAuthenticated = False
		request.write("OK")
		request.finish()
	
	def getStatus(self, request):
		tmp        = {}
		servername = request.args.get('servername', [None])[0]
		session    = request.getSession()
		server     = self.monast.servers.get(servername)
		
		## Clear Updates
		session.updates = []
		
		tmp[servername] = {
			'peers': {},
			'channels': [],
			'bridges': [],
			'meetmes': [],
			'queues': [],
			'queueMembers': [],
			'queueClients': [],
			'queueCalls': [],
			'parkedCalls': []
		}
		## Peers
		for tech, peerlist in server.status.peers.items():
			tmp[servername]['peers'][tech] = []
			for peername, peer in peerlist.items():
				tmp[servername]['peers'][tech].append(peer.__dict__)
			tmp[servername]['peers'][tech].sort(lambda x, y: cmp(x.get(self.monast.sortPeersBy), y.get(self.monast.sortPeersBy)))
		## Channels
		for uniqueid, channel in server.status.channels.items():
			tmp[servername]['channels'].append(channel.__dict__)
		tmp[servername]['channels'].sort(lambda x, y: cmp(x.get('starttime'), y.get('starttime')))
		## Bridges
		for uniqueid, bridge in server.status.bridges.items():
			bridge.seconds = [0, int(time.time() - bridge.linktime)][bridge.status == "Link"]
			tmp[servername]['bridges'].append(bridge.__dict__)
		tmp[servername]['bridges'].sort(lambda x, y: cmp(x.get('seconds'), y.get('seconds')))
		tmp[servername]['bridges'].reverse()
		#tmp[servername]['bridges'].sort(lambda x, y: cmp(x.get('dialtime'), y.get('dialtime')))
		## Meetmes
		for meetmeroom, meetme in server.status.meetmes.items():
			tmp[servername]['meetmes'].append(meetme.__dict__)
		tmp[servername]['meetmes'].sort(lambda x, y: cmp(x.get('meetme'), y.get('meetme')))
		## Parked Calls
		for channel, parked in server.status.parkedCalls.items():
			tmp[servername]['parkedCalls'].append(parked.__dict__)
		tmp[servername]['parkedCalls'].sort(lambda x, y: cmp(x.get('exten'), y.get('exten')))
		## Queues
		for queuename, queue in server.status.queues.items():
			tmp[servername]['queues'].append(queue.__dict__)
		tmp[servername]['queues'].sort(lambda x, y: cmp(x.get('queue'), y.get('queue')))
		for (queuename, membername), member in server.status.queueMembers.items():
			member.pausedur = int(time.time() - member.pausedat)
			tmp[servername]['queueMembers'].append(member.__dict__)
		tmp[servername]['queueMembers'].sort(lambda x, y: cmp(x.get('name'), y.get('name')))
		for (queuename, uniqueid), client in server.status.queueClients.items():
			client.seconds = int(time.time() - client.jointime)
			tmp[servername]['queueClients'].append(client.__dict__)
		tmp[servername]['queueClients'].sort(lambda x, y: cmp(x.get('seconds'), y.get('seconds')))
		tmp[servername]['queueClients'].reverse()
		for uniqueid, call in server.status.queueCalls.items():
			if call.client and call.member:
				call.seconds = int(time.time() - call.starttime)  
				tmp[servername]['queueCalls'].append(call.__dict__)
					 
#		request.write(json.dumps(tmp, encoding = "ISO8859-1"))
		request.write(json.dumps(tmp, encoding = "UTF-8"))
		request.finish()
	
	def getUpdates(self, request):
		session    = request.getSession()
		servername = request.args.get('servername', [None])[0]
		updates    = []
		if len(session.updates) > 0:
			updates         = [u for u in session.updates if u.get('servername') == servername]
			session.updates = []
		if len(updates) > 0:
#			request.write(json.dumps(updates, encoding = "ISO8859-1"))
			request.write(json.dumps(updates, encoding = "UTF-8"))
		else:
			request.write("NO UPDATES")
		request.finish()
	
	def listServers(self, request):
		session = request.getSession()
		servers = self.monast.servers.keys()
		if self.monast.authRequired and session.isAuthenticated and session.username:
			servers = self.monast.authUsers[session.username].servers.keys()
		servers.sort()		
#		request.write(json.dumps(servers, encoding = "ISO8859-1"))
		request.write(json.dumps(servers, encoding = "UTF-8"))
		request.finish()
	
	def doAction(self, request):
		session = request.getSession()
		self.monast.clientActions.append((session, request.args))
		reactor.callWhenRunning(self.monast._processClientActions)
		request.write("OK")
		request.finish()

##
## Monast AMI
##
class MonastAMIProtocol(manager.AMIProtocol):
	"""Class Extended to solve some issues on original methods"""
	def connectionLost(self, reason):
		"""Connection lost, clean up callbacks"""
		for key,callable in self.actionIDCallbacks.items():
			try:
				callable(tw_error.ConnectionDone("""AMI connection terminated"""))
			except Exception, err:
				log.error("""Failure during connectionLost for callable %s: %s""", callable, err)
		self.actionIDCallbacks.clear()
		self.eventTypeCallbacks.clear()
		
	def collectDeferred(self, message, stopEvent):
		"""Collect all responses to this message until stopEvent or error
		   returns deferred returning sequence of events/responses
		"""
		df = defer.Deferred()
		cache = []
		def onEvent(event):
			if type(event) == type(dict()):
				if event.get('response') == 'Error':
					df.errback(AMICommandFailure(event))
				elif event['event'] == stopEvent:
					df.callback(cache)
				else:
					cache.append(event)
			else:
				df.errback(AMICommandFailure(event))
		actionid = self.sendMessage(message, onEvent)
		df.addCallbacks(
			self.cleanup, self.cleanup,
			callbackArgs=(actionid,), errbackArgs=(actionid,)
		)
		return df
	
	def errorUnlessResponse(self, message, expected='Success'):
		"""Raise a AMICommandFailure error unless message['response'] == expected
		If == expected, returns the message
		"""
		if type(message) == type(dict()) and message['response'] != expected or type(message) != type(dict()):
			raise AMICommandFailure(message)
		return message
	
	def redirect(self, channel, context, exten, priority, extraChannel = None, extraContext = None, extraExten = None, extraPriority = None):
		"""Transfer channel(s) to given context/exten/priority"""
		message = {
			'action': 'redirect', 'channel': channel, 'context': context,
			'exten': exten, 'priority': priority,
		}
		if extraChannel is not None:
			message['extrachannel'] = extraChannel
		if extraExten is not None:
			message['extraexten'] = extraExten
		if extraContext is not None:
			message['extracontext'] = extraContext
		if extraPriority is not None:
			message['extrapriority'] = extraPriority
		return self.sendDeferred(message).addCallback(self.errorUnlessResponse)

	def stopMonitor(self, channel):
		"""Stop monitorin the given channel"""
		message = {"action": "stopmonitor", "channel": channel}
		return self.sendDeferred(message).addCallback(self.errorUnlessResponse)

	def queueAdd(self, queue, interface, penalty=0, paused=True, membername=None, stateinterface=None):
		"""Add given interface to named queue"""
		if paused in (True,'true',1):
			paused = 'true'
		else:
			paused = 'false'
		message = {'action': 'queueadd', 'queue': queue, 'interface': interface, 'penalty':penalty, 'paused': paused}
		if membername is not None:
			message['membername'] = membername
		if stateinterface is not None:
			message['stateinterface'] = stateinterface
		return self.sendDeferred(message).addCallback(self.errorUnlessResponse)


class MonastAMIFactory(manager.AMIFactory):
	amiWorker  = None
	servername = None
	protocol   = MonastAMIProtocol
	def __init__(self, servername, username, password, amiWorker):
		log.info('Server %s :: Initializing Monast AMI Factory...' % servername)
		self.servername = servername
		self.amiWorker  = amiWorker
		manager.AMIFactory.__init__(self, username, password)
		
	def clientConnectionLost(self, connector, reason):
		log.warning("Server %s :: Lost connection to AMI: %s" % (self.servername, reason.value))
		self.amiWorker.__disconnected__(self.servername)
		reactor.callLater(AMI_RECONNECT_INTERVAL, self.amiWorker.connect, self.servername)

	def clientConnectionFailed(self, connector, reason):
		log.error("Server %s :: Failed to connected to AMI: %s" % (self.servername, reason.value))
		self.amiWorker.__disconnected__(self.servername)
		reactor.callLater(AMI_RECONNECT_INTERVAL, self.amiWorker.connect, self.servername)
		
class Monast:

	configFile         = None
	servers            = {}
	sortPeersBy        = 'callerid'
	clientActions      = []
	authRequired       = False
	isParkedCallStatus = False
	
	def __init__(self, configFile):
		log.log(logging.NOTICE, "Initializing Monast AMI Interface...")
		
		self.eventHandlers = {
			'Reload'              : self.handlerEventReload,
			'Shutdown'            : self.handlerEventReload,
			'ModuleLoad'          : self.handlerEventModuleLoad,
#			'ModuleLoadReport'    : self.handlerEventModuleLoadReport,
			'ChannelReload'       : self.handlerEventChannelReload,
			'Alarm'               : self.handlerEventAlarm,
			'AlarmClear'          : self.handlerEventAlarmClear,
			'DNDState'            : self.handlerEventDNDState,
			'PeerEntry'           : self.handlerEventPeerEntry,
			'PeerStatus'          : self.handlerEventPeerStatus,
##			'RTCPReceived'        : self.handlerEventRTCPReceived,
##			'ContactStatus'        : self.handlerEventContactStatus,
			'EndpointList'        : self.handlerEventEndpointList,
			'EndpointDetail'      : self.handlerEventEndpointDetail,
			'AorDetail'           : self.handlerEventAorDetail,
			'AuthDetail'          : self.handlerEventAuthDetail,
			'TransportDetail'     : self.handlerEventTransportDetail,
			'IdentifyDetail'      : self.handlerEventIdentifyDetail,
			'EndpointlistComplete': self.handlerEventEndpointlistComplete,

#			'BridgeCreate'        : self.handlerEventBridgeCreate,
			'BridgeEnter'         : self.handlerEventBridgeEnter,
#			'BridgeLeave'         : self.handlerEventUBridgeLeave, # не актуально
			'BridgeDestroy'       : self.handlerEventBridgeDestroy,
			'BridgeUpdate'        : self.handlerEventBridgeUpdate,
			'DAHDIChannel'        : self.handlerEventDAHDIChannel,
			'UserEvent'           : self.handlerEventUserEvent,
			'DongleStatus'        : self.handlerEventDongleStatus,
			'DonglePortFail'      : self.handlerEventDonglePortFail,
			'DongleChanelStatus'  : self.handlerEventDongleChanelStatus,
			'DongleCallStateChange' : self.handlerEventDongleCallStateChange,
			'DongleAntennaLevel'  : self.handlerEventDongleAntennaLevel,
			'DongleNewSMSBase64'  : self.handlerEventDongleNewSmsBase64,
			'DongleNewUSSD'       : self.handlerEventDongleNewUSSD,
			'DongleUSSDStatus'    : self.handlerEventDongleSentUSSDNotify,
			'DongleSMSStatus'     : self.handlerEventDongleSentSMSNotify,
			'Newchannel'          : self.handlerEventNewchannel,
			'Newstate'            : self.handlerEventNewstate,
			'Rename'              : self.handlerEventRename,
			'Masquerade'          : self.handlerEventMasquerade,
			'Newcallerid'         : self.handlerEventNewcallerid,
			'NewCallerid'         : self.handlerEventNewcallerid,
			'Hangup'              : self.handlerEventHangup,
			'Dial'                : self.handlerEventDial,
			'Link'                : self.handlerEventLink,
			'Unlink'              : self.handlerEventUnlink,
			'Bridge'              : self.handlerEventBridge,
			'MeetmeJoin'          : self.handlerEventMeetmeJoin,
			'MeetmeLeave'         : self.handlerEventMeetmeLeave,
			'ParkedCall'          : self.handlerEventParkedCall,
			'UnParkedCall'        : self.handlerEventUnParkedCall,
			'ParkedCallTimeOut'   : self.handlerEventParkedCallTimeOut,
			'ParkedCallGiveUp'    : self.handlerEventParkedCallGiveUp,
			'QueueMemberAdded'    : self.handlerEventQueueMemberAdded,
			'QueueMemberRemoved'  : self.handlerEventQueueMemberRemoved,
			'Join'                : self.handlerEventJoin, # Queue Join Поднимается, когда канал соединяется с очередью.
			'Leave'               : self.handlerEventLeave, # Queue Leave Поднимается, когда канал выходит из очереди.

			'QueueCallerJoin'     : self.handlerEventJoin, # Queue Join Поднимается, когда канал соединяется с очередью.
			'QueueCallerLeave'    : self.handlerEventLeave, # Queue Leave Поднимается, когда канал выходит из очереди.


			'QueueCallerAbandon'  : self.handlerEventQueueCallerAbandon,
			'QueueMemberStatus'   : self.handlerEventQueueMemberStatus,
			'QueueMemberPaused'   : self.handlerEventQueueMemberPaused,
			'QueueMemberPause'    : self.handlerEventQueueMemberPaused, # 12 выше

			'MonitorStart'        : self.handlerEventMonitorStart,
			'MonitorStop'         : self.handlerEventMonitorStop,
			'AntennaLevel'        : self.handlerEventAntennaLevel,
			'BranchOnHook'        : self.handlerEventBranchOnHook,
			'BranchOffHook'       : self.handlerEventBranchOffHook,
			'ChanSpyStart'        : self.handlerEventChanSpyStart,
			'ChanSpyStop'         : self.handlerEventChanSpyStop,
		}
		
		self.actionHandlers = {
			'CliCommand'         : ('command', self.clientAction_CliCommand),
			'RequestInfo'        : ('command', self.clientAction_RequestInfo),
			'Originate'          : ('originate', self.clientAction_Originate),
			'Transfer'           : ('originate', self.clientAction_Transfer),
			'Park'               : ('originate', self.clientAction_Park),
			'Hangup'       	     : ('originate', self.clientAction_Hangup),
			'MonitorStart'       : ('originate', self.clientAction_MonitorStart),
			'MonitorStop'        : ('originate', self.clientAction_MonitorStop),
			'QueueMemberPause'   : ('queue', self.clientAction_QueueMemberPause),
			'QueueMemberUnpause' : ('queue', self.clientAction_QueueMemberUnpause),
			'QueueMemberAdd'     : ('queue', self.clientAction_QueueMemberAdd),
			'QueueMemberRemove'  : ('queue', self.clientAction_QueueMemberRemove),
			'MeetmeKick'         : ('originate', self.clientAction_MeetmeKick),
			'SpyChannel'         : ('spy', self.clientAction_SpyChannel),
		}
		
		self.configFile = configFile
		self.__parseMonastConfig()
		
	def __start(self):
		log.info("Starting Monast Services...")
		for servername in self.servers:
			reactor.callWhenRunning(self.connect, servername)
	
	def __connected__(self, ami, servername):
		log.info("Server %s :: Marking as connected..." % servername)
		ami.servername   = servername
		server           = self.servers.get(servername)
		server.connected = True
		server.ami       = ami
		
		## Request Server Version
		def _onCoreShowVersion(result):
			versions = [1.4, 1.6, 1.8, 10, 11, 12, 13, 14, 15, 16] 
			log.info("Server %s :: %s" %(servername, result[0]))
##			log.log(logging.NOTICE, "Server %s :: Asterisk CoreShowVersion [%s]" % (servername, result[0]))

			for version in versions:
				if "Asterisk %s" % version in result[0]:
					server.version = version
					log.log(logging.NOTICE, "Server %s :: Asterisk Version [%s]" % (servername, server.version))
					log.log(logging.NOTICE, "Server %s :: Monast %s" % (servername, MONAST_VERSION))
					log.log(logging.NOTICE, "Server %s :: %s" % (servername, MONAST_UPDATE))
					break
			for event, handler in self.eventHandlers.items():
				log.debug("Server %s :: Registering EventHandler for %s" % (servername, event))
				server.ami.registerEvent(event, handler)
			log.debug("Server %s :: Starting Task Check Status..." % servername)
			server.taskCheckStatus.start(TASK_CHECK_STATUS_INTERVAL, False)
			self._requestAsteriskConfig(servername)
			
		server.pushTask(server.ami.command, 'core show version') \
			.addCallbacks(_onCoreShowVersion, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting Asterisk Version"))
		
	def __disconnected__(self, servername):
		server = self.servers.get(servername)
		if server.connected:
			log.info("Server %s :: [%s] :: Marking as disconnected..." % (servername, server.hostname))
			log.debug("Server %s :: [%s] :: Stopping Task Check Status..." % (servername, server.hostname))
			server.clearCalls()
			if server.taskCheckStatus.running:
				server.taskCheckStatus.stop()
		server.connected = False
		server.ami       = None
	
	def connect(self, servername):
		server = self.servers.get(servername)
		log.info("Server %s :: Trying to connect to AMI at %s:%d" % (servername, server.hostname, server.hostport))
		df = server.factory.login(server.hostname, server.hostport)
		df.addCallback(self.onLoginSuccess, servername)
		df.addErrback(self.onLoginFailure, servername)
		return df
		
	def onLoginSuccess(self, ami, servername):
		server = self.servers.get(servername)
		log.log(logging.NOTICE, "Server %s :: [%s] :: AMI Connected..." % (servername, server.hostname))
#		log.log(logging.NOTICE, "Server %s :: AMI Connected..." % (servername))
		self.__connected__(ami, servername)
		
	def onLoginFailure(self, reason, servername):
		server = self.servers.get(servername)
		log.error("Server %s :: [%s] :: Monast AMI Failed to Login, reason: %s" % (servername, server.hostname, reason.getErrorMessage()))
#		log.error("Server %s :: Monast AMI Failed to Login, reason: %s" % (servername, reason.getErrorMessage()))
		self.__disconnected__(servername)
		
	##
	## Helpers
	##
	## Users/Peers
	def _createPeer(self, servername, **kw):
		server      = self.servers.get(servername)
		channeltype = kw.get('channeltype')
		peername    = kw.get('peername')
		_log        = kw.get('_log', '')
		
		if not server.status.peers.has_key(channeltype) and kw.get('forced', False):
			log.warning("Server %s :: Adding a not implemented ChannelType %s (forced in config file)", servername, channeltype)
			server.status.peers[channeltype] = {}
		
		if server.status.peers.has_key(channeltype):
			peer = server.status.peers[channeltype].get(peername)
			if not peer:
				peer = GenericObject("User/Peer")
				peer.channeltype = channeltype
				peer.peername    = peername
				peer.channel     = '%s/%s' % (channeltype, peername)
				peer.callerid    = kw.get('callerid', '--')
				peer.forced      = kw.get('forced', False)
				peer.forcedCid   = kw.get('forcedCid', False)
				try:
					peer.peergroup = server.peergroups[channeltype][peername]
				except:
					if len(server.peergroups.keys()) > 0:
						peer.peergroup = "No Group"
			
			peer.context     = kw.get('context', server.default_context)
			peer.variables   = kw.get('variables', [])
			peer.status      = kw.get('status', '--')
			peer.time        = kw.get('time', -1)
			peer.calls       = int(kw.get('calls', 0))

			if channeltype == 'PJSIP':
				if peer.callerid == "--":
					peer.callerid = [peer.callerid, peer.peername][peer.callerid == '--']

				## делаем запрос на апдейт информации по пиру
				## Peers PJSIP :: PJSIPShowEndpoint Peername - Process results via events include 
				## EndpointDetail, AorDetail, AuthDetail, TransportDetail, and IdentifyDetail.

				log.debug("Server %s :: Requesting PJSIP Peer [%s] detal info" % (servername, peer.peername))
				if not peer.forcedCid:						
					server.pushTask(server.ami.sendDeferred, {'action': 'pjsipshowendpoint', 'endpoint': "%s" % peer.peername}) \
						.addCallback(server.ami.errorUnlessResponse) \
						.addErrback(self._onAmiCommandFailure, servername, "Error Requesting PJSIP Peer [%s] detal info" % peer.peername)
##						.addErrback(self._onAmiCommandFailure, servername, "Error Requesting PJSIP Peer [%s] detal info" % int(peer.peername))


			## Dahdi Specific attributes
			if channeltype == 'DAHDI':
				peer.signalling = kw.get('signalling')
				peer.alarm      = kw.get('alarm', '--')
				peer.dnd        = kw.get('dnd', 'disabled').lower() == 'enabled'
				peer.status     = ['--', peer.alarm][peer.status == '--']
				peer.uniqueid   = kw.get('uniqu', 0)
				if peer.callerid == "--":
					if peer.peername.isdigit():
						peer.callerid = [peer.channel, "%s %02d" % (peer.signalling, int(peer.peername))][peer.callerid == '--']
					else:
						peer.callerid = [peer.channel, "%s %s" % (peer.signalling, peer.peername)][peer.callerid == '--']

			## DONGLE отображение в Peers/Users
			if channeltype == 'Dongle':
				peer.channel  = peername ## одинокое имя донгла
##				log.warning("Server %s :: Peers/Users server [%s], channeltype [%s], peername [%s], some AMI events...", servername, server, channeltype, peername) 
##				log.warning("Server %s :: not peer, peer.channeltype [%s], peer.peername [%s], peer.channel = [%s], peer.callerid = [%s], some AMI events...", servername, peer.channeltype, peer.peername, peer.channel, peer.callerid)

				if peer.status == '--':
					peer.status   = "Not found"
				peer.alarm = kw.get('alarm', '--')

				if peer.sms != -1:
					peer.level       = kw.get('level', '--')
					peer.quality     = kw.get('quality', '--')
					peer.sms         = kw.get('sms', '--')
					peer.portfail    = int(kw.get('portfail', 0)) 
					peer.callincom   = int(kw.get('callincom', 0))
					peer.calldialing = int(kw.get('calldialing', 0))
					peer.calloutcom  = int(kw.get('calloutcom', 0))
					peer.alarmcount  = int(kw.get('alarmcount', 0))
					peer.reboot      = int(kw.get('reboot', 0))
					peer.smsincom    = int(kw.get('smsincom', 0))
					peer.smssend     = int(kw.get('smssend', 0))
					peer.smserror    = int(kw.get('smserror', 0))
					peer.ussdincom   = int(kw.get('ussdincom', 0))
					peer.ussdsend    = int(kw.get('ussdsend', 0))
				
				if peer.callerid == "--":
					peer.callerid = [peer.callerid, peer.channel][peer.callerid == '--']
					peer.callerid = [peer.channel, "Dongle %s" % peer.peername]['Signal' in peer.status]
			
			## Khomp
			if channeltype == 'Khomp':
				peer.alarm = kw.get('alarm', '--')
				if peer.callerid == "--":
					peer.callerid = [peer.callerid, peer.channel][peer.callerid == '--']
					peer.callerid = [peer.channel, "KGSM %s" % peer.peername]['Signal' in peer.status]
					peer.context  = 'set-netu'
				
			log.debug("Server %s :: Adding User/Peer %s %s", servername, peer.channel, _log)
			server.status.peers[peer.channeltype][peer.peername] = peer
			
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", peer)
		else:
			log.warning("Server %s :: Channeltype %s not implemented in Monast.", servername, channeltype)

	def _DongleSaveStat(self, servername, **kw):
		server      = self.servers.get(servername)
		channeltype = kw.get('channeltype')
		_log        = kw.get('_log', '')
		
		if not server.status.peers.has_key(channeltype) and kw.get('forced', False):
			log.warning("Server %s :: Adding a not implemented ChannelType %s (forced in config file)", servername, channeltype)
			server.status.peers[channeltype] = {}
		
		now_time = datetime.datetime.now() # Текущая дата со временем
		old_stdout = sys.stdout
		
		donglestatpathserver = self.donglestatpath + '/' + servername + '/'
		if os.path.exists(donglestatpathserver) == False:
			log.warning("Server %s :: Create path %s", servername, donglestatpathserver)  
			os.makedirs(donglestatpathserver)
			
		statfile = donglestatpathserver  + now_time.strftime("%Y-%m-") + 'donglestat.log'
		
##		statfile = self.donglestatpath + '/' + now_time.strftime("%Y-%m-") + 'donglestat.log'
##		if os.path.exists(self.donglestatpath) == False:
##			os.makedirs(self.donglestatpath)
		
		sys.stdout = open(statfile, 'a')

##	filedate = now_time.strftime("%Y-%m-")
##		print '%s' % now_time.hour
##		print '%s' % now_time.minute
##		print(now_time.strftime("%d.%m.%Y %I:%M %p")) # форматируем дату
##		print(now_time.strftime("%d.%m.%Y %H:%M")) # форматируем дату

##	формируем строку заголовка
		print '%-10s %-5s %-11s %-6s %-8s %-9s %-10s %-9s %-10s %-8s %-8s %-9s %-9s' %("Date", "Time", "Dongle name", "Reboot", "PortFail", "AlarmCount", "Total call", "Outgoning", "Not answer", "Incoming", "SMS sent", "SMS s.err", "SMS incom")
		
		for channeltype, peers in server.status.peers.items():
			toSave = []
			toSaveTmp = []
			for peername, peer in peers.items():
				if channeltype == 'Dongle':
					toSave.append(peername)
##			['dn12', 'dn11', 'dn13', 'dn5', 'dn4', 'dn7', 'dn6', 'dn1', 'dn14', 'dn3', 'dn2', 'dn15', 'dn8']	
			
			toSaveTmp = sorted(toSave) 									## по алфавиту
			toSaveSorted = sorted(toSaveTmp, key=len)		## по длинне
			for peername in toSaveSorted:
				peer = self.servers.get(servername).status.peers.get(channeltype, {}).get(peername)
				print '%16s %-11s %-6d %-8d  %-10d %-10d %-9d %-10d %-8d %-8d %-9d %-9d' % (now_time.strftime("%d.%m.%Y %H:%M"), peername, peer.reboot, peer.portfail, peer.alarmcount, (peer.calldialing + peer.calloutcom), peer.calloutcom, peer.calldialing, peer.callincom , peer.smssend, peer.smserror, peer.smsincom)
		
	##	возвращаем назад старый вывод
		sys.stdout = old_stdout

		log.debug("Server %s :: [%s] :: Save Statistic User/Peer %s %s", servername, self.servers[servername].hostname, peer.channel, _log)		
		log.warning("Server %s :: [%s] :: SaveStat,  some Server events...", servername, self.servers[servername].hostname)

	def sortByLength(inputStr):
		return len(inputStr) # Ключом является длина каждой строки, сортируем по длине


	def _DongleResetStat(self, servername, **kw):
		server      = self.servers.get(servername)
		channeltype = kw.get('channeltype')
		_log        = kw.get('_log', '')
		
		if not server.status.peers.has_key(channeltype) and kw.get('forced', False):
			log.warning("Server %s :: Adding a not implemented ChannelType %s (forced in config file)", servername, channeltype)
			server.status.peers[channeltype] = {}

		for channeltype, peers in server.status.peers.items():
			toReset = []
			for peername, peer in peers.items():
				if channeltype == 'Dongle':
					toReset.append(peername)
			for peername in toReset:
##					log.warning("Server %s :: [%s] :: _ResetStat, Dongle peername [%s], channeltype [%s],  some Server events...", servername, self.servers[servername].hostname, peername, channeltype) 
					self._updatePeer(servername, channeltype = channeltype, peername = peername, _action = 'resetDongleStat')
					
					log.debug("Server %s :: [%s] :: Reset Statistic User/Peer %s %s", servername, self.servers[servername].hostname, peer.channel, _log)
	
	def _deletePeer(self, servername, **kw):
		server      = self.servers.get(servername)
		channeltype = kw.get('channeltype')
		deletepeername  = kw.get('peername')
		status      = kw.get('status')
		_log        = kw.get('_log', '')
		
		if not server.status.peers.has_key(channeltype) and kw.get('forced', False):
			log.warning("Server %s :: Adding a not implemented ChannelType %s (forced in config file)", servername, channeltype)
			server.status.peers[channeltype] = {}

##		if server.status.peers.has_key(channeltype):
##			peer = server.status.peers[channeltype].get(deletepeername)
##			if not peer:
##				peer = GenericObject("User/Peer")
##				peer.channeltype = channeltype
##				peer.peername    = deletepeername

		if channeltype == 'Dongle':
			for channeltype, peers in server.status.peers.items():
				toRemove = []
				for peername, peer in peers.items():
					if channeltype == 'Dongle':
						if peername == deletepeername:
							toRemove.append(peername)
##							log.warning("Server %s :: _deletePeer [%s], Dongle peername [%s], peer.forced [%s], status [%s], some AMI events...", servername, deletepeername, peername, peer.forced, peer.status) 
				for peername in toRemove:
						del peers[peername]
		else:
			if server.status.peers.has_key(channeltype):
				peer = server.status.peers[channeltype].get(deletepeername)
				if not peer:
					peer = GenericObject("User/Peer")
					peer.channeltype = channeltype
					peer.peername    = deletepeername
						
		log.debug("Server %s :: Delete User/Peer %s %s", servername, peer.channel, _log)
	
	def _updatePeer(self, servername, **kw):
		channeltype = kw.get('channeltype')
		peername    = kw.get('peername')
		_log        = kw.get('_log', '')
		try:
			peer = self.servers.get(servername).status.peers.get(channeltype, {}).get(peername)
			if peer:
##				log.debug("Server %s :: Updating User/Peer %s/%s %s", servername, channeltype, peername, _log)
				if channeltype == 'DAHDI':
					uniqueid    = kw.get('uniqueid', 0)
					log.debug("Server %s :: Updating User/Peer %s/%s Uniqueid %s %s", servername, channeltype, peername, uniqueid, _log)
				else:
					log.debug("Server %s :: Updating User/Peer %s/%s %s", servername, channeltype, peername, _log)
					
				for k, v in kw.items():
					if k == '_action':
						if v == 'increaseCallCounter':
							peer.calls += 1
						elif v == 'decreaseCallCounter':
							peer.calls -= 1

						elif v == 'increaseDahdiCallCounter':
##							uniqueid    = kw.get('uniqueid')
							peer.calls = 1
							peer.uniqueid = uniqueid
						elif v == 'decreaseDahdiCallCounter':
							peer.calls = 0
							peer.uniqueid = 0

						elif v == 'increaseDonglePortFail':
							peer.portfail     += 1
##							log.warning("Server %s :: Dongle PortFail [%s], Counter = [%s]  some AMI events...", servername, peer.peername, peer.portfail)

						elif v == 'clearSms':
							if peer.time > 0 :
								if int(time.time() - peer.time) > TIMER_CLEAR_SMS:
									## log.warning("Server %s :: Dongle clearSms [%s], Status = [%s], Time = [%s], Counter = [%s], TimeCear = [%s]  some AMI events...", servername, peer.peername, peer.status, peer.time, v, int(time.time() - peer.time))
									peer.sms       = '--'
									peer.time      = -1
						elif v == 'increaseCallDialing':
							peer.calldialing  += 1
							peer.alarmcount   += 1
							if peer.alarmcount > MAX_PEER_ALARMCOUT_ALARM:
								peer.alarm = 'alarm'
							if peer.time > 0:
								if int(time.time() - peer.time) > TIMER_CLEAR_SMS:
									##log.warning("Server %s :: Dongle clearSms [%s], Status = [%s], Time = [%s], Counter = [%s], TimeCear = [%s]  some AMI events...", servername, peer.peername, peer.status, peer.time, v, int(time.time() - peer.time))
									peer.sms    = '--'
									peer.time   = -1
						elif v == 'increaseCallOutcom':
							peer.calloutcom += 1
							peer.alarmcount  = 0 
							peer.alarm       = '--'
						elif v == 'increaseCallIncom':
							peer.callincom  += 1
							if peer.time > 0:
								if int(time.time() - peer.time) > TIMER_CLEAR_SMS:
									##log.warning("Server %s :: Dongle clearSms [%s], Status = [%s], Time = [%s], Counter = [%s], TimeCear = [%s]  some AMI events...", servername, peer.peername, peer.status, peer.time, v, int(time.time() - peer.time))
									peer.sms    = '--'
									peer.time   = -1
						elif v == 'reboot':
							peer.reboot     += 1
							peer.alarmcount  = 0
							peer.alarm       = "--"
						elif v == 'increaseSmsIncom':
							peer.smsincom   += 1
						elif v == 'increaseSmsSend':
							peer.smssend    += 1
						elif v == 'increaseSmsError':
							peer.smserror   += 1
						elif v == 'increaseUSSDIncom':
							peer.ussdincom  += 1
						elif v == 'increaseUSSDSend':
							peer.ussdsend   += 1
						elif v == 'resetDongleStat':
							peer.portfail    = 0
							peer.callincom   = 0
							peer.calldialing = 0
							peer.calloutcom  = 0
							peer.alarmcount  = 0
							peer.reboot      = 0
							peer.smsincom    = 0
							peer.smssend     = 0
							peer.smserror    = 0
							peer.ussdincom   = 0
							peer.ussdsend    = 0
							peer.alarm       = "--"
				##		-----------------------------------------------------------------------
					# Ignore callerid on forced peers
					if k == "callerid" and peer.forcedCid:
						continue
					# Update peer
					if k not in ('_log', '_action'): 
						if peer.__dict__.has_key(k):
							peer.__dict__[k] = v
						else:
							log.warning("Server %s :: User/Peer %s/%s does not have attribute %s", servername, channeltype, peername, k)
				self.http._addUpdate(servername = servername, **peer.__dict__.copy())
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", peer)
			else:
				if channeltype != 'Local':
					self._requestAsteriskPeers(servername, channeltype)

#				if ((channeltype == 'SIP') or (channeltype == 'PJSIP') or (channeltype == 'IAX2') or (channeltype == 'Dongle')):
#					self._requestAsteriskPeers(servername)
			#	else:
			#		log.warning("Server %s :: User/Peer not found: %s/%s", servername, channeltype, peername)					
		except:
			log.exception("Server %s :: Unhandled exception updating User/Peer: %s/%s", servername, channeltype, peername)
	
	## Channels	
	def _createChannel(self, servername, **kw):
		server        = self.servers.get(servername)
		uniqueid      = kw.get('uniqueid')
		channel       = kw.get('channel')
		_log          = kw.get('_log', '')
		
		if not server.status.channels.has_key(uniqueid):
			chan              = GenericObject("Channel")
			chan.uniqueid     = uniqueid
			chan.channel      = channel
			chan.state        = kw.get('state', 'Unknown')
			chan.calleridnum  = kw.get('calleridnum', '')
			chan.calleridname = kw.get('calleridname', '')
			chan.bridgeduniqueid = kw.get('bridgeduniqueid', '')
			chan.monitor      = kw.get('monitor', False)
			chan.spy          = kw.get('spy', False)
			chan.starttime    = time.time()
			
			log.debug("Server %s :: Channel create: %s (%s) %s", servername, uniqueid, channel, _log)
			server.status.channels[uniqueid] = chan
			self.http._addUpdate(servername = servername, **chan.__dict__.copy())
			
			channeltype, peername = channel.rsplit('-', 1)[0].split('/', 1)

			self._updatePeer(servername, channeltype = channeltype, peername = peername, _action = 'increaseCallCounter')
			
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", chan)
			return True
		else:
			if not kw.get('_isCheckStatus'):
				log.warning("Server %s :: Channel already exists: %s (%s)", servername, uniqueid, channel)
		return False
	
	def _lookupChannel(self, servername, chan):
		server  = self.servers.get(servername)
		channel = None
		for uniqueid, channel in server.status.channels.items():
			if channel.channel == chan:
				break
		return channel
	
	def _updateChannel(self, servername, **kw):
		uniqueid = kw.get('uniqueid')
		channel  = kw.get('channel')
		_log     = kw.get('_log', '')
		
		try:
			chan = self.servers.get(servername).status.channels.get(uniqueid)
			if chan:
				log.debug("Server %s :: Channel update: %s (%s) %s", servername, uniqueid, chan.channel, _log)
				for k, v in kw.items():
					if k not in ('_log'):
						if chan.__dict__.has_key(k):
							chan.__dict__[k] = v
# 	Wlads не обновляем если значение = пустое
#							if v != '':
#								chan.__dict__[k] = v
						else:
							log.warning("Server %s :: Channel %s (%s) does not have attribute %s", servername, uniqueid, chan.channel, k)
				self.http._addUpdate(servername = servername, subaction = 'Update', **chan.__dict__.copy())
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", chan)
			else:
				log.warning("Server %s :: Channel not found: %s (%s) %s", servername, uniqueid, channel, _log)
		except:
			log.exception("Server %s :: Unhandled exception updating channel: %s (%s)", servername, uniqueid, channel)
			
	def _removeChannel(self, servername, **kw):
		uniqueid = kw.get('uniqueid')
		channel  = kw.get('channel')
		_log     = kw.get('_log', '')
		try:
			server = self.servers.get(servername)
			chan   = server.status.channels.get(uniqueid)
			if chan:
				log.debug("Server %s :: Channel remove: %s (%s) %s", servername, uniqueid, chan.channel, _log)
				if kw.get('_isLostChannel'):
					log.warning("Server %s :: Removing lost channel: %s (%s)", servername, uniqueid, chan.channel)
				else:
					bridgekey = self._locateBridge(servername, uniqueid = uniqueid)
					if bridgekey:
						self._removeBridge(servername, uniqueid = bridgekey[0], bridgeduniqueid = bridgekey[1], _log = _log)
				del server.status.channels[uniqueid]
				self.http._addUpdate(servername = servername, action = 'RemoveChannel', uniqueid = uniqueid)
				
				channeltype, peername = channel.rsplit('-', 1)[0].split('/', 1)
				self._updatePeer(servername, channeltype = channeltype, peername = peername, _action = 'decreaseCallCounter')
				
				##	DAHDI - положили трубку ищем имя, обнуляем счетчик
				if channeltype == 'DAHDI':
					for channeltype, peers in server.status.peers.items():
						for peername, peer in peers.items():
							if (peer.uniqueid):
								if uniqueid == peer.uniqueid:
									self._updatePeer(servername, channeltype = channeltype, peername = peername, _action = 'decreaseDahdiCallCounter')

				
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", chan)
			else:
				log.warning("Server %s :: Channel does not exists: %s (%s)", servername, uniqueid, channel)
		except:
			log.exception("Server %s :: Unhandled exception removing channel: %s (%s)", servername, uniqueid, channel)
	
	## Bridges
	def _createBridge(self, servername, **kw):
		server          = self.servers.get(servername)
		uniqueid        = kw.get('uniqueid')
		channel         = kw.get('channel')
		bridgeduniqueid = kw.get('bridgeduniqueid')
		linkedid        = kw.get('linkedid', '')
		bridgedchannel  = kw.get('bridgedchannel')
		bridgekey       = (uniqueid, bridgeduniqueid) 
		_log            = kw.get('_log', '')
		
		if not server.status.bridges.has_key(bridgekey):
			if not server.status.channels.has_key(uniqueid):
				log.warning("Server %s :: Could not create bridge %s (%s) with %s (%s). Source Channel not found.", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel)
				return False
# Wlad
#			if not server.status.channels.has_key(bridgeduniqueid):
#				##	bridge PJSIP
#				if server.version < 12: 
#					log.warning("Server %s :: Could not create bridge %s (%s) with %s (%s). Bridged Channel not found.", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel)
#				return False
				
			bridge			       = GenericObject("Bridge")
			bridge.uniqueid        = uniqueid
			bridge.bridgeduniqueid = bridgeduniqueid
			bridge.linkedid        = linkedid
			bridge.channel         = channel
			bridge.bridgedchannel  = bridgedchannel
			bridge.status          = kw.get('status', 'Link')
			bridge.dialtime        = kw.get('dialtime', time.time())
			bridge.linktime        = kw.get('linktime', 0)
			bridge.seconds         = int(time.time() - bridge.linktime)
			
			log.debug("Server %s :: Bridge create: %s (%s) with %s (%s) %s", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel, _log)
			server.status.bridges[bridgekey] = bridge
			self.http._addUpdate(servername = servername, **bridge.__dict__.copy())
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", bridge)
			return True
		else:
			log.warning("Server %s :: Bridge already exists: %s (%s) with %s (%s)", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel)
		return False
	
	def _updateBridge(self, servername, **kw):
		uniqueid        = kw.get('uniqueid')
		channel         = kw.get('channel')
		bridgeduniqueid = kw.get('bridgeduniqueid')
		bridgedchannel  = kw.get('bridgedchannel')
		_log            = kw.get('_log', '')
		try:
			bridge = kw.get('_bridge', self.servers.get(servername).status.bridges.get((uniqueid, bridgeduniqueid)))
			if bridge:
				log.debug("Server %s :: Bridge update: %s (%s) with %s (%s) %s", servername, bridge.uniqueid, bridge.channel, bridge.bridgeduniqueid, bridge.bridgedchannel, _log)
				for k, v in kw.items():
					if k not in ('_log', '_bridge'):
						if bridge.__dict__.has_key(k):
							bridge.__dict__[k] = v
						else:
							log.warning("Server %s :: Bridge %s (%s) with %s (%s) does not have attribute %s", servername, uniqueid, bridge.channel, bridgeduniqueid, bridge.bridgedchannel, k)
				bridge.seconds = int(time.time() - bridge.linktime)
				self.http._addUpdate(servername = servername, subaction = 'Update', **bridge.__dict__.copy())
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", bridge)
			else:
				log.warning("Server %s :: Bridge not found: %s (%s) with %s (%s)", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel)
		except:
			log.exception("Server %s :: Unhandled exception updating bridge: %s (%s) with %s (%s)", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel)
	
	def _locateBridge(self, servername, **kw):
		server          = self.servers.get(servername)
		uniqueid        = kw.get('uniqueid')
		bridgeduniqueid = kw.get('bridgeduniqueid')
		
		if uniqueid and bridgeduniqueid:
			return [None, (uniqueid, bridgeduniqueid)][server.status.bridges.has_key((uniqueid, bridgeduniqueid))]
		
		bridges = [i for i in server.status.bridges.keys() if uniqueid in i or bridgeduniqueid in i]
		if len(bridges) == 1:
			return bridges[0]
		if len(bridges) > 1:
		##	bridge PJSIP
			if server.version < 12:
				log.warning("Server %s :: Found more than one bridge with same uniqueid: %s", servername, bridges)
			return None
	
	def _removeBridge(self, servername, **kw):
		uniqueid        = kw.get('uniqueid')
		channel         = kw.get('channel')
		bridgeduniqueid = kw.get('bridgeduniqueid')
		bridgedchannel  = kw.get('bridgedchannel')
		bridgekey       = (uniqueid, bridgeduniqueid)
		_log            = kw.get('_log', '')
		try:
			server = self.servers.get(servername)
			bridge = server.status.bridges.get(bridgekey)
			if bridge:
				log.debug("Server %s :: Bridge remove: %s (%s) with %s (%s) %s", servername, uniqueid, bridge.channel, bridge.bridgeduniqueid, bridge.bridgedchannel, _log)
				if kw.get('_isLostBridge'):
					if server.version < 12:
						log.warning("Server %s :: Removing lost bridge: %s (%s) with %s (%s)", servername, uniqueid, bridge.channel, bridge.bridgeduniqueid, bridge.bridgedchannel)
				del server.status.bridges[bridgekey]
				self.http._addUpdate(servername = servername, action = 'RemoveBridge', uniqueid = uniqueid, bridgeduniqueid = bridgeduniqueid)
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", bridge)
			else:
				log.warning("Server %s :: Bridge does not exists: %s (%s) with %s (%s)", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel)
		except:
			log.exception("Server %s :: Unhandled exception removing bridge: %s (%s) with %s (%s)", servername, uniqueid, channel, bridgeduniqueid, bridgedchannel)
			
	## Meetme
	def _createMeetme(self, servername, **kw):
		server     = self.servers.get(servername)
		meetmeroom = kw.get('meetme')
		dynamic    = kw.get("dynamic", False)
		forced     = kw.get("forced", False)
		_log       = kw.get('_log')
		meetme     = server.status.meetmes.get(meetmeroom)
		
		if not meetme:
			meetme = GenericObject("Meetme")
			meetme.meetme  = meetmeroom
			meetme.dynamic = dynamic
			meetme.forced  = forced
			meetme.users   = {}
			
			log.debug("Server %s :: Meetme create: %s %s", servername, meetme.meetme, _log)
			server.status.meetmes[meetmeroom] = meetme
			if dynamic:
				self.http._addUpdate(servername = servername, **meetme.__dict__.copy())
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", meetme)
		else:
			log.warning("Server %s :: Meetme already exists: %s", servername, meetme.meetme)
			
		return meetme
			
	def _updateMeetme(self, servername, **kw):
		meetmeroom = kw.get("meetme")
		_log       = kw.get('_log', '')
		try:
			meetme = self.servers.get(servername).status.meetmes.get(meetmeroom)
			if not meetme:
				meetme = self._createMeetme(servername, meetme = meetmeroom, dynamic = True, _log = "(dynamic)")
			
			user = kw.get('addUser')
			if user:
				meetme.users[user.get('usernum')] = user
				log.debug("Server %s :: Added user %s to Meetme %s %s", servername, user.get('usernum'), meetme.meetme, _log)
				
			user = kw.get('removeUser')
			if user:
				u = meetme.users.get(user.get('usernum'))
				if u:
					log.debug("Server %s :: Removed user %s from Meetme %s %s", servername, u.get('usernum'), meetme.meetme, _log)
					del meetme.users[u.get('usernum')]
					
			self.http._addUpdate(servername = servername, **meetme.__dict__.copy())
					
			if meetme.dynamic and len(meetme.users) == 0:
				self._removeMeetme(servername, meetme = meetme.meetme, _log = "(dynamic)")
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", meetme)
		except:
			log.exception("Server %s :: Unhandled exception updating meetme: %s", servername, meetmeroom)
			
	def _removeMeetme(self, servername, **kw):
		meetmeroom = kw.get("meetme")
		_log       = kw.get('_log', '')
		try:
			server = self.servers.get(servername)
			meetme = server.status.meetmes.get(meetmeroom)
			if meetme:
				log.debug("Server %s :: Meetme remove: %s %s", servername, meetme.meetme, _log)
				del server.status.meetmes[meetme.meetme]
				self.http._addUpdate(servername = servername, action = 'RemoveMeetme', meetme = meetme.meetme)
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", meetme)
			else:
				log.warning("Server %s :: Meetme does not exists: %s", servername, meetmeroom)
		except:
			log.exception("Server %s :: Unhandled exception removing meetme: %s", servername, meetmeroom)
	
	## Parked Calls
	def _createParkedCall(self, servername, **kw):
		server     = self.servers.get(servername)
		channel    = kw.get('channel')
		parked     = server.status.parkedCalls.get(channel)
		_log       = kw.get('_log', '')
		
		if not parked:
			parked = GenericObject('ParkedCall')
			parked.channel      = channel
			parked.parkedFrom   = kw.get('from')
			parked.calleridname = kw.get('calleridname')
			parked.calleridnum  = kw.get('calleridnum')
			parked.exten        = kw.get('exten')
			parked.timeout      = int(kw.get('timeout'))
			
			# locate "from" channel
			fromChannel = None
			for uniqueid, fromChannel in server.status.channels.items():
				if parked.parkedFrom == fromChannel.channel:
					parked.calleridnameFrom = fromChannel.calleridname
					parked.calleridnumFrom = fromChannel.calleridnum
					break
			
			log.debug("Server %s :: ParkedCall create: %s at %s %s", servername, parked.channel, parked.exten, _log)
			server.status.parkedCalls[channel] = parked
			self.http._addUpdate(servername = servername, **parked.__dict__.copy())
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", parked)
		else:
			if not self.isParkedCallStatus:
				log.warning("Server %s :: ParkedCall already exists: %s at %s", servername, parked.channel, parked.exten)
				
	def _removeParkedCall(self, servername, **kw):
		channel    = kw.get('channel')
		_log       = kw.get('_log', '')
		
		try:
			server = self.servers.get(servername)
			parked = server.status.parkedCalls.get(channel)
			if parked:
				log.debug("Server %s :: ParkedCall remove: %s at %s %s", servername, parked.channel, parked.exten, _log)
				del server.status.parkedCalls[parked.channel]
				self.http._addUpdate(servername = servername, action = 'RemoveParkedCall', channel = parked.channel)
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", parked)
			else:
				log.warning("Server %s :: ParkedCall does not exists: %s", servername, channel)
		except:
			log.exception("Server %s :: Unhandled exception removing ParkedCall: %s", servername, channel)
	
	## Queues
	def _createQueue(self, servername, **kw):
		server    = self.servers.get(servername)
		queuename = kw.get('queue')
		_log      = kw.get('_log', '')
		
		queue     = server.status.queues.get(queuename)
		
		if not queue:
			queue                  = GenericObject("Queue")
			queue.queue            = queuename
			queue.mapname          = kw.get('mapname')
			queue.calls            = int(kw.get('calls', 0))
			queue.completed        = int(kw.get('completed', 0))
			queue.abandoned        = int(kw.get('abandoned', 0))
			queue.holdtime         = kw.get('holdtime', 0)
			queue.max              = kw.get('max', 0)
			queue.servicelevel     = kw.get('servicelevel', 0)
			queue.servicelevelperf = kw.get('servicelevelperf', 0)
			queue.weight           = kw.get('weight', 0)
			queue.strategy         = kw.get('strategy')
			queue.talktime         = kw.get('talktime', 0)
			
			log.debug("Server %s :: Queue create: %s %s", servername, queue.queue, _log)
			server.status.queues[queuename] = queue
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", queue)
		else:
			log.warning("Server %s :: Queue already exists: %s", servername, queue.queue)
			
		return queue
	
	def _updateQueue(self, servername, **kw):	
		server    = self.servers.get(servername)
		queuename = kw.get('queue')
		event     = kw.get('event')
		_log      = kw.get('_log', '')
		
		try:
			queue = server.status.queues.get(queuename)
			if queue:
				if event == "QueueParams":
					log.debug("Server %s :: Queue update: %s %s", servername, queuename, _log)
					queue.calls            = int(kw.get('calls', 0))
					queue.completed        = int(kw.get('completed', 0))
					queue.abandoned        = int(kw.get('abandoned', 0))
					queue.holdtime         = kw.get('holdtime', 0)
					queue.max              = kw.get('max', 0)
					queue.servicelevel     = kw.get('servicelevel', 0)
					queue.servicelevelperf = kw.get('servicelevelperf', 0)
					queue.weight           = kw.get('weight', 0)
					queue.talktime         = kw.get('talktime', 0)
					self.http._addUpdate(servername = servername, subaction = 'Update', **queue.__dict__.copy())
					if logging.DUMPOBJECTS:
						log.debug("Object Dump:%s", queue)
					return
				
				if event in ("QueueMember", "QueueMemberAdded", "QueueMemberStatus", "QueueMemberPaused", "QueueMemberPause"):
#					log.debug("Server %s :: Processing Event _updateQueue QueueMember [%s]" % (servername, event))

					location   = kw.get('location', kw.get('interface'))
					membername = kw.get('name', kw.get('membername'))
					if server.queueMapMember.has_key(location):
						membername = server.queueMapMember[location]
						
					memberid = (queuename, location)
					member   = server.status.queueMembers.get(memberid)

#					log.debug("Object Dump member:%s", member)

					tech, num = location.rsplit('@', 1)[0].split('/', 1)
					if tech == 'Local':
						if "/" in membername:
							membername = membername.split('/', 1)[1]
# --
							membername = membername.split('@', 1)[0] + ' '
						else:
							membername = membername.split('@', 1)[0] + ' <' + num + '> '
# --<номер внутри>
#						membername = membername.split('@', 1)[0] + ' <' + num + '> '

					if "@" in location:
						membername = membername + location.split('@', 1)[1].replace('/n', '')
						
					if not member:
						member            = GenericObject("QueueMember")
						member.location   = location
						member.name       = membername
						member.queue      = kw.get('queue')
						member.callstaken = kw.get('callstaken', 0)
						member.lastcall   = kw.get('lastcall', 0)
						member.membership = kw.get('membership')
						member.paused     = kw.get('paused')
						member.pausedat   = [0, time.time()][member.paused == '1']
						member.pausedur   = int(time.time() - member.pausedat)
						member.penalty    = kw.get('penalty')
						member.status     = kw.get('status')
						member.statustext = AST_DEVICE_STATES.get(member.status, 'Unknown')
						self.http._addUpdate(servername = servername, **member.__dict__.copy())
					else:
						log.debug("Server %s :: Queue update, member updated: %s -> %s %s", servername, queuename, location, _log)
						member.name       = membername
						member.queue      = kw.get('queue')
						member.callstaken = kw.get('callstaken', 0)
						member.lastcall   = kw.get('lastcall', 0)
						member.membership = kw.get('membership')
						member.paused     = kw.get('paused')
						member.pausedat   = [member.pausedat, time.time()][(event == "QueueMemberPaused" or event == "QueueMemberPause") and member.paused == '1']
						member.pausedur   = int(time.time() - member.pausedat)
						member.penalty    = kw.get('penalty')
						member.status     = kw.get('status')
						member.statustext = AST_DEVICE_STATES.get(member.status, 'Unknown')
						self.http._addUpdate(servername = servername, subaction = 'Update', **member.__dict__.copy())
					server.status.queueMembers[memberid] = member
					if logging.DUMPOBJECTS:
						log.debug("Object Dump:%s", member)
					return
				
				if event == "QueueMemberRemoved":
					location = kw.get('location', kw.get('interface'))
					memberid = (queuename, location)
					member   = server.status.queueMembers.get(memberid)
					if member:
						log.debug("Server %s :: Queue update, member removed: %s -> %s %s", servername, queuename, location, _log)
						del server.status.queueMembers[memberid]
						self.http._addUpdate(servername = servername, action = 'RemoveQueueMember', location = member.location, queue = member.queue)
						if logging.DUMPOBJECTS:
							log.debug("Object Dump:%s", member)
					else:
						log.warning("Server %s :: Queue Member does not exists: %s -> %s", servername, queuename, location)
					return
				
#				if event in ("QueueEntry", "Join"):
				if event in ("QueueEntry", "Join", "QueueCallerJoin"):
					uniqueid = kw.get('uniqueid', None)
					if not uniqueid:
						# try to found uniqueid based on channel name
						channel  = kw.get('channel')
						for uniqueid, chan in server.status.channels.items():
							if channel == chan:
								break
					clientid = (queuename, uniqueid) 
					client   = server.status.queueClients.get(clientid)
					if not client:
						log.debug("Server %s :: Queue update, client added: %s -> %s %s", servername, queuename, uniqueid, _log)
						client              = GenericObject("QueueClient")
						client.uniqueid     = uniqueid
						client.channel      = kw.get('channel')
						client.queue        = kw.get('queue')
						client.calleridname = kw.get('calleridname')
						client.calleridnum  = kw.get('calleridnum')
						client.position     = kw.get('position')
						client.abandonned   = False
						client.jointime     = time.time() - int(kw.get('wait', 0))
						client.seconds      = int(time.time() - client.jointime)
						self.http._addUpdate(servername = servername, **client.__dict__.copy())
					else:
						log.debug("Server %s :: Queue update, client updates: %s -> %s %s", servername, queuename, uniqueid, _log)
						client.channel      = kw.get('channel')
						client.queue        = kw.get('queue')
						client.calleridname = kw.get('calleridname')
						client.calleridnum  = kw.get('calleridnum')
						client.position     = kw.get('position')
						client.seconds      = int(time.time() - client.jointime)
						self.http._addUpdate(servername = servername, subaction = 'Update', **client.__dict__.copy())
					server.status.queueClients[clientid] = client
					if event == "Join":
						queue.calls += 1
						self.http._addUpdate(servername = servername, subaction = 'Update', **queue.__dict__.copy())
					if logging.DUMPOBJECTS:
						log.debug("Object Dump:%s", client)
					return
				
				if event == "QueueCallerAbandon":
					uniqueid = kw.get('uniqueid', None)
					if not uniqueid:
						# try to found uniqueid based on channel name
						channel  = kw.get('channel')
						for uniqueid, chan in server.status.channels.items():
							if channel == chan:
								break
					clientid = (queuename, uniqueid) 
					client   = server.status.queueClients.get(clientid)
					if client:
						log.debug("Server %s :: Queue update, client marked as abandonned: %s -> %s %s", servername, queuename, uniqueid, _log)
						client.abandonned = True
						queue.abandoned  += 1
						self.http._addUpdate(servername = servername, subaction = 'Update', **queue.__dict__.copy())
					else:
						log.warning("Server %s :: Queue Client does not exists: %s -> %s", servername, queuename, uniqueid)
					return
				
#				if event == "Leave":
				if event in ("Leave", "QueueCallerLeave"):
					uniqueid = kw.get('uniqueid', None)
					if not uniqueid:
						# try to found uniqueid based on channel name
						channel = kw.get('channel')
						for uniqueid, chan in server.status.channels.items():
							if channel == chan:
								break
					clientid = (queuename, uniqueid) 
					client   = server.status.queueClients.get(clientid)
					if client:
						queue.calls -= 1
						self.http._addUpdate(servername = servername, subaction = 'Update', **queue.__dict__.copy())
						if not client.abandonned:
							call           = GenericObject("QueueCall")
							call.client    = client.__dict__
							call.member    = None
							call.link      = False
							call.starttime = time.time()
							call.seconds   = int(time.time() - call.starttime)
							server.status.queueCalls[client.uniqueid] = call
						
						log.debug("Server %s :: Queue update, client removed: %s -> %s %s", servername, queuename, uniqueid, _log)
						del server.status.queueClients[clientid]
						self.http._addUpdate(servername = servername, action = 'RemoveQueueClient', uniqueid = client.uniqueid, queue = client.queue)
						if logging.DUMPOBJECTS:
							log.debug("Object Dump:%s", client)
					else:
						log.warning("Server %s :: Queue Client does not exists: %s -> %s", servername, queuename, uniqueid)
					return
				
			else:
				if (self.displayQueuesDefault and not server.displayQueues.has_key(queuename)) or (not self.displayQueuesDefault and server.displayQueues.has_key(queuename)):
					log.warning("Server %s :: Queue not found: %s", servername, queuename)
		except:
			log.exception("Server %s :: Unhandled exception updating queue: %s", servername, queuename)
			
	##
	## Parse monast.conf
	##	
	def __parseMonastConfig(self):
		log.log(logging.NOTICE, 'Parsing config file %s' % self.configFile)
		
		config = MyConfigParser()
		config.read(self.configFile)
		
		self.authRequired = config.get('global', 'auth_required') == 'true'
		self.scriptpath = config.get('global', 'script_path') 
		self.donglestatpath = config.get('global', 'dongle_stat_path')
##		log.log(logging.WARNING, 'Parsing config file script_path [%s] dongle_stat_path [%s]' %(self.scriptpath, self.donglestatpath))
		
		## HTTP Server
		self.bindHost    = config.get('global', 'bind_host')
		self.bindPort    = int(config.get('global', 'bind_port'))
		self.http        = MonastHTTP(self.bindHost, self.bindPort)
		self.http.monast = self
		self.site        = TWebServer.Site(self.http)
		reactor.listenTCP(self.bindPort, self.site, 50, self.bindHost)
		
		## Reading servers sections
		servers = [s for s in config.sections() if s.startswith('server:')]
		servers.sort()
		
		for server in servers:
			servername = server.replace('server:', '').strip()
			username   = config.get(server, 'username')
			password   = config.get(server, 'password')
			
			self.servers[servername]                  = ServerObject()
			self.servers[servername].servername       = servername
			self.servers[servername].version          = None
			self.servers[servername].lastReload       = 0
			self.servers[servername].hostname         = config.get(server, 'hostname')
			self.servers[servername].hostport         = int(config.get(server, 'hostport'))
			self.servers[servername].username         = config.get(server, 'username')
			self.servers[servername].password         = config.get(server, 'password')
			self.servers[servername].default_context  = config.get(server, 'default_context')
			self.servers[servername].transfer_context = config.get(server, 'transfer_context')
			self.servers[servername].meetme_context   = config.get(server, 'meetme_context')
			self.servers[servername].meetme_prefix    = config.get(server, 'meetme_prefix')
			
			self.servers[servername].connected        = False
			self.servers[servername].factory          = MonastAMIFactory(servername, username, password, self)
			self.servers[servername].ami              = None
			self.servers[servername].taskCheckStatus  = task.LoopingCall(self.taskCheckStatus, servername)
			
			self.servers[servername].status              = GenericObject()
			self.servers[servername].status.meetmes      = {}
			self.servers[servername].status.channels     = {}
			self.servers[servername].status.bridges      = {}
			self.servers[servername].status.peers        = {
				'SIP': {},
				'PJSIP': {},
				'IAX2': {},
				'DAHDI': {},
				'Dongle': {},
				'Khomp': {},
			}
			self.servers[servername].peergroups          = {}
			self.servers[servername].displayUsers        = {}
			self.servers[servername].displayMeetmes      = {}
			self.servers[servername].displayQueues       = {}
			self.servers[servername].status.queues       = {}
			self.servers[servername].status.queueMembers = {}
			self.servers[servername].status.queueClients = {}
			self.servers[servername].status.queueCalls   = {}
			self.servers[servername].status.parkedCalls  = {}
			
			self.servers[servername].queueMapName        = {}
			self.servers[servername].queueMapMember      = {}
		
		## Peers Groups
		for peergroup, peers in config.items('peers'):
			if peergroup in ('default', 'sortby'):
				continue
			
			if re.match("^[^\/]+\/@group\/[^\/]+", peergroup):
				servername, peergroup = peergroup.replace('@group/', '').split('/', 1)
				server = self.servers.get(servername)
				if server:
					peergroup = peergroup.strip()
					peers     = peers.split(',')
					for peer in peers:
						tech, peer = peer.split('/', 1)
						tech = tech.strip()
						peer = peer.strip()
						if not server.peergroups.has_key(tech):
							server.peergroups[tech] = {}
						server.peergroups[tech][peer] = peergroup
		
		## Peers
		self.displayUsersDefault = config.get('peers', 'default') == 'show'
		try:
			self.sortPeersBy = config.get('peers', 'sortby')
			if not self.sortPeersBy in ('channel', 'callerid'):
				log.error("Invalid value for 'sortby' in section 'peers' of config file. valid options: channel, callerid")
				self.sortPeersBy = 'callerid'
		except NoOptionError:
			self.sortPeersBy = 'callerid'
			log.error("No option 'sortby' in section: 'peers' of config file, sorting by CallerID")
		
		for user, display in config.items('peers'):
			if user in ('default', 'sortby'):
				continue
			
			if not re.match("^[^\/]+\/[^\/@]+\/[^\/]+", user):
				continue
			
			servername, user = user.split('/', 1)
			server = self.servers.get(servername)
			if not server:
				continue
			
			tech, peer = user.split('/')
			
			if tech in server.status.peers.keys(): 
				if (self.displayUsersDefault and display == 'hide') or (not self.displayUsersDefault and display == 'show'):
					server.displayUsers[user] = True
					
			if display.startswith('force'):
				tmp       = display.split(',')
				display   = tmp[0].strip()
				status    = '--'
				callerid  = '--'
				forcedCid = False
				if len(tmp) == 2:
					callerid  = tmp[1].strip()
					forcedCid = True
				
				self._createPeer(
					servername, 
					channeltype = tech, 
					peername    = peer,
					callerid    = callerid,
					status      = status,
					forced      = True,
					forcedCid   = forcedCid,
					_log        = '(forced peer)'
				)
		
		## Meetmes / Conferences
		self.displayMeetmesDefault = config.get('meetmes', 'default') == 'show'
		for meetme, display in config.items('meetmes'):
			if meetme in ('default'):
				continue
			
			servername, meetme = meetme.split('/', 1)
			server = self.servers.get(servername)
			if not server:
				continue
			
			if (self.displayMeetmesDefault and display == "hide") or (not self.displayMeetmesDefault and display == "show"):
				server.displayMeetmes[meetme] = True
				
			if display == "force":
				self._createMeetme(servername, meetme = meetme, forced = True, _log = "By monast config")
					
		## Queues
		self.displayQueuesDefault = config.get('queues', 'default') == 'show'
			
		for queue, display in config.items('queues'):
			if queue in ('default'):
				continue
			
			servername, queue = queue.split('/', 1)
			server = self.servers.get(servername)
			if not server:
				continue
			
			if "@member" in queue:
				peer = queue.replace("@member/", "").strip()
				self.servers[servername].queueMapMember[peer] = display
				continue
			
			mapName = None
			if display.count(",") == 1:
				display, mapName = [i.strip() for i in display.split(",", 1)]
				server.queueMapName[queue] = mapName
			
			if (self.displayQueuesDefault and display == 'hide') or (not self.displayQueuesDefault and display == 'show'):
				server.displayQueues[queue] = True
		
		## User Roles
		self.authUsers = {}
		users = [s for s in config.sections() if s.startswith('user:')]
		for user in users:
			username = user.replace('user:', '').strip()
			try:
				montasUser          = GenericObject("Monast User")
				montasUser.username = username 
				montasUser.secret   = config.get(user, 'secret')
				montasUser.servers  = {}
				
				roles   = [i.strip() for i in config.get(user, 'roles').split(',')]
				servers = [i.strip() for i in config.get(user, 'servers').split(',')]
				
				if config.get(user, 'servers').upper() == 'ALL':
					servers = self.servers.keys()
				
				for server in servers:
					if self.servers.has_key(server):
						try:
							serverRoles = [i.strip() for i in config.get(user, server).split(',')]
							montasUser.servers[server] = serverRoles
						except:
							montasUser.servers[server] = roles
				
				if len(montasUser.servers) == 0:
					log.error("Username %s has errors in config file!" % username)
					continue
				
				self.authUsers[username] = montasUser
			except:
				log.error("Username %s has errors in config file!" % username)
			
		## Start all server factory
		self.__start()
	
	##
	## Request Asterisk Configuration
	##
	def _onAmiCommandFailure(self, reason, servername, message = None):
		if not message:
			message = "AMI Action Error"
		
		errorMessage = reason.getErrorMessage()
		if type(reason.value) == AMICommandFailure and type(reason.value.args[0]) == type(dict()) and reason.value.args[0].has_key('message'):
			errorMessage = reason.value.args[0].get('message')
		
		log.error("Server %s :: %s, reason: %s" % (servername, message, errorMessage))

	## поиск новых пиров Asterisk 
	def _requestAsteriskPeers(self, servername, channeltype):
		server      = self.servers.get(servername)

		if channeltype == 'SIP' or channeltype == 'ALL':
			## Peers (SIP, IAX) :: Process results via handlerEventPeerEntry
			log.debug("Server %s :: Requesting SIP Peers..." % servername)
			server.pushTask(server.ami.sendDeferred, {'action': 'sippeers'}) \
				.addCallback(server.ami.errorUnlessResponse) \
				.addErrback(self._onAmiCommandFailure, servername, "Error Requesting SIP Peers")

		if channeltype == 'PJSIP' or channeltype == 'ALL':
			## Peers PJSIP :: Process results via handlerEventEndpointList  - PJSIPShowEndpoints pjsipshowendpoints
			log.debug("Server %s :: Requesting PJSIP Peers..." % servername)
			server.pushTask(server.ami.sendDeferred, {'action': 'pjsipshowendpoints'}) \
				.addCallback(server.ami.errorUnlessResponse) \
				.addErrback(self._onAmiCommandFailure, servername, "Error Requesting PJSIP Peers")

		if channeltype == 'Dongle' or channeltype == 'ALL':
			## DONGLE ищем активные донглы
			def onDongleShowDevices(result):
				if len(result) > 2:
					if result[0].split()[4] == 'RSSI':
						rssi = 4 # для моего форка
					else:
						rssi = 3 # для стандарного chan_dongle
					for line in result[1:]:
						peername = line.split(' ', 1)[0].split('/', 1)[0]
						setstatus = line.split()[2]
			
						level = line.split()[rssi] # Получили уровень
						if level == '>=':   ## >= -51 dBm
							level = line.split()[rssi+1]
						if level == '<=':   ## <= -113 dBm
							level = line.split()[rssi+1]
						if level == 'unknown':   ## 'unknown or unmeasurable' - Неизвестный или неизмеримый
							level = "-120"
				 		
##					log.warning("Server %s :: DongleSearch [%s], Status = [%s], Level = [%s] some AMI events...", servername, peername, setstatus, level)
						self.handlerEventPeerEntry(server.ami, {'channeltype': 'Dongle', 'objectname': peername, 'status': setstatus, 'level': level})
    	
			log.debug("Server %s :: Requesting Dongle devices (via dongle show devices)..." % servername)
			server.pushTask(server.ami.command, 'dongle show devices') \
				.addCallbacks(onDongleShowDevices, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting Dongle devices (via dongle show devices)"))

		if channeltype == 'IAX2' or channeltype == 'IAX' or channeltype == 'ALL':
			## Peers IAX different behavior in asterisk 1.4
			if server.version == 1.4:
				log.log(logging.NOTICE, "Server %s :: Asterisk server.version >= 1.4 [%s]" % (servername, server.version))
				def onIax2ShowPeers(result):
					if len(result) > 2:
						for line in result[1:][:-1]:
							peername = line.split(' ', 1)[0].split('/', 1)[0]
							self.handlerEventPeerEntry(server.ami, {'channeltype': 'IAX2', 'objectname': peername, 'status': 'Unknown'})
				log.debug("Server %s :: Requesting IAX Peers (via iax2 show peers)..." % servername)
				server.pushTask(server.ami.command, 'iax2 show peers') \
					.addCallbacks(onIax2ShowPeers, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting IAX Peers (via iax2 show peers)"))
			else:		
				log.debug("Server %s :: Requesting IAX Peers..." % servername)
				server.pushTask(server.ami.sendDeferred, {'action': 'iaxpeers'}) \
					.addCallback(server.ami.errorUnlessResponse) \
					.addErrback(self._onAmiCommandFailure, servername, "Error Requesting IAX Peers")


	def _requestAsteriskConfig(self, servername):
		log.info("Server %s :: Requesting Asterisk Configuration..." % servername)

		server = self.servers.get(servername)
		log.warning("Server %s :: Requesting Asterisk Configuration..." % servername)
#		log.log(logging.NOTICE, "Server %s :: Requesting Asterisk Configuration..." % servername)
		
		## Request Browser Reload
		self.http._addUpdate(servername = servername, action = "Reload", time = 5000)
		
		## Clear Server Status
		toRemove = []
		for meetmeroom, meetme in server.status.meetmes.items():
			if not meetme.forced:
				toRemove.append(meetmeroom)
		for meetmeroom in toRemove:
			del server.status.meetmes[meetmeroom]
		
		server.status.channels.clear()
		server.status.bridges.clear()
		server.status.queues.clear()
		server.status.queueMembers.clear()
		server.status.queueClients.clear()
		server.status.queueCalls.clear()
		server.status.parkedCalls.clear()
		for channeltype, peers in server.status.peers.items():
			toRemove = []
			for peername, peer in peers.items():
				if not peer.forced:
					toRemove.append(peername)
			for peername in toRemove:
				del peers[peername]
		
		## Peers (SIP, IAX) :: Process results via handlerEventPeerEntry
		log.debug("Server %s :: Requesting SIP Peers..." % servername)
		server.pushTask(server.ami.sendDeferred, {'action': 'sippeers'}) \
			.addCallback(server.ami.errorUnlessResponse) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Requesting SIP Peers")

		if server.version > 11:
			## Peers PJSIP :: Process results via handlerEventEndpointList  - PJSIPShowEndpoints pjsipshowendpoints
			log.debug("Server %s :: Requesting PJSIP Peers..." % servername)
			server.pushTask(server.ami.sendDeferred, {'action': 'pjsipshowendpoints'}) \
				.addCallback(server.ami.errorUnlessResponse) \
				.addErrback(self._onAmiCommandFailure, servername, "Error Requesting PJSIP Peers")

#	standart chan_dongle
# ID           Group State      RSSI        Mode Submode Provider Name  Model      Firmware          IMEI             IMSI             Number
# ============================================================================================================================================
# kivko wlad chan_dongle
# ID           Group State      SNR RSSI    Mode Submode Provider Name  Model      Firmware          IMEI             IMSI             Number        
# dn1          92    Free       15  -83 dBm 5    4       MTS-RUS        E173       11.126.15.00.209  867455003761242  250013902961412  Unknown
# ============================================================================================================================================
		## DONGLE ищем активные донглы
		def onDongleShowDevices(result):
			if len(result) > 2:
				if result[0].split()[4] == 'RSSI':
					rssi = 4 # ny forks
				else:
					rssi = 3 # standart chan_dongle
				for line in result[1:]:
					peername = line.split(' ', 1)[0].split('/', 1)[0]
					setstatus = line.split()[2]
		## надо переделать
		##			setstatus = line[19:29]							
		##			log.warning("Server %s :: DongleSearch [%s], Status = [%s], some AMI events...", servername, peername, setstatus)
		##			self.handlerEventPeerEntry(server.ami, {'channeltype': 'Dongle', 'objectname': peername, 'status': setstatus})
		
					level = line.split()[rssi] # Получили уровень
					if level == '>=':   ## >= -51 dBm
						level = line.split()[rssi+1]
					if level == '<=':   ## <= -113 dBm
						level = line.split()[rssi+1]
					if level == 'unknown':   ## 'unknown or unmeasurable' - Неизвестный или неизмеримый
						level = "-120"
			 		
##					log.warning("Server %s :: DongleSearch [%s], Status = [%s], Level = [%s], some AMI events...", servername, peername, setstatus, level)
					self.handlerEventPeerEntry(server.ami, {'channeltype': 'Dongle', 'objectname': peername, 'status': setstatus, 'level': level})

		log.debug("Server %s :: Requesting Dongle devices (via dongle show devices)..." % servername)
		server.pushTask(server.ami.command, 'dongle show devices') \
			.addCallbacks(onDongleShowDevices, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting Dongle devices (via dongle show devices)"))

		## Peers IAX different behavior in asterisk 1.4
		if server.version == 1.4:
			def onIax2ShowPeers(result):
				if len(result) > 2:
					for line in result[1:][:-1]:
						peername = line.split(' ', 1)[0].split('/', 1)[0]
						self.handlerEventPeerEntry(server.ami, {'channeltype': 'IAX2', 'objectname': peername, 'status': 'Unknown'})
			log.debug("Server %s :: Requesting IAX Peers (via iax2 show peers)..." % servername)
			server.pushTask(server.ami.command, 'iax2 show peers') \
				.addCallbacks(onIax2ShowPeers, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting IAX Peers (via iax2 show peers)"))
		else:		
			log.debug("Server %s :: Requesting IAX Peers..." % servername)
			server.pushTask(server.ami.sendDeferred, {'action': 'iaxpeers'}) \
				.addCallback(server.ami.errorUnlessResponse) \
				.addErrback(self._onAmiCommandFailure, servername, "Error Requesting IAX Peers")
		
		# DAHDI
		def onDahdiShowChannels(events):
			log.debug("Server %s :: Processing DAHDI Channels..." % servername)
			for event in events:
				user = "DAHDI/%s" % event.get('dahdichannel')
				if (self.displayUsersDefault and not server.displayUsers.has_key(user)) or (not self.displayUsersDefault and server.displayUsers.has_key(user)):
					self._createPeer(
						servername,
						channeltype = 'DAHDI',
						peername    = event.get('dahdichannel', event.get('channel')),
						context     = event.get('context'),
						alarm       = event.get('alarm'),
						signalling  = event.get('signalling'),
						dnd         = event.get('dnd'),
						uniqueid       = event.get('uniqueid', 0)
					)
		def onDahdiShowChannelsFailure(reason, servername, message = None):
			if not "unknown command" in reason.getErrorMessage():
				self._onAmiCommandFailure(reason, servername, message)			

		log.debug("Server %s :: Requesting DAHDI Channels..." % servername)
		server.pushTask(server.ami.collectDeferred, {'action': 'dahdishowchannels'}, 'DAHDIShowChannelsComplete') \
			.addCallbacks(onDahdiShowChannels, onDahdiShowChannelsFailure, errbackArgs = (servername, "Error Requesting DAHDI Channels"))
		
		# Khomp
		def onKhompChannelsShow(result):
			log.debug("Server %s :: Processing Khomp Channels..." % servername)
			if not 'no such command' in result[0].lower():
				reChannelGSM = re.compile("\|\s+([0-9,]+)\s+\|.*\|\s+([0-9%]+)\s+\|")
				reChannel    = re.compile("\|\s+([0-9,]+)\s+\|")
				for line in result:
					gChannelGSM = reChannelGSM.search(line)
					gChannel    = reChannel.search(line)
					if gChannelGSM:
						board, chanid = gChannelGSM.group(1).split(',')
						user = "Khomp/B%dC%d" % (int(board), int(chanid))
						if (self.displayUsersDefault and not server.displayUsers.has_key(user)) or (not self.displayUsersDefault and server.displayUsers.has_key(user)):
							self._createPeer(
								servername,
								channeltype = 'Khomp',
								peername    = 'B%dC%d' % (int(board), int(chanid)),
								status      = 'Signal: %s' % gChannelGSM.group(2).strip()
							)
					elif gChannel:
						board, chanid = gChannel.group(1).split(',')
						user = "Khomp/B%dC%d" % (int(board), int(chanid))
						if (self.displayUsersDefault and not server.displayUsers.has_key(user)) or (not self.displayUsersDefault and server.displayUsers.has_key(user)):
							self._createPeer(
								servername,
								channeltype = 'Khomp',
								peername    = 'B%dC%d' % (int(board), int(chanid)),
								status      = 'No Alarm'
							)
			
		log.debug("Server %s :: Requesting Khomp Channels..." % servername)
		server.pushTask(server.ami.command, 'khomp channels show') \
			.addCallbacks(onKhompChannelsShow, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting Khomp Channels"))
		
		# Meetme
		def onGetMeetmeConfig(result):
			log.debug("Server %s :: Processing meetme.conf..." % servername)
			for k, v in result.items():
				if v.startswith("conf="):
					meetmeroom = v.replace("conf=", "")
					if (self.displayMeetmesDefault and not server.displayMeetmes.has_key(meetmeroom)) or (not self.displayMeetmesDefault and server.displayMeetmes.has_key(meetmeroom)):
						self._createMeetme(servername, meetme = meetmeroom)

		log.debug("Server %s :: Requesting meetme.conf..." % servername)
		server.pushTask(server.ami.getConfig, 'meetme.conf') \
			.addCallbacks(onGetMeetmeConfig, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting meetme.conf"))

		# Wlads
		# Queues
		def onQueueStatus(events):
			log.debug("Server %s :: Processing Queues..." % servername)
			otherEvents = []
			for event in events:
				eventType = event.get('event')
				if eventType == "QueueParams":
					queuename = event.get('queue')
					if (self.displayQueuesDefault and not server.displayQueues.has_key(queuename)) or (not self.displayQueuesDefault and server.displayQueues.has_key(queuename)):
						self._createQueue(servername, mapname = server.queueMapName.get(queuename), **event)
				else:
					otherEvents.append(event)
			for event in otherEvents:
#				log.debug("Server %s :: Processing Event _updateQueue otherEvents [%s]" % (servername, event))
				self._updateQueue(servername, **event)
		
		log.debug("Server %s :: Requesting Queues..." % servername)
		server.pushTask(server.ami.collectDeferred, {'Action': 'QueueStatus'}, 'QueueStatusComplete') \
			.addCallbacks(onQueueStatus, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting Queue Status"))
		
		## Run Task Channels Status
		reactor.callWhenRunning(self.taskCheckStatus, servername)
	
	##
	## Tasks
	##
	def taskCheckStatus(self, servername):
		log.info("Server %s :: Requesting asterisk status..." % servername)
		server = self.servers.get(servername)
		
		## Channels Status
		def onStatusComplete(events):
			log.debug("Server %s :: Processing channels status..." % servername)
			channelStatus = {}
			callsCounter  = {}
			#Sort channels by uniqueid desc
			events.sort(lambda x, y: cmp(y.get('uniqueid'), x.get('uniqueid')))
			for event in events:
				uniqueid        = event.get('uniqueid')
				channel         = event.get('channel')
				bridgedchannel  = event.get('bridgedchannel', event.get('link'))
				seconds         = int(event.get('seconds', 0))
				
				tech, chan = channel.rsplit('-', 1)[0].split('/', 1)
				try:
					callsCounter[(tech, chan)] += 1
				except:
					callsCounter[(tech, chan)] = 1
				
				channelStatus[uniqueid] = None
				channelCreated          = self._createChannel(
					servername,
					uniqueid       = uniqueid,
					channel        = channel,
					state          = event.get('channelstatedesc', event.get('state')),
					calleridnum    = event.get('calleridnum'),
					calleridname   = event.get('calleridname'),
					_isCheckStatus = True,
					_log           = "-- By Status Request"
				)

			## Create bridge asterisk >= 12 (sip, pjsip) ->  Event: BridgeEnter
					
				## Create bridge if not exists
				if channelCreated and bridgedchannel:
					for bridgeduniqueid, chan in server.status.channels.items():
						if chan.channel == bridgedchannel:
							self._createBridge(
								servername,
								uniqueid        = uniqueid,
								bridgeduniqueid = bridgeduniqueid,
								channel         = channel,
								bridgedchannel  = bridgedchannel,
								status          = 'Link',
								dialtime        = time.time() - seconds,
								linktime        = time.time() - seconds,
								seconds         = seconds,
								_log            = "-- By Status Request"
							)
							break
						
			## Search for lost channels
			lostChannels = [(k, v.channel) for k, v in server.status.channels.items() if not channelStatus.has_key(k)]
			for uniqueid, channel in lostChannels:
				self._removeChannel(servername, uniqueid = uniqueid, channel = channel, _isLostChannel = True, _log = "-- Lost Channel")
			
			## Search for lost bridges
			if server.version < 12:
				lostBridges = [
					(b.uniqueid, b.bridgeduniqueid) for b in server.status.bridges.values()
					if not server.status.channels.has_key(b.uniqueid) or not server.status.channels.has_key(b.bridgeduniqueid)
				]
			else:
				lostBridges = [
					(b.uniqueid, b.bridgeduniqueid) for b in server.status.bridges.values()
					if not server.status.channels.has_key(b.uniqueid)
				]

			for uniqueid, bridgeduniqueid in lostBridges:
				self._removeBridge(servername, uniqueid = uniqueid, bridgeduniqueid = bridgeduniqueid, _isLostBridge = True, _log = "-- Lost Bridge")
			
			## Update Peer Calls Counter
			for channeltype, peers in server.status.peers.items():
				if channeltype != 'DAHDI':
					for peername, peer in peers.items():
						calls = callsCounter.get((channeltype, peername), 0)
						if peer.calls != calls:
							if server.version < 12:
								log.warning("Server %s :: Updating %s/%s calls counter from %d to %d, we lost some AMI events...", servername, channeltype, peername, peer.calls, calls)
							self._updatePeer(servername, channeltype = channeltype, peername = peername, calls = calls, _log = "-- Update calls counter (by status request)")

			## Update Dongle Status

			log.debug("Server %s :: End of channels status..." % servername)
			
		server.pushTask(server.ami.status) \
			.addCallbacks(onStatusComplete, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting Channels Status"))
		
		## Queues
		def onQueueStatusComplete(events):
			log.debug("Server %s :: Processing Queues Status..." % servername)
			for event in events:
				queuename = event.get('queue')
				if (self.displayQueuesDefault and not server.displayQueues.has_key(queuename)) or (not self.displayQueuesDefault and server.displayQueues.has_key(queuename)):
					self._updateQueue(servername, **event)
			for callid, call in server.status.queueCalls.items():
				call.seconds = int(time.time() - call.starttime)
				self.http._addUpdate(servername = servername, **call.__dict__.copy())
		
		log.debug("Server %s :: Requesting Queues Status..." % servername)
		for queuename in server.status.queues.keys():
			server.pushTask(server.ami.collectDeferred, {'Action': 'QueueStatus', 'Queue': queuename}, 'QueueStatusComplete') \
				.addCallbacks(onQueueStatusComplete, self._onAmiCommandFailure, errbackArgs = (servername, "Error Requesting Queues Status"))
				
		## Parked Calls
		def onParkedCalls(result):
			self.isParkedCallStatus = False
			if isinstance(result, failure.Failure):
				self._onAmiCommandFailure(result, servername, "Error Requesting Parked Calls")
			# Parked calls was processed by handlerEventParkedCall
		
		log.debug("Server %s :: Requesting Parked Calls..." % servername)
		self.isParkedCallStatus = True
		server.pushTask(server.ami.collectDeferred, {'Action': 'ParkedCalls'}, 'ParkedCallsComplete') \
			.addBoth(onParkedCalls)
		
	##
	## Client Action Handler
	##
	def _processClientActions(self):
		log.debug("Processing Client Actions...")
		while self.clientActions:
			session, action = self.clientActions.pop(0)
			servername      = action['server'][0]
			role, handler   = self.actionHandlers.get(action['action'][0], (None, None))
			if handler:
				if self.authRequired:
					if role in self.authUsers[session.username].servers.get(servername):
						reactor.callWhenRunning(handler, session, action)
					else:
						self.http._addUpdate(servername = servername, sessid = session.uid, action = "RequestError", message = "You do not have permission to execute this action.")
				else:
					reactor.callWhenRunning(handler, session, action)
			else:
				log.error("ClientActionHandler for action %s does not exixts..." % action['action'][0]) 
			
	def clientAction_Originate(self, session, action):
		servername  = action['server'][0]
		source      = action['from'][0]
		destination = action['to'][0] 
		type        = action['type'][0]
		server      = self.servers.get(servername)
		
		channel     = source
		context     = server.default_context
		exten       = None
		priority    = None
		timeout     = None
		callerid    = action.get('callerid', [MONAST_CALLERID])[0]
		account     = None
		application = None
		data        = None
		variable    = {}
		async       = True

		originates  = []
		logs        = []

		if type == "internalCall":
			application = "Dial"
			data        = "%s,30,rTt" % destination
			originates.append((channel, context, exten, priority, timeout, callerid, account, application, data, variable, async))
			logs.append("from %s to %s" % (channel, destination))

		if type == "dial":
			tech, peer = source.split('/')
			peer       = server.status.peers.get(tech).get(peer)
			context    = peer.context
			exten      = destination
			priority   = 1
			variable   = dict([i.split('=', 1) for i in peer.variables])
			originates.append((channel, context, exten, priority, timeout, callerid, account, application, data, variable, async))
			logs.append("from %s to %s@%s" % (channel, exten, context))
		
		if type == "meetmeInviteUser":
			application = "Meetme"
			data        = "%s%sd" % (destination, [",", "|"][server.version >= 1.4])
			originates.append((channel, context, exten, priority, timeout, callerid, account, application, data, variable, async))
			logs.append("Invite from %s to %s(%s)" % (channel, application, data))
		
		if type == "meetmeInviteNumbers":
			dynamic     = not server.status.meetmes.has_key(destination)
			application = "Meetme"
			data        = "%s%sd" % (destination, [",", "|"][server.version >= 1.4])
			numbers     = source.replace('\r', '').split('\n')
			for number in [i.strip() for i in numbers if i.strip()]:
				channel     = "Local/%s@%s" % (number, context)
				callerid    = "MonAst Invited <%s>" % (number)
				originates.append((channel, context, exten, priority, timeout, callerid, account, application, data, variable, async))
				logs.append("Invite from %s to %s(%s)" % (channel, application, data))
				
		for idx, originate in enumerate(originates):
			channel, context, exten, priority, timeout, callerid, account, application, data, variable, async = originate
			log.info("Server %s :: Executting Client Action Originate: %s..." % (servername, logs[idx]))
			server.pushTask(server.ami.originate, *originate) \
				.addErrback(self._onAmiCommandFailure, servername, "Error Executting Client Action Originate: %s" % (logs[idx]))
				
	def clientAction_Transfer(self, session, action):
		servername  = action['server'][0]
		source      = action['from'][0]
		destination = action['to'][0] 
		type        = action['type'][0]
		server      = self.servers.get(servername)
		
		channel       = source
		context       = server.default_context
		exten         = destination
		priority      = 1
		extraChannel  = None
		extraExten    = None
		extraContext  = None
		extraPriority = None
		
		if type == "meetme":
			extraChannel = action['extrachannel'][0]
			exten        = "%s%s" % (server.meetme_prefix, exten)
			context      = server.meetme_context
			
			if server.version >= 1.8: ## Asterisk >= 1.8 requires some extra params
				extraExten    = exten
				extraContext  = context
				extraPriority = priority
		
		log.info("Server %s :: Executting Client Action Transfer: %s -> %s@%s..." % (servername, channel, exten, context))
		server.pushTask(server.ami.redirect, channel, context, exten, priority, extraChannel, extraContext, extraExten, extraPriority) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Client Action Transfer: %s -> %s@%s" % (channel, exten, context))

	def clientAction_Park(self, session, action):
		servername  = action['server'][0]
		channel     = action['channel'][0]
		announce    = action['announce'][0]
		server      = self.servers.get(servername)
		
		log.info("Server %s :: Executting Client Action Park: %s from %s..." % (servername, channel, announce))
		server.pushTask(server.ami.park, channel, announce, "") \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Client Action Transfer: %s from %s" % (channel, announce))

	def clientAction_CliCommand(self, session, action):
		servername  = action['server'][0]
		command     = action['command'][0]
		
		server = self.servers.get(servername)
		def _onResponse(response):
			self.http._addUpdate(servername = servername, sessid = session.uid, action = "CliResponse", response = response)
		
		log.info("Server %s :: Executting Client Action CLI Command: %s..." % (servername, command))
		server.pushTask(server.ami.command, command) \
			.addCallbacks(_onResponse, self._onAmiCommandFailure, \
			errbackArgs = (servername, "Error Executting Client Action CLI Command '%s'" % command))
		
	def clientAction_RequestInfo(self, session, action):
		servername  = action['server'][0]
		command     = action['command'][0]
		
		server = self.servers.get(servername)
		def _onResponse(response):
			self.http._addUpdate(servername = servername, sessid = session.uid, action = "RequestInfoResponse", response = response)
			
		log.info("Server %s :: Executting Client Action Request Info: %s..." % (servername, command))
		server.pushTask(server.ami.command, command) \
			.addCallbacks(_onResponse, self._onAmiCommandFailure, \
			errbackArgs = (servername, "Error Executting Client Action Request Info '%s'" % command))
			
	def clientAction_Hangup(self, session, action):
		servername  = action['server'][0]
		channel     = action['channel'][0]
		
		log.info("Server %s :: Executting Client Action Hangup: %s..." % (servername, channel))
		server = self.servers.get(servername)
		server.pushTask(server.ami.hangup, channel) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Hangup on Channel: %s" % channel)
			
	def clientAction_MonitorStart(self, session, action):
		servername  = action['server'][0]
		channel     = action['channel'][0]
		
		log.info("Server %s :: Executting Client Action Monitor Start: %s..." % (servername, channel))
		server = self.servers.get(servername)
		server.pushTask(server.ami.monitor, channel, "", "", 1) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Monitor Start on Channel: %s" % channel)
			
	def clientAction_MonitorStop(self, session, action):
		servername  = action['server'][0]
		channel     = action['channel'][0]
		
		log.info("Server %s :: Executting Client Action Monitor Stop: %s..." % (servername, channel))
		server = self.servers.get(servername)
		server.pushTask(server.ami.stopMonitor, channel) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Monitor Stop on Channel: %s" % channel)
			
	def clientAction_QueueMemberPause(self, session, action):
		servername = action['server'][0]
		queue      = action['queue'][0]
		location   = action['location'][0]
		
		log.info("Server %s :: Executting Client Action Queue Member Pause: %s -> %s..." % (servername, queue, location))
		server = self.servers.get(servername)
		server.pushTask(server.ami.queuePause, queue, location, True) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Queue Member Pause: %s -> %s" % (queue, location))
			
	def clientAction_QueueMemberUnpause(self, session, action):
		servername = action['server'][0]
		queue      = action['queue'][0]
		location   = action['location'][0]
		
		log.info("Server %s :: Executting Client Action Queue Member Unpause: %s -> %s..." % (servername, queue, location))
		server = self.servers.get(servername)
		server.pushTask(server.ami.queuePause, queue, location, False) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Queue Member Unpause: %s -> %s" % (queue, location))
			
	def clientAction_QueueMemberAdd(self, session, action):
		servername = action['server'][0]
		queue      = action['queue'][0]
		location   = action['location'][0]
		external   = action.get('external', [False])[0]
		membername = action.get('membername', [location])[0]
		
		if not external:
			tech, peer = location.split('/')
			peer       = self.servers.get(servername).status.peers.get(tech).get(peer)
			if peer.callerid:
				membername = peer.callerid
		
		log.info("Server %s :: Executting Client Action Queue Member Add: %s -> %s..." % (servername, queue, location))
		server = self.servers.get(servername)
		server.pushTask(server.ami.queueAdd, queue, location, 0, False, membername) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Queue Member Add: %s -> %s" % (queue, location))

			
	def clientAction_QueueMemberRemove(self, session, action):
		servername = action['server'][0]
		queue      = action['queue'][0]
		location   = action['location'][0]
		
		log.info("Server %s :: Executting Client Action Queue Member Remove: %s -> %s..." % (servername, queue, location))
		server = self.servers.get(servername)
		server.pushTask(server.ami.queueRemove, queue, location) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Queue Member Remove: %s -> %s" % (queue, location))
			
	def clientAction_MeetmeKick(self, session, action):
		servername = action['server'][0]
		meetme     = action['meetme'][0]
		usernum    = action['usernum'][0]
		
		log.info("Server %s :: Executting Client Action Meetme Kick: %s -> %s..." % (servername, meetme, usernum))
		server = self.servers.get(servername)
		server.pushTask(server.ami.command, "meetme kick %s %s" % (meetme, usernum)) \
			.addErrback(self._onAmiCommandFailure, servername, "Error Executting Client Action Meetme Kick: %s -> %s..." % (meetme, usernum))
			
	def clientAction_SpyChannel(self, session, action):
		servername = action['server'][0]
		server     = self.servers.get(servername)
		spyer      = action['spyer'][0]
		spyee      = action['spyee'][0]
		type       = action['type'][0]

		channel     = None
		context     = server.default_context
		exten       = None
		priority    = None
		timeout     = None
		callerid    = "MonAst Spyer"
		account     = None
		application = "ChanSpy"
		data        = "%s%sqs" % (spyee, [",", "|"][server.version >= 1.4])
		variable    = {}
		async       = True

		if type == "peer":
			channel = spyer
			
		if type == "number":
			channel = "Local/%s@%s" % (spyer, server.default_context)
		
		log.info("Server %s :: Executting Client Action Spy Channel: %s -> %s..." % (servername, spyer, spyee))
		server.pushTask(server.ami.originate, channel, context, exten, priority, timeout, callerid, account, application, data, variable, async) \
				.addErrback(self._onAmiCommandFailure, servername, "Error Executting Client Spy Channel: %s -> %s" % (spyer, spyee))
	
	##
	## Event Handlers
	##
	def handlerEventReload(self, ami, event):
		server = self.servers.get(ami.servername)
		log.debug("Server %s :: Processing Event Reload/Shutdown..." % ami.servername)
		log.warning("Server %s :: Processing Event Reload/Shutdown...", ami.servername)
		
		if time.time() - server.lastReload > 5:
			server.lastReload = time.time()
			self._DongleSaveStat (ami.servername, channeltype = 'Dongle') ## Сохраним статистику server Reload
			# не правильно но надо сделать паузу, чтобы прогрузился канальный драйвер
			time.sleep(MODULE_LOAD_TIMER)
			self._requestAsteriskConfig(ami.servername)

## не работает искать событие
	def handlerEventModuleLoad(self, ami, event):
		module   = event.get('module', '--')
		loadtype = event.get('loadtype', '--')
		server   = self.servers.get(ami.servername)
		
		log.debug("Server %s :: Processing Event Module:[%s] Load/Unload/Reload:[%s]" % (ami.servername, module, loadtype))
		log.warning("Server %s :: Processing Event Module:[%s] Load/Unload/Reload:[%s]", ami.servername, module, loadtype)

##		if module == "chan_dongle.so":
##			if (loadtype == "unload") or (loadtype == "reload"):
##		log.debug("Server %s :: Processing Event Module Load/Unload/Reload..." % ami.servername)
##		log.warning("Server %s :: Processing Event Module:[%s] Load/Unload/Reload:[%s]", ami.servername, module, loadtype)
		
		if time.time() - server.lastReload > 5:
##			log.warning("Server %s :: Processing Event Reload...", ami.servername)
			server.lastReload = time.time()
			self._DongleSaveStat (ami.servername, channeltype = 'Dongle') ## Сохраним статистику server unload & reload
			# не правильно но надо сделать паузу, чтобы прогрузился канальный драйвер
			time.sleep(MODULE_LOAD_TIMER)
			self._requestAsteriskConfig(ami.servername)

	def handlerEventModuleLoadReport(self, ami, event):
		server   = self.servers.get(ami.servername)
		moduleloadstatus   = event.get('moduleloadstatus', '--')
		moduleselection = event.get('moduleselection', '--')
		modulecount = event.get('modulecount', '--')
		
		log.debug("Server %s :: Processing Event ModuleLoadReport moduleloadstatus:[%s] moduleselection:[%s] modulecount:[%s]" % (ami.servername, moduleloadstatus, moduleselection, modulecount))
		log.warning("Server %s :: Processing Event ModuleLoadReport moduleloadstatus:[%s] moduleselection:[%s] modulecount:[%s]",ami.servername, moduleloadstatus, moduleselection, modulecount)

		self._requestAsteriskConfig(ami.servername)

#		if time.time() - server.lastReload > 5:
###			log.warning("Server %s :: Processing Event Reload...", ami.servername)
#			server.lastReload = time.time()
#			# self._DongleSaveStat (ami.servername, channeltype = 'Dongle') ## Сохраним статистику server unload & reload
#			# не правильно но надо сделать паузу, чтобы прогрузился канальный драйвер
#			# time.sleep(MODULE_LOAD_TIMER)
#			self._requestAsteriskConfig(ami.servername)

	def handlerEventChannelReload(self, ami, event):
		channel = event.get('channel', '--')
		server = self.servers.get(ami.servername)

		log.debug("Server %s :: Processing Event Channel:[%s] ChannelReload..." % (ami.servername, channel))
		log.warning("Server %s :: Processing Event Channel:[%s] ChannelReload...", ami.servername, channel)
				
		if time.time() - server.lastReload > 5:
#			log.warning("Server %s :: Processing Event Channel:[%s] Reload...", ami.servername, channel)
			server.lastReload = time.time()
			self._DongleSaveStat (ami.servername, channeltype = 'Dongle') ## Сохраним статистику
			# не правильно но надо сделать паузу, чтобы прогрузился канальный драйвер
			time.sleep(MODULE_LOAD_TIMER)
			self._requestAsteriskConfig(ami.servername)
	
	def handlerEventAlarm(self, ami, event):
		log.debug("Server %s :: Processing Event Alarm..." % ami.servername)
		channel = event.get('channel')
		alarm   = event.get('alarm', 'No Alarm')
		tech    = "DAHDI"
		chan    = channel
		
		if not channel.isdigit(): # Not a DAHDI Channel
			tech, chan = channel.split('/', 1)
		
		self._updatePeer(ami.servername, channeltype = tech, peername = chan, alarm = alarm, status = alarm, _log = "Alarm Detected (%s)" % alarm)
		
	def handlerEventAlarmClear(self, ami, event):
		log.debug("Server %s :: Processing Event AlarmClear..." % ami.servername)
		channel = event.get('channel')
		tech    = "DAHDI"
		chan    = channel
		
		if not channel.isdigit(): # Not a DAHDI Channel
			tech, chan = channel.split('/', 1)
		
		self._updatePeer(ami.servername, channeltype = tech, peername = chan, alarm = 'No Alarm', status = 'No Alarm', _log = "Alarm Cleared")
			
	def handlerEventDNDState(self, ami, event):
		log.debug("Server %s :: Processing Event DNDState..." % ami.servername)
		channel = event.get('channel')
		status  = event.get('status')
		dnd     = status.lower() == "enabled"
				
		tech, chan = channel.split('/', 1)
		self._updatePeer(ami.servername, channeltype = tech, peername = chan, dnd = dnd, _log = "DND (%s)" % status)
		
	def handlerEventPeerEntry(self, ami, event):
		log.debug("Server %s :: Processing Event PeerEntry..." % ami.servername)
		server      = self.servers.get(ami.servername)
		status      = event.get('status')
		channeltype = event.get('channeltype')
		objectname  = event.get('objectname').split('/')[0]
		time        = -1
		
		reTime = re.compile("([0-9]+)\s+ms")
		gTime  = reTime.search(status)
		if gTime:
			time = int(gTime.group(1))
		
		if status.startswith('OK'):
			status = 'Registered'
		elif status.find('(') != -1:
			status = status[0:status.find('(')]
			
		user = '%s/%s' % (channeltype, objectname)
		
		if (self.displayUsersDefault and not server.displayUsers.has_key(user)) or (not self.displayUsersDefault and server.displayUsers.has_key(user)):		
			self._createPeer(
				ami.servername,
				channeltype = channeltype,
				peername    = objectname,
				status      = status,
				time        = time
			)
		else:
			user = None

		if channeltype != 'Dongle':		
			if user:
				type    = ['peer', 'user'][channeltype == 'Skype']
				command = '%s show %s %s' % (channeltype.lower(), type, objectname)
				
				def onShowPeer(response):
					log.debug("Server %s :: Processing %s..." % (ami.servername, command))
					result    = '\n'.join(response)
					callerid  = None
					context   = None
					variables = []
					
					try:
						callerid = re.compile("['\"]").sub("", re.search('Callerid[\s]+:[\s](.*)\n', result).group(1))
						if callerid == ' <>':
							callerid = '--'
					except:
						callerid = '--'
					
					try:
						context = re.search('Context[\s]+:[\s](.*)\n', result).group(1)
					except:
						context = server.default_context
					
					start = False
					for line in response:
						if re.search('Variables[\s+]', line):
							start = True
							continue
						if start:
							gVar = re.search('^[\s]+([^=]*)=(.*)', line)
							if gVar:
								variables.append("%s=%s" % (gVar.group(1).strip(), gVar.group(2).strip()))
					
					self._updatePeer(
						ami.servername, 
						channeltype = channeltype, 
						peername    = objectname,
						callerid    = [callerid, objectname][callerid == "--"],
						context     = context,
						variables   = variables
					)
					
				server.pushTask(server.ami.command, command) \
					.addCallbacks(onShowPeer, self._onAmiCommandFailure, \
						errbackArgs = (ami.servername, "Error Executting Command '%s'" % command))

		else:
			if user:		
				level		= event.get('level', '--')
#				quality = event.get('quality', '--')

				if level != '--':	
					sig = int(level) 	
					if sig == -51:				## подозрительно отличный сигнал
						quality = "Super"
					elif sig >= -75 and sig < -51:		## отличный сигнал
						quality = "Excellent"
					elif sig >= -85 and sig < -75:		## хороший сигнал
						quality = "Good"
					elif sig >= -95 and sig < -85:		## удовлетворительный сигнал
						quality = "Normal"
					elif sig >= -100 and sig < -95:		## плохой сигнал
						quality = "Bad"
					elif sig  < '-100':			## очень плохой сигнал, либо отсутствует
						quality = "Very bad"
				else:
					 quality = '--'
			
				command = 'dongle show device settings %s' % objectname
				def onShowPeer(response):
					log.debug("Server %s :: Processing %s..." % (ami.servername, command))
					result    = '\n'.join(response)
					callerid  = None
					context   = None				
					variables = []
				
					try:
						callerid = re.compile("['\"]").sub("", re.search('Device[\s]+:[\s](.*)\n', result).group(1))
						if callerid == ' <>':
							callerid = '--'
					except:
						callerid = '--'
					
					try:
						context = re.search('Context[\s]+:[\s](.*)\n', result).group(1)
					except:
						context = server.default_context
					
					start = False
					for line in response:
						if re.search('Settings[\s+]', line):
							start = True
							continue 

						if start:
							gVar = re.search('^[\s]+([^=]*)=(.*)', line)
							if gVar:
								variables.append("%s=%s" % (gVar.group(1).strip(), gVar.group(2).strip()))
	
								self._updatePeer(
									ami.servername,
									channeltype = channeltype,
									peername    = objectname,
									callerid    = [callerid, objectname][callerid == "--"],
									context     = context,
									## добавим уровни
									level       = level,
									quality     = quality,	
									variables   = variables
									)
	
				server.pushTask(server.ami.command, command) \
					.addCallbacks(onShowPeer, self._onAmiCommandFailure, \
					errbackArgs = (ami.servername, "Error Executting Command '%s'" % command))

## https://wiki.asterisk.org/wiki/display/AST/Asterisk+13+ManagerEvent_ContactStatus
## Event: ContactStatus
## URI: <value>
## ContactStatus: <value>
## AOR: <value>
## EndpointName: <value>
## RoundtripUsec: <value>
## UserAgent: <value>
## RegExpire: <value>
## ViaAddress: <value>
## CallID: <value>
	def handlerEventContactStatus(self, ami, event):
		log.debug("Server %s :: Processing Event ContactStatus..." % ami.servername)
		server        = self.servers.get(ami.servername)
		endpointname  = event.get('endpointname')
		time = int(event.get('roundtripusec'))

		channeltype  = 'PJSIP'
#		time = int(roundtripusec)

		self._updatePeer(ami.servername, channeltype = channeltype, peername = endpointname, time = time)
			

## https://wiki.asterisk.org/wiki/display/AST/Asterisk+13+ManagerEvent_RTCPReceived
	def handlerEventRTCPReceived(self, ami, event):
		log.debug("Server %s :: Processing Event RTCPReceived..." % ami.servername)
		server           = self.servers.get(ami.servername)
		channel          = event.get('channel')
		channelstatedesc = event.get('channelstatedesc')
##		uniqueid         = event.get('uniqueid')
##		linkedid         = event.get('linkedid') ## - Уникальный из самого старого канала, связанного с этим каналом.
		rtt              = event.get('rtt')

		channeltype  = channel.split('/')[0]
		peername  = channel.split('/')[1]
		time = int(rtt)*1000

		if channeltype != 'PJSIP':
			if time:
				self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = channelstatedesc, time = time)
##			else:
##				self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = channelstatedesc)

## pjsip
	def handlerEventEndpointList(self, ami, event):
		log.debug("Server %s :: Processing Event PJSIP EndpointList..." % ami.servername)
		server      = self.servers.get(ami.servername)
		objectname  = event.get('objectname')
		status      = event.get('devicestate')
		channeltype = 'PJSIP' 

		time        = -1
		
##		reTime = re.compile("([0-9]+)\s+ms")
##		gTime  = reTime.search(status)
##		if gTime:
##			time = int(gTime.group(1))
		
##		if status.startswith('OK'):
##			status = 'Registered'
##		elif status.find('(') != -1:
##			status = status[0:status.find('(')]
			
		if objectname != 'dpma_endpoint':
			user = '%s/%s' % (channeltype, objectname)
##			log.warning("Server %s :: PJSIP - EndpointList - [%s], objectname [%s], status [%s], Channeltype [%s]" % (server, user, objectname, status, channeltype))

			if (self.displayUsersDefault and not server.displayUsers.has_key(user)) or (not self.displayUsersDefault and server.displayUsers.has_key(user)):
				self._createPeer(
					ami.servername,
					channeltype = channeltype,
					peername    = objectname,
					status      = status,
					time        = time
				)
			else:
				user = None

	def handlerEventPeerStatus(self, ami, event):
		log.debug("Server %s :: Processing Event PeerStatus..." % ami.servername)
		channel = event.get('peer')
		status  = event.get('peerstatus')
		time    = event.get('time')
		channeltype, peername = channel.split('/', 1)
		
		if time:
			self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = status, time = time)
		else:
			self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = status)

	def handlerEventEndpointDetail(self, ami, event):
		log.debug("Server %s :: Processing Event PJSIP handlerEventEndpointDetail..." % ami.servername)
		objectname  = event.get('objectname')
		status   = event.get('devicestate')
		callerid = event.get('callerid').replace('\"','')
		context  = event.get('context')
		time     = event.get('timers')
		channeltype = 'PJSIP'

		if callerid == '<unknown>':
			callerid = objectname

##		log.debug("Requesting EndpointDetail PJSIP Peer [%s] status [%s], callerid [%s], context [%s], time [%s]" % (objectname, status, callerid, context, time))
		
		if time:
			self._updatePeer(ami.servername, channeltype = channeltype, peername = objectname, status = status, callerid = callerid, context = context, time = time)
		else:
			self._updatePeer(ami.servername, channeltype = channeltype, peername = objectname, status = status, callerid = callerid, context = context)

	def handlerEventAorDetail(self, ami, event):
		log.debug("Server %s :: Processing Event PJSIP handlerEventAorDetail..." % ami.servername)

	def handlerEventAuthDetail(self, ami, event):
		log.debug("Server %s :: Processing Event PJSIP handlerEventAuthDetail..." % ami.servername)

	def handlerEventTransportDetail (self, ami, event):
		log.debug("Server %s :: Processing Event PJSIP handlerEventTransportDetail..." % ami.servername)
		
	def handlerEventIdentifyDetail(self, ami, event):
		log.debug("Server %s :: Processing Event PJSIP handlerEventIdentifyDetail..." % ami.servername)

	def handlerEventEndpointlistComplete(self, ami, event):
		log.debug("Server %s :: Processing Event PJSIP handlerEventEndpointlistComplete..." % ami.servername)

#		:: Line In: 'Event: BridgeCreate'                                 
#		:: Line In: 'Privilege: call,all'                                 
#		:: Line In: 'BridgeUniqueid: d0b3ecfc-1a27-4bd7-95af-42df81c272f5'
#		:: Line In: 'BridgeType: basic'                                   
#		:: Line In: 'BridgeTechnology: simple_bridge'                     
#		:: Line In: 'BridgeCreator: <unknown>'                            
#		:: Line In: 'BridgeName: <unknown>'                               
#		:: Line In: 'BridgeNumChannels: 0'                                
#		:: Line In: ''                                                    
	def handlerEventBridgeCreate(self, ami, event):
		log.debug("Server %s :: Processing Event handlerEventBridgeCreate..." % ami.servername)



# тел 1																												тел 2
# Line In: 'Event: BridgeEnter'                                  	 Line In: 'Event: BridgeEnter'                                  
# Line In: 'Privilege: call,all'                                 	 Line In: 'Privilege: call,all'                                 
# Line In: 'BridgeUniqueid: 7090ec7d-2be4-42ca-b165-42044854a271'	 Line In: 'BridgeUniqueid: 7090ec7d-2be4-42ca-b165-42044854a271'
# Line In: 'BridgeType: basic'                                   	 Line In: 'BridgeType: basic'                                   
# Line In: 'BridgeTechnology: simple_bridge'                     	 Line In: 'BridgeTechnology: simple_bridge'                     
# Line In: 'BridgeCreator: <unknown>'                            	 Line In: 'BridgeCreator: <unknown>'                            
# Line In: 'BridgeName: <unknown>'                               	 Line In: 'BridgeName: <unknown>'                               
# Line In: 'BridgeNumChannels: 1'                                	 Line In: 'BridgeNumChannels: 2'                                
# Line In: 'BridgeVideoSourceMode: none'                         	 Line In: 'BridgeVideoSourceMode: none'                         
# Line In: 'Channel: SIP/262-00000008'                           	 Line In: 'Channel: SIP/261-00000007'                           
# Line In: 'ChannelState: 6'                                     	 Line In: 'ChannelState: 6'                                     
# Line In: 'ChannelStateDesc: Up'                                	 Line In: 'ChannelStateDesc: Up'                                
# Line In: 'CallerIDNum: 262'                                    	 Line In: 'CallerIDNum: 261'                                    
# Line In: 'CallerIDName: Operator 2'                            	 Line In: 'CallerIDName: Operator 1'                            
# Line In: 'ConnectedLineNum: 261'                               	 Line In: 'ConnectedLineNum: 262'                               
# Line In: 'ConnectedLineName: Operator 1'                       	 Line In: 'ConnectedLineName: Operator 2'                       
# Line In: 'Language: en'                                        	 Line In: 'Language: ru'                                        
# Line In: 'AccountCode: '                                       	 Line In: 'AccountCode: '                                       
# Line In: 'Context: from-internal'                              	 Line In: 'Context: macro-dial-one'                             
# Line In: 'Exten: '                                             	 Line In: 'Exten: s'                                            
# Line In: 'Priority: 1'                                         	 Line In: 'Priority: 43'                                        
# Line In: 'Uniqueid: 1540521762.55'                             	 Line In: 'Uniqueid: 1540521761.53'                             
# Line In: 'Linkedid: 1540521761.53'                             	 Line In: 'Linkedid: 1540521761.53'                             
# Line In: ''                                                    	 Line In: ''
	def handlerEventBridgeEnter(self, ami, event):
		log.debug("Server %s :: Processing Event handlerEventBridgeEnter..." % ami.servername)
		server      = self.servers.get(ami.servername)
		
		bridgeduniqueid   = event.get('bridgeuniqueid')
		calleridnum       = event.get('calleridnum')
		calleridname      = event.get('calleridname')
		connectedlinenum  = event.get('connectedlinenum')        
		connectedlinename = event.get('connectedlinename')
		bridgetype        = event.get('bridgetype')
		bridgenumchannels = event.get('bridgenumchannels')
		linkedid          = event.get('linkedid')
		seconds           = int(event.get('seconds', 0))

		channelStatus = {}
		uniqueid        = event.get('uniqueid')					# In: 'Uniqueid: 1506397267.8'
		channel         = event.get('channel')          # 'Channel: PJSIP/200-00000004' 
		bridgedchannel  = event.get('linkedid')					# In: 'Linkedid: 1506397267.7'

		tech, chan = channel.rsplit('-', 1)[0].split('/', 1)

		calleridname = calleridname.replace("CID:","")
		if calleridname == "<unknown>":
			calleridname = ""

		if uniqueid != linkedid:					# Step 1 Вызывайщий канал
			self._updateChannel(
				ami.servername,
				uniqueid     = uniqueid,
				channel      = channel,
				calleridnum  = calleridnum,
				calleridname = calleridname,
				bridgeduniqueid = bridgeduniqueid,
#				_log         = "-- Callerid updated to '%s <%s>' uniqueid [%s] bridgeduniqueid [%s]" % (calleridname, calleridnum, uniqueid, bridgeduniqueid)
				_log         = "-- Channel BridgeUniqueid updated"
			)

		else: 														# Step 2 прилетели данные 2 го канала бриджа 	
			self._updateChannel(
				ami.servername,
				uniqueid     = uniqueid,
				channel      = channel,
				calleridnum  = calleridnum,
				calleridname = calleridname,
				bridgeduniqueid = bridgeduniqueid,
#				_log         = "-- Callerid updated to '%s <%s>' uniqueid [%s] bridgeduniqueid [%s]" % (calleridname, calleridnum, uniqueid, bridgeduniqueid)
				_log         = "-- Channel BridgeUniqueid updated"
			)

			for uniqueid0, chan in server.status.channels.items(): 		# пройдемся по каналам
#				log.debug("Object Dump:%s", chan)
				if chan.bridgeduniqueid == bridgeduniqueid: 						# выбирам нужный бридж
					if chan.uniqueid == uniqueid: 												# куда звоним
						channel  = chan.channel
						uniqueid = chan.uniqueid
						callerid = (chan.calleridnum, chan.calleridname)
					else:
						bridgedchannel 	 = chan.channel
#  Куда звоним
						bridgedcallerid  = (chan.calleridnum, chan.calleridname)

# если проверяем на существование
						bridgekey = self._locateBridge(ami.servername, uniqueid = uniqueid, bridgeduniqueid = bridgeduniqueid)

						if not bridgekey:
							self._createBridge(
								ami.servername,
								uniqueid        = uniqueid, 
								bridgeduniqueid = bridgeduniqueid,
								linkedid        = chan.uniqueid,					#		для b.bridgedcallerid js
								channel         = channel,
								bridgedchannel  = bridgedchannel,
								status          = 'Link',
								linktime        = time.time(),
								_log            = "-- Link"
							)
						
							# Detect QueueCall
							queueCall = server.status.queueCalls.get(uniqueid)

							if queueCall:
								queuename = queueCall.client.get('queue')
								location  = bridgedchannel.rsplit('-', 1)[0]
								member    = None
								for location in [location, "%s/n" % location]:
									member = server.status.queueMembers.get((queuename, location))
									if member:
										queueCall.member  = member.__dict__
										queueCall.link    = True
										queueCall.seconds = int(time.time() - queueCall.starttime) 
										self.http._addUpdate(servername = ami.servername, **queueCall.__dict__.copy())
										if logging.DUMPOBJECTS:
											log.debug("Object Dump:%s", queueCall)


	def handlerEventBridgeUpdate(self, ami, event):
#		log.debug("Server %s :: Processing Event handlerEventBridgeUpdate... event[%s]" % (ami.servername, event))
		log.debug("Server %s :: Processing Event handlerEventBridgeUpdate..." % (ami.servername))




#		:: Line In: 'Event: BridgeLeave'
#		:: Line In: 'Privilege: call,all'
#		:: Line In: 'BridgeUniqueid: d0b3ecfc-1a27-4bd7-95af-42df81c272f5'
#		:: Line In: 'BridgeType: basic'
#		:: Line In: 'BridgeTechnology: simple_bridge'
#		:: Line In: 'BridgeCreator: <unknown>'
#		:: Line In: 'BridgeName: <unknown>'
#		:: Line In: 'BridgeNumChannels: 0'
#		:: Line In: 'Channel: PJSIP/200-00000004'
#		:: Line In: 'ChannelState: 6'
#		:: Line In: 'ChannelStateDesc: Up'
#		:: Line In: 'CallerIDNum: 200'
#		:: Line In: 'CallerIDName: device'
#		:: Line In: 'ConnectedLineNum: 100'
#		:: Line In: 'ConnectedLineName: test-sip'
#		:: Line In: 'Language: ru'
#		:: Line In: 'AccountCode: '
#		:: Line In: 'Context: from-internal'
#		:: Line In: 'Exten: '
#		:: Line In: 'Priority: 1'
#		:: Line In: 'Uniqueid: 1506397267.8'
#		:: Line In: 'Linkedid: 1506397267.7'
#		:: Line In: ''
	def handlerEventUBridgeLeave(self, ami, event):
#		log.debug("Server %s :: Processing Event handlerEventUBridgeLeave... event[%s]" % (ami.servername, event))
		log.debug("Server %s :: Processing Event handlerEventUBridgeLeave..." % (ami.servername))

		server      = self.servers.get(ami.servername)
		bridgeduniqueid   = event.get('bridgeuniqueid')
		calleridnum       = event.get('calleridnum')
		calleridname      = event.get('calleridname')

		channelStatus = {}
		uniqueid        = event.get('uniqueid')					# In: 'Uniqueid: 1506397267.8'
		channel         = event.get('channel')          # 'Channel: PJSIP/200-00000004' 
		linkedid        = event.get('linkedid')

		tech, chan = channel.rsplit('-', 1)[0].split('/', 1)
		calleridname = calleridname.replace("CID:","")
		if calleridname == "<unknown>":
			calleridname = ""

		if server.status.channels.has_key(uniqueid):		# если канал жив то обновляем
			self._updateChannel(
				ami.servername,
				uniqueid        = uniqueid,
				channel         = channel,
				calleridnum     = calleridnum,
				calleridname    = calleridname,
				bridgeduniqueid = bridgeduniqueid,
				_log            = "-- Channel BridgeUniqueid updated"
			)

			bridgekey = self._locateBridge(ami.servername, uniqueid = uniqueid, bridgeduniqueid = bridgeduniqueid)
			if not bridgekey:
				bridgekey = self._locateBridge(ami.servername, uniqueid = linkedid, bridgeduniqueid = bridgeduniqueid)
				if not bridgekey:
					for uniqueid0, chan in server.status.channels.items(): 		# пройдемся по каналам зададим bridgeduniqueid
						if chan.uniqueid == uniqueid or chan.uniqueid == linkedid:
							self._updateChannel(
								ami.servername,
								uniqueid        = chan.uniqueid,
								channel         = chan.channel,
								bridgeduniqueid = bridgeduniqueid,
								_log            = "-- Channel - BridgeUniqueid updated"
							)

					for uniqueid0, chan in server.status.channels.items(): 		# пройдемся по каналам
#						log.debug("Object Dump:%s", chan)
						if chan.bridgeduniqueid == bridgeduniqueid: 						# выбирам нужный бридж 
							if chan.uniqueid == linkedid: 												# куда звоним
								channel  = chan.channel
								uniqueid = chan.uniqueid
								callerid = (chan.calleridnum, chan.calleridname)
							else:
								bridgedchannel 	 = chan.channel
# 		 Куда звоним
								bridgedcallerid  = (chan.calleridnum, chan.calleridname)

					if uniqueid == linkedid:
						log.debug("Server %s :: handlerEventUBridgeLeave 2-2 bridgeduniqueid-[%s] uniqueid-[%s] linkedid-[%s] channel-[%s] bridgedchannel-[%s]" % (ami.servername, bridgeduniqueid, uniqueid, linkedid, channel, bridgedchannel))
						self._createBridge(
							ami.servername,
							uniqueid        = uniqueid, 
							bridgeduniqueid = bridgeduniqueid,
							linkedid        = linkedid,
							channel         = chan.channel,
							bridgedchannel  = bridgedchannel,
							status          = 'Link',
							linktime        = time.time(),
							_log            = "-- Restore Bridge Link"
						)


#		:: Line In: 'Event: BridgeDestroy'
#		:: Line In: 'Privilege: call,all'
#		:: Line In: 'BridgeUniqueid: d0b3ecfc-1a27-4bd7-95af-42df81c272f5'
#		:: Line In: 'BridgeType: basic'
#		:: Line In: 'BridgeTechnology: simple_bridge'
#		:: Line In: 'BridgeCreator: <unknown>'
#		:: Line In: 'BridgeName: <unknown>'
#		:: Line In: 'BridgeNumChannels: 0'
#		:: Line In: ''
	def handlerEventBridgeDestroy(self, ami, event):
		log.debug("Server %s :: Processing Event handlerEventBridgeDestroy..." % ami.servername)

		server      = self.servers.get(ami.servername)
		bridgeduniqueid = event.get('bridgeuniqueid')
		

		for uniqueid, chan in server.status.channels.items(): 	# пройдемся по каналам
#			log.debug("Object Dump:%s", chan)
			if chan.bridgeduniqueid == bridgeduniqueid: 					# выбирам нужный бридж
				uniqueid = chan.uniqueid
				break

		bridgekey = (uniqueid, bridgeduniqueid)
		bridge    = server.status.bridges.get(bridgekey)
		if bridge:
			self._removeBridge(ami.servername, uniqueid = uniqueid, bridgeduniqueid = bridgeduniqueid, _log = "-- End Bridge")	

		# Detect QueueCall
		queueCall = server.status.queueCalls.get(uniqueid)
#		queueCall = server.status.queueCalls.get(bridgeduniqueid)
		
		if queueCall:
			queueCall.link = False
			if queueCall.member:
				log.debug("Server %s :: Queue update, client -> member call unlink: %s -> %s -> %s", ami.servername, queueCall.client.get('queue'), uniqueid, queueCall.member.get('location'))
				self.http._addUpdate(servername = ami.servername, action = "RemoveQueueCall", uniqueid = uniqueid, queue = queueCall.client.get('queue'), location = queueCall.member.get('location'))
#				log.debug("Server %s :: Queue update, client -> member call unlink: %s -> %s -> %s", ami.servername, queueCall.client.get('queue'), bridgeduniqueid, queueCall.member.get('location'))
#				self.http._addUpdate(servername = ami.servername, action = "RemoveQueueCall", uniqueid = bridgeduniqueid, queue = queueCall.client.get('queue'), location = queueCall.member.get('location'))

				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", queueCall)



	def handlerEventUserEvent(self, ami, event):
		log.debug("Server %s :: Processing Event Reset Dongle Statistic ..." % ami.servername)
		channeltype = event.get('channeltype')
		event = event.get('userevent')
##			log.warning("Server %s :: Processing Event UserEvent, channeltype = [%s], userevent = [%s], some AMI events...", ami.servername, channeltype, event )

		if ((event == "ResetStat") & (channeltype == "Dongle")):
			self._DongleResetStat (ami.servername, channeltype = 'Dongle')

		elif ((event == "SaveStat") & (channeltype == "Dongle")):
			self._DongleSaveStat (ami.servername, channeltype = 'Dongle')		## Сохраним статистику server AMI events

		elif ((event == "SaveStatAll") & (channeltype == "Dongle")):
			for servername in self.servers:
				self._DongleSaveStat (servername, channeltype = 'Dongle')			## Сохраним статистику по всем подключеным серверам server AMI events

		elif event == "UpdatePeers":
		##	log.warning("Server %s :: UpdatePeers AMI events...", ami.servername)
			self._requestAsteriskPeers(ami.servername, 'ALL')								## обновим список пиров
#			self._requestAsteriskPeers(ami.servername, {'channeltype': 'ALL'})

## Test
##		elif ((event == "DonglePortFail") & (channeltype == "Dongle")):
##			peername = 'dn1'
##			status = 'Port Fail'
##			counter = 'increaseDonglePortFail'
##						
##			log.warning("Server %s :: Dongle PortFail (test) [%s], Status = [%s], some AMI events...", ami.servername, peername, status)
##			self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = status, _action = counter)

## Test 2
		elif event == "TestReload":
			self.handlerEventReload( ami, {'channel': channeltype})
		elif event == "TestModuleReload":
			self.handlerEventModuleLoad(ami, {'module': 'chan_sip.so','loadtype': 'reload'})
		elif event == "TestChannelReload":
			self.handlerEventChannelReload(ami, {'channel': channeltype})


	def handlerEventDongleStatus(self, ami, event):
		log.debug("Server %s :: Processing Event DongleStatus..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
		peer.status  = event.get('status')
		peer.channeltype = "Dongle"
		peer.channel  = '%s/%s' % (peer.channeltype, peer.peername)

		send = "1" ## для отображения всех сообщений
	##	send = "0" ## для отображения событий DongleChanelStatus (Ring, Dial, и т.д.)
 
		if peer.status == "Disconnect":
			send = "1"
		elif peer.status == "Unregister":
			send = "1"
		elif peer.status == "Register":
			send = "0"
		elif peer.status == "Initialize":
		##	peer.status = "Register"
			send = "1"
	##	elif peer.status == 'Connect':
	##		self.handlerEventPeerEntry(server.ami, {'channeltype': 'Dongle', 'objectname': peer.peername, 'status': 'Connect'})
	##		send = "0"

		elif peer.status == 'Loaded':
##			log.warning("Server %s :: DongleStatus [%s], Status = [%s], servername = [%s], some AMI events...", ami.servername, peer.peername, peer.status, ami.servername )
			self._createPeer(
					ami.servername,
					channeltype = 'Dongle',
					peername    = peer.peername,
			)
		elif peer.status == 'Removal':
##			log.warning("Server %s :: DongleStatus [%s], Status = [%s], servername = [%s], some AMI events...", ami.servername, peer.peername, peer.status, ami.servername )
			self._deletePeer(
					ami.servername,
					channeltype = 'Dongle',
					peername    = peer.peername,
					status      = 'Removal',
			)
		
		if peer.status == 'Disconnect':
			counter = 'reboot'
			level = "--"
			quality = "--"
			self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, status = peer.status, _action = counter, level = level, quality = quality)
		else:
			counter = 'clearSms'

		if send != "0":
		##	log.warning("Server %s :: DongleStatus [%s], Status = [%s], Counter = [%s], some AMI events...", ami.servername, peer.peername, peer.status, counter)
			self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, status = peer.status, _action = counter)

	def handlerEventDonglePortFail(self, ami, event):
		log.debug("Server %s :: Processing Event DonglePortFail..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
##		peer.status  = event.get('message')
		peer.channeltype = "Dongle"
		peer.channel  = '%s/%s' % (peer.channeltype, peer.peername)
		peer.status = "Port Fail"
		
## рестарт зависшего порта /dev/ttyUSB44
## http://www.py-my.ru/post/4bfb3c691d41c846bc000061
		str = peer.peername
		if str[:5] == '/dev/':
			peer.status = "Reset Port"
			cmd = self.scriptpath + '/usbreset.sh ' + peer.peername			
##			cmd = '/root/script/usbreset.sh ' + peer.peername
## без ожидания результата 
##			subprocess.Popen(cmd, shell = True)
##			str2 = 'Send Reset USB device'
## с ожиданием результата 

			PIPE = subprocess.PIPE
			p = subprocess.Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE,stderr=subprocess.STDOUT, close_fds=True, cwd='/root/script')
			str2 = p.stdout.read()

			log.warning("Server %s :: Dongle PortFail [%s], cmd = [%s]->[%s]", ami.servername, peer.peername, cmd, str2)
		else:
			counter = 'increaseDonglePortFail'
			log.warning("Server %s :: Dongle PortFail [%s], Status = [%s], some AMI events...", ami.servername, peer.peername, peer.status)
			self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, status = peer.status, _action = counter)


	def handlerEventDongleChanelStatus(self, ami, event):
		log.debug("Server %s :: Processing Event DongleStatus..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
		peer.status  = event.get('status')
		peer.channeltype = "Dongle"
		peer.channel  = '%s/%s' % (peer.channeltype, peer.peername)  

## wlad ======================================
		if peer.status == 'Incoming':
			counter = 'increaseCallIncom'
		elif peer.status == 'Dialing':
			counter = 'increaseCallDialing'
		elif peer.status == 'Outgoing':
			counter = 'increaseCallOutcom'
		else:
			counter = 'clearSms'

	##	log.warning("Server %s :: DongleChanelStatus [%s], Status = [%s], Counter = [%s], some AMI events...", ami.servername, peer.peername, peer.status, counter)
		self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, status = peer.status, _action = counter)
 
	## Dongle Events
	def handlerEventDongleAntennaLevel(self, ami, event):
		log.debug("Server %s :: Processing Event DongleAntennaLevel..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
	##	rssi  = event.get('rssi')
		signal  = event.get('signal')
		peer.channeltype = "Dongle"
	##	peer.level = signal
	##	channeltype = "Dongle"

		level = signal.split(' ', 1)[0] ## отрезаем dBm

		if level == '>=':   ## >= -51 dBm
			level = signal.split(' ', 1)[1].split(' ', 1)[0]

		if level == '<=':   ## <= -113 dBm
			level = signal.split(' ', 1)[1].split(' ', 1)[0] 
		
		if level == 'unknown':   ## 'unknown or unmeasurable' - Неизвестный или неизмеримый
			return
			
		sig = int(level) 	
		if sig == -51:				## подозрительно отличный сигнал
			quality = "Super"
		elif sig >= -75 and sig < -51:		## отличный сигнал
			quality = "Excellent"
		elif sig >= -85 and sig < -75:		## хороший сигнал
			quality = "Good"
		elif sig >= -95 and sig < -85:		## удовлетворительный сигнал
			quality = "Normal"
		elif sig >= -100 and sig < -95:		## плохой сигнал
			quality = "Bad"
		elif sig  < '-100':			## очень плохой сигнал, либо отсутствует
			quality = "Very bad"
 
		## channeltype, peername = channel.split('/', 1)
	##	log.warning("Server %s :: DongleAntennaLevel [%s], LevelFull = [%s], Level = [%s], Quality =[%s] some AMI events...", ami.servername, peer.peername, signal, level, quality)
	##	Вместо статуса канала выдает уровень приема - неудобно
	##	self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, status = 'Signal: %s' % signal)
	##	раб в вар без СМС
	##	self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, time = '%s' % signal, sms = '--')
		## при получении нового сигнала чистим поле СМС - что не совсем коректно
		
		self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, level = '%s' % level, quality = '%s' % quality, _action = 'clearSms')

	def handlerEventDongleCallStateChange(self, ami, event):
		log.debug("Server %s :: Processing Event DongleDeviceStatus..." % ami.servername)
	
		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
		peer.status  = event.get('newstate')
		peer.channeltype = "Dongle"
		peer.channel  = '%s/%s' % (peer.channeltype, peer.peername)  

		if peer.status == "released":
			peer.status = "Free"

	##	log.warning("Server %s :: DongleDeviceStatus [%s], Status = [%s], some AMI events...", ami.servername, peer.peername, peer.status )
		self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, status = peer.status, _action = 'clearSms')

	##wlad

	def handlerEventDongleSentSMSNotify(self, ami, event):
		log.debug("Server %s :: Processing Event DongleSentNotify..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername    = event.get('device')
		peer.status      = 'sms - %s' % (event.get('status'))
		peer.channeltype = "Dongle"
		peer.channel     = '%s/%s' % (peer.channeltype, peer.peername)
		peer.time        = time.time()
		
		if peer.status == 'sms - Sent':
			counter = 'increaseSmsSend'
		elif peer.status == 'sms - NotSent':
			counter = 'increaseSmsError'
		
	##	log.warning("Server %s :: DongleSentSMSNotify [%s], Status = [%s], Time = [%s], Counter = [%s], some AMI events...", ami.servername, peer.peername, peer.status, peer.time, counter)
		self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, sms = peer.status, time = peer.time, _action = counter)

	def handlerEventDongleSentUSSDNotify(self, ami, event):             
		log.debug("Server %s :: Processing Event DongleSentNotify..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
		peer.status  = 'ussd - %s' % (event.get('status'))           
		peer.channeltype = "Dongle"
		peer.channel  = '%s/%s' % (peer.channeltype, peer.peername)   
		peer.time        = time.time()
		
		if peer.status == 'ussd - Sent':
			counter = 'increaseUSSDSend'
		else:
			counter = 'false'

	##	log.warning("Server %s :: DongleSentUSSDNotify [%s], Status = [%s], Time = [%s], Counter = [%s], some AMI events...", ami.servername, peer.peername, peer.status, peer.time, counter)
		self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, sms = peer.status, time = peer.time, _action = counter)

	def handlerEventDongleNewSmsBase64(self, ami, event):   
		log.debug("Server %s :: Processing Event DongleNewSmsBase64..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
		peer.status  = "incom. sms"
		peer.channeltype = "Dongle"
		peer.channel  = '%s/%s' % (peer.channeltype, peer.peername)
		peer.time        = time.time()
		counter = 'increaseSmsIncom'
		
	##	log.warning("Server %s :: DongleNewSmsBase64 [%s], Status = [%s], Time = [%s], Counter = [%s], some AMI events...", ami.servername, peer.peername, peer.status, peer.time, counter)
		self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, sms = peer.status, time = peer.time, _action = counter)
		
	def handlerEventDongleNewUSSD(self, ami, event):                
		log.debug("Server %s :: Processing Event EventDongleNewUSSD..." % ami.servername)

		peer = GenericObject("User/Peer")
		peer.peername = event.get('device')
		peer.status  = "incom. ussd"
		peer.channeltype = "Dongle"
		peer.channel  = '%s/%s' % (peer.channeltype, peer.peername)  
		peer.time        = time.time()
		counter = 'increaseUSSDIncom'
		
	##	log.warning("Server %s :: DongleNewUSSD [%s], Status = [%s], Time = [%s], Counter = [%s], some AMI events...", ami.servername, peer.peername, peer.status, peer.time, counter)
		self._updatePeer(ami.servername, channeltype = peer.channeltype, peername = peer.peername, sms = peer.status, time = peer.time, _action = counter)
		
	def handlerEventNewchannel(self, ami, event):
		log.debug("Server %s :: Processing Event Newchannel..." % ami.servername)
		server   = self.servers.get(ami.servername)
		uniqueid = event.get('uniqueid')
		channel  = event.get('channel')
		
#		log.debug("Server %s :: Processing Event Newchannel... uniqueid [%s], channel [%s] " % (ami.servername, uniqueid, channel))
		
		self._createChannel(
			ami.servername,
			uniqueid     = uniqueid,
			channel      = channel,
			state        = event.get('channelstatedesc', event.get('state')),
#			state        = event.get('channelstatedesc', event.get('state'), event.get('channelstate')),
			calleridnum  = event.get('calleridnum'),
			calleridname = event.get('calleridname'),
			_log         = "-- Newchannel"
		)
		
	def handlerEventNewstate(self, ami, event):
		log.debug("Server %s :: Processing Event Newstate..." % ami.servername)
		server       = self.servers.get(ami.servername)		
		uniqueid     = event.get('uniqueid')
		channel      = event.get('channel')
		state        = event.get('channelstatedesc', event.get('state'))
		calleridnum  = event.get('calleridnum', event.get('callerid'))
		calleridname = event.get('calleridname')
		
		self._updateChannel(
			ami.servername,
			uniqueid     = uniqueid,
			channel      = channel,
			state        = state,
			calleridnum  = calleridnum,
			calleridname = calleridname,
			_log         = "-- State changed to %s" % state
		)
		
	def handlerEventRename(self, ami, event):
		log.debug("Server %s :: Processing Event Rename..." % ami.servername)
		uniqueid = event.get('uniqueid')
		channel  = event.get('channel')
		newname  = event.get('newname')
		
		self._updateChannel(ami.servername, uniqueid = uniqueid, channel = newname, _log = "Channel %s renamed to %s" % (channel, newname))
		bridgekey = self._locateBridge(ami.servername, uniqueid = uniqueid)
		if bridgekey:
			if uniqueid == bridgekey[0]:
				self._updateBridge(ami.servername, uniqueid = bridgekey[0], bridgeduniqueid = bridgekey[1], channel = newname, _log = "Channel %s renamed to %s" % (channel, newname))
			else:
				self._updateBridge(ami.servername, uniqueid = bridgekey[0], bridgeduniqueid = bridgekey[1], bridgedchannel = newname, _log = "Channel %s renamed to %s" % (channel, newname))
				
	def handlerEventMasquerade(self, ami, event):
		log.debug("Server %s :: Processing Event Masquerade..." % ami.servername)
		server        = self.servers.get(ami.servername)	
		cloneUniqueid = event.get('cloneuniqueid')
		
		if not cloneUniqueid:
			log.warn("Server %s :: Detected BUG on Asterisk. Masquerade Event does not have cloneuniqueid and originaluniqueid properties. " % ami.servername \
				+ "See https://issues.asterisk.org/view.php?id=16555 for more informations.")
			return
		
		clone = server.status.channels.get(cloneUniqueid)
		self._createChannel(
			ami.servername,
			uniqueid     = event.get('originaluniqueid'),
			channel      = event.get('original'),
			state        = event.get('originalstate'),
			calleridnum  = clone.calleridnum,
			calleridname = clone.calleridname,
			_log         = "-- Newchannel (Masquerade)"
		)
		
	def handlerEventNewcallerid(self, ami, event):
		log.debug("Server %s :: Processing Event Newcallerid..." % ami.servername)
		server       = self.servers.get(ami.servername)	
		uniqueid     = event.get('uniqueid')
		channel      = event.get('channel')
		calleridnum  = event.get('calleridnum', event.get('callerid'))
		calleridname = event.get('calleridname')
		
		self._updateChannel(
			ami.servername,
			uniqueid     = uniqueid,
			channel      = channel,
			calleridnum  = calleridnum,
			calleridname = calleridname,
			_log         = "-- Callerid updated to '%s <%s>'" % (calleridname, calleridnum)
		)
		bridgekey = self._locateBridge(ami.servername, uniqueid = uniqueid)
		if bridgekey:
			self._updateBridge(ami.servername, uniqueid = bridgekey[0], bridgeduniqueid = bridgekey[1], _log = "-- Touching Bridge...")

	def handlerEventDAHDIChannel(self, ami, event):
		log.debug("Server %s :: Processing Event DAHDIChannel..." % ami.servername)
		server       = self.servers.get(ami.servername)
		channel      = event.get('channel')
		uniqueid     = event.get('uniqueid')
##		dahdispan  = event.get('dahdispan')
		dahdichannel = event.get('dahdichannel')
		
		channeltype  = 'DAHDI'
		peername     = dahdichannel

		## log.warning("Server %s :: Channel [%s], DahdiSpan [%s], DahdiChannel [%s], Peername [%s], Uniqueid [%s], some AMI events...", ami.servername, channel, dahdispan, dahdichannel, peername, uniqueid)
		self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, uniqueid = uniqueid, _action = 'increaseDahdiCallCounter')
		
	def handlerEventHangup(self, ami, event):
		log.debug("Server %s :: Processing Event Hangup..." % ami.servername)
		server   = self.servers.get(ami.servername)
		uniqueid = event.get('uniqueid')
		channel  = event.get('channel')
		
		self._removeChannel(
			ami.servername,
			uniqueid = uniqueid,
			channel  = channel,
			_log     = "-- Hangup"
		)
		
		# Detect QueueCall
		queueCall = server.status.queueCalls.get(uniqueid)
		if queueCall:
			log.debug("Server %s :: Queue update, call hangup: %s -> %s", ami.servername, queueCall.client.get('queue'), uniqueid)
			del server.status.queueCalls[uniqueid]
			if queueCall.member:
				self.http._addUpdate(servername = ami.servername, action = "RemoveQueueCall", uniqueid = uniqueid, queue = queueCall.client.get('queue'), location = queueCall.member.get('location'))
				queue = server.status.queues.get(queueCall.client.get('queue'))
				queue.completed += 1
				self.http._addUpdate(servername = ami.servername, subaction = 'Update', **queue.__dict__.copy())
			if logging.DUMPOBJECTS:
				log.debug("Object Dump:%s", queueCall)
		# Detect QueueClient
		for qname, clientuniqueid in server.status.queueClients.items():
			if clientuniqueid == uniqueid:
				self._updateQueue(ami.servername, queue = qname, event = "Leave", uniqueid = uniqueid, _log = "By Channel Hangup")
		
	def handlerEventDial(self, ami, event):
		log.debug("Server %s :: Processing Event Dial..." % ami.servername)
		server   = self.servers.get(ami.servername)
		subevent = event.get('subevent', "begin")
		if subevent.lower() == 'begin':
			log.debug("Server %s :: Processing Event Dial -> SubEvent Begin..." % ami.servername)
			self._createBridge(
				ami.servername,
				uniqueid        = event.get('uniqueid', event.get('srcuniqueid')),
				channel         = event.get('channel', event.get('source')),
				bridgeduniqueid = event.get('destuniqueid'),
				bridgedchannel  = event.get('destination'),
				status          = 'Dial',
				dialtime        = time.time(),
				_log            = '-- Dial Begin'
			)
		elif subevent.lower() == 'end':
			log.debug("Server %s :: Processing Event Dial -> SubEvent End..." % ami.servername)
			bridgekey = self._locateBridge(ami.servername, uniqueid = event.get('uniqueid'))
			if bridgekey:
				self._removeBridge(ami.servername, uniqueid = bridgekey[0], bridgeduniqueid = bridgekey[1], _log = "-- Dial End")
				
			# Detect QueueCall
			uniqueid = event.get('uniqueid', event.get('srcuniqueid'))
			queueCall = server.status.queueCalls.get(uniqueid)
			if queueCall:
				queueCall.link = False
				if queueCall.member:
					log.debug("Server %s :: Queue update, client -> member call unlink: %s -> %s -> %s", ami.servername, queueCall.client.get('queue'), uniqueid, queueCall.member.get('location'))
					self.http._addUpdate(servername = ami.servername, action = "RemoveQueueCall", uniqueid = uniqueid, queue = queueCall.client.get('queue'), location = queueCall.member.get('location'))
					if logging.DUMPOBJECTS:
						log.debug("Object Dump:%s", queueCall)
		else:
			log.warning("Server %s :: Unhandled Dial SubEvent %s", ami.servername, subevent)
	
	def handlerEventLink(self, ami, event):
		log.debug("Server %s :: Processing Event Link..." % ami.servername)
		server          = self.servers.get(ami.servername)
		uniqueid        = event.get('uniqueid1')
		channel         = event.get('channel1')
		bridgeduniqueid = event.get('uniqueid2')
		bridgedchannel  = event.get('channel2')
		callerid        = event.get('callerid1')
		bridgedcallerid = event.get('callerid2')
		
		bridgekey = self._locateBridge(ami.servername, uniqueid = uniqueid, bridgeduniqueid = bridgeduniqueid)
		if bridgekey:
			linktime = server.status.bridges.get(bridgekey).linktime
			self._updateBridge(
				ami.servername,
				uniqueid        = uniqueid, 
				bridgeduniqueid = bridgeduniqueid,
				status          = 'Link',
				linktime        = [linktime, time.time()][linktime == 0],
				_log            = "-- Status changed to Link"
			)
		else:
			self._createBridge(
				ami.servername,
				uniqueid        = uniqueid, 
				bridgeduniqueid = bridgeduniqueid,
				channel         = channel,
				bridgedchannel  = bridgedchannel,
				status          = 'Link',
				linktime        = time.time(),
				_log            = "-- Link"
			)
		
		# Detect QueueCall
		queueCall = server.status.queueCalls.get(uniqueid)
		if queueCall:
			queuename = queueCall.client.get('queue')
			location  = bridgedchannel.rsplit('-', 1)[0]
			member    = None
			for location in [location, "%s/n" % location]:
				member = server.status.queueMembers.get((queuename, location))
				if member:
					log.debug("Server %s :: Queue update, client -> member call link: %s -> %s -> %s", ami.servername, queuename, uniqueid, location)
					queueCall.member  = member.__dict__
					queueCall.link    = True
					queueCall.seconds = int(time.time() - queueCall.starttime) 
					self.http._addUpdate(servername = ami.servername, **queueCall.__dict__.copy())
					if logging.DUMPOBJECTS:
						log.debug("Object Dump:%s", queueCall)
					break
		
	def handlerEventUnlink(self, ami, event):
		log.debug("Server %s :: Processing Event Unlink..." % ami.servername)
		server          = self.servers.get(ami.servername)
		uniqueid        = event.get('uniqueid1')
		channel         = event.get('channel1')
		bridgeduniqueid = event.get('uniqueid2')
		bridgedchannel  = event.get('channel2')
		self._updateBridge(
			ami.servername, 
			uniqueid        = uniqueid, 
			bridgeduniqueid = bridgeduniqueid,
			channel         = channel,
			bridgedchannel  = bridgedchannel,
			status          = 'Unlink',
			_log            = "-- Status changed to Unlink"
		)
		
		# Detect QueueCall
		queueCall = server.status.queueCalls.get(uniqueid)
		if queueCall:
			queueCall.link = False
			if queueCall.member:
				log.debug("Server %s :: Queue update, client -> member call unlink: %s -> %s -> %s", ami.servername, queueCall.client.get('queue'), uniqueid, queueCall.member.get('location'))
				self.http._addUpdate(servername = ami.servername, action = "RemoveQueueCall", uniqueid = uniqueid, queue = queueCall.client.get('queue'), location = queueCall.member.get('location'))
				if logging.DUMPOBJECTS:
					log.debug("Object Dump:%s", queueCall)
	
	def handlerEventBridge(self, ami, event):
		log.debug("Server %s :: Processing Event Bridge..." % ami.servername)
		self.handlerEventLink(ami, event)
	
	# Meetme Events
	def handlerEventMeetmeJoin(self, ami, event):
		log.debug("Server %s :: Processing Event MeetmeJoin..." % ami.servername)
		meetme = event.get("meetme")
		
		self._updateMeetme(
			ami.servername,
			meetme  = meetme,
			addUser = {
				'uniqueid'     : event.get('uniqueid'), 
				'channel'      : event.get('channel'),
				'usernum'      : event.get("usernum"), 
				'calleridnum'  : event.get("calleridnum"), 
				'calleridname' : event.get("calleridname"),
			}  
		)
		
	# Meetme Events
	def handlerEventMeetmeLeave(self, ami, event):
		log.debug("Server %s :: Processing Event MeetmeLeave..." % ami.servername)
		meetme = event.get("meetme")
		
		self._updateMeetme(
			ami.servername,
			meetme  = meetme,
			removeUser = {
				'uniqueid'     : event.get('uniqueid'), 
				'channel'      : event.get('channel'),
				'usernum'      : event.get("usernum"), 
				'calleridnum'  : event.get("calleridnum"), 
				'calleridname' : event.get("calleridname"),
			}  
		)
		
	# Parked Calls Events
	def handlerEventParkedCall(self, ami, event):
		log.debug("Server %s :: Processing Event ParkedCall..." % ami.servername)
		self._createParkedCall(ami.servername, **event)
		
	def handlerEventUnParkedCall(self, ami, event):
		log.debug("Server %s :: Processing Event UnParkedCall..." % ami.servername)
		self._removeParkedCall(ami.servername, _log = "(Unparked)", **event)
	
	def handlerEventParkedCallTimeOut(self, ami, event):
		log.debug("Server %s :: Processing Event ParkedCallTimeOut..." % ami.servername)
		self._removeParkedCall(ami.servername, _log = "(Timeout)", **event)
	
	def handlerEventParkedCallGiveUp(self, ami, event):
		log.debug("Server %s :: Processing Event ParkedCallGiveUp..." % ami.servername)
		self._removeParkedCall(ami.servername, _log = "(Giveup)", **event)
		
	# Queue Events
	def handlerEventQueueMemberAdded(self, ami, event):
		log.debug("Server %s :: Processing Event QueueMemberAdded..." % ami.servername)
		self._updateQueue(ami.servername, **event)
	
	def handlerEventQueueMemberRemoved(self, ami, event):
		log.debug("Server %s :: Processing Event QueueMemberRemoved..." % ami.servername)
		self._updateQueue(ami.servername, **event)
	
	def handlerEventJoin(self, ami, event):
		log.debug("Server %s :: Processing Event Join..." % ami.servername)
		self._updateQueue(ami.servername, **event)
		
	def handlerEventLeave(self, ami, event):
		log.debug("Server %s :: Processing Event Leave..." % ami.servername)
		self._updateQueue(ami.servername, **event)
		
	def handlerEventQueueCallerAbandon(self, ami, event):
		log.debug("Server %s :: Processing Event QueueCallerAbandon..." % ami.servername)
		self._updateQueue(ami.servername, **event)
		
	def handlerEventQueueMemberStatus(self, ami, event):
#		log.debug("Server %s :: Processing Event QueueMemberStatus... [%s]" % (ami.servername, event))
		log.debug("Server %s :: Processing Event QueueMemberStatus..." % ami.servername)
		self._updateQueue(ami.servername, **event)
		
	def handlerEventQueueMemberPaused(self, ami, event):
		log.debug("Server %s :: Processing Event QueueMemberPaused..." % ami.servername)
		
		server   = self.servers.get(ami.servername)
		queue    = event.get('queue')
#		location = event.get('location')
		location = event.get('location', event.get('interface'))
		memberid = (queue, location)
		member   = server.status.queueMembers.get(memberid)
		
		if member:
			event['callstaken'] = member.callstaken
			event['lastcall']   = member.lastcall
			event['penalty']    = member.penalty
			event['status']     = member.status
			self._updateQueue(ami.servername, **event)
		else:
			log.warning("Server %s :: Queue Member does not exists: %s -> %s", ami.servername, queue, memberid[1])
	
	## Monitor
	def handlerEventMonitorStart(self, ami, event):
		log.debug("Server %s :: Processing Event MonitorStart..." % ami.servername)
		self._updateChannel(ami.servername, uniqueid = event.get('uniqueid'), channel = event.get('channel'), monitor = True, _log = "-- Monitor Started")
	
	def handlerEventMonitorStop(self, ami, event):
		log.debug("Server %s :: Processing Event MonitorStop..." % ami.servername)
		self._updateChannel(ami.servername, uniqueid = event.get('uniqueid'), channel = event.get('channel'), monitor = False, _log = "-- Monitor Stopped")
	
	# Khomp Events
	def handlerEventAntennaLevel(self, ami, event):
		log.debug("Server %s :: Processing Event AntennaLevel..." % ami.servername)
		channel = event.get('channel')
		signal  = event.get('signal')
		channeltype, peername = channel.split('/', 1)
		self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = 'Signal: %s' % signal)
		
	def handlerEventBranchOnHook(self, ami, event):
		log.debug("Server %s :: Processing Event BranchOnHook..." % ami.servername)
		channel = event.get('channel')
		channeltype, peername = channel.split('/', 1)
		self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = "On Hook")
		
	def handlerEventBranchOffHook(self, ami, event):
		log.debug("Server %s :: Processing Event BranchOffHook..." % ami.servername)
		channel = event.get('channel')
		channeltype, peername = channel.split('/', 1)
		self._updatePeer(ami.servername, channeltype = channeltype, peername = peername, status = "Off Hook")
		
	def handlerEventChanSpyStart(self, ami, event):
		log.debug("Server %s :: Processing Event ChanSpyStart..." % ami.servername)
		spyeechannel = event.get('spyeechannel')
		spyerchannel = event.get('spyerchannel')
		channel      = self._lookupChannel(ami.servername, spyeechannel)
		
		if channel:
			self._updateChannel(ami.servername, uniqueid = channel.uniqueid, spy = True)
		
	def handlerEventChanSpyStop(self, ami, event):
		log.debug("Server %s :: Processing Event ChanSpyStop..." % ami.servername)
		spyeechannel = event.get('spyeechannel')
		channel      = self._lookupChannel(ami.servername, spyeechannel)
		
		if channel:
			self._updateChannel(ami.servername, uniqueid = channel.uniqueid, spy = False)
		
##
## Daemonizer
##
#MONAST_PID_FILE = '%s/.monast.pid' % sys.argv[0].rsplit('/', 1)[0]
MONAST_PID_FILE = '/var/run/monast.pid'
def createDaemon():
	if os.fork() == 0:
		os.setsid()
		if os.fork() == 0:
			os.chdir(os.getcwd())
			os.umask(0)
		else:
			os._exit(0)
	else:
		os._exit(0)
	
	pid = os.getpid()
	print '\nMonast daemonized with pid %s' % pid
	f = open(MONAST_PID_FILE, 'w')
	f.write('%s' % pid)
	f.close()

##
## Main
##
def RunMonast(MM):

	global logging
	global log

	opt = optparse.OptionParser()
	opt.add_option('--config',
		dest    = "configFile",
		default = '/etc/monast.conf',
		help    = "use this config file instead of /etc/monast.conf"
	)
	opt.add_option('--info',
		dest   = "info",
		action = "store_true",
		help   = "display INFO messages"
	)
	opt.add_option('--debug',
		dest   = "debug",
		action = "store_true",
		help   = "display DEBUG messages"
	)
	opt.add_option('--debug-ami',
		dest = "debugAMI",
		action = "store_true",
		help = "display DEBUG messages for AMI Factory"
	)
	opt.add_option('--dump-objects',
		dest   = "dump_objects",
		action = "store_true",
		help   = "display DEBUG messages"
	)
	opt.add_option('--colored',
		dest   = "colored",
		action = "store_true",
		help   = "display colored log messages"
	)
	opt.add_option('--daemon',
		dest   = "daemon",
		action = "store_true",
		help   = "deamonize (fork in background)"
	)
	opt.add_option('--logfile',
		dest    = "logfile",
		default = "/var/log/monast.log",
		help    = "use this log file instead of /var/log/monast.log"
	)
	opt.add_option('--stop',
		dest   = "stop",
		action = "store_true",
		help   = "stop Monast (only in daemon mode)"
	)
	
	(options, args) = opt.parse_args()

	if options.stop:
		if os.path.exists(MONAST_PID_FILE):
			pid = open(MONAST_PID_FILE, 'r').read()
			os.unlink(MONAST_PID_FILE)
			os.popen("kill -TERM %d" % int(pid))
			print "Monast stopped..."
			sys.exit(0)
		else:
			print "Monast is not running as daemon..."
			sys.exit(1)
		sys.exit(2)
	
	if options.daemon:
		createDaemon()
		
	if options.info:
		logging.getLogger("").setLevel(logging.INFO)
	
	if options.debug:
		logging.getLogger("").setLevel(logging.DEBUG)
		#logging.FORMAT = "[%(asctime)s] %(levelname)-8s :: [%(module)s.%(funcName)s] :: %(message)s"
		
	if options.debugAMI:
		manager.log.setLevel(logging.DEBUG)
	else:
		manager.log.setLevel(logging.WARNING)
		
	if options.dump_objects:
		logging.DUMPOBJECTS = True
		
	if options.colored:
		logging.COLORED = True
		logging.FORMAT  = "[%(asctime)s] %(levelname)-19s :: %(message)s"
		#if options.debug:
		#	logging.FORMAT = "[%(asctime)s] %(levelname)-19s :: [%(module)s.%(funcName)s] :: %(message)s"
		
	_colorFormatter = ColorFormatter(logging.FORMAT, '%a %b %d %H:%M:%S %Y')
	_logHandler     = None
	if options.daemon:
		logfile = options.logfile
		if not logfile:
			logfile = '/var/log/monast.log'
		_logHandler = logging.FileHandler(logfile)
	else:
		_logHandler = logging.StreamHandler(sys.stdout)
	_logHandler.setFormatter(_colorFormatter)
	logging.getLogger("").addHandler(_logHandler)
	
	global log
	log = logging.getLogger("Monast")
	
	if not os.path.exists(options.configFile):
		print '  Config file "%s" not found.' % options.configFile
		print '  Run "%s --help" for help.' % sys.argv[0]
		sys.exit(1)
		
	monast = MM(options.configFile)
	reactor.run()
	
	_logHandler.close()

if __name__ == '__main__':
	RunMonast(Monast)
