
/*
*
* Kivko Wlad mail@kivko.nsk.ru updates https://yadi.sk/d/PVRLfxQXfNnuZ
* Add chanel_dongle (http://wiki.e1550.mobi/doku.php?id=Main%20page)
* Copyright (c) 2018 ver. 0.7.3.30.04 b
*
* Copyright (c) 2008-2011, Diego Aguirre
* All rights reserved.
* 
* Redistribution and use in source and binary forms, with or without modification,
* are permitted provided that the following conditions are met:
* 
*     * Redistributions of source code must retain the above copyright notice, 
*       this list of conditions and the following disclaimer.
*     * Redistributions in binary form must reproduce the above copyright notice, 
*       this list of conditions and the following disclaimer in the documentation 
*       and/or other materials provided with the distribution.
*     * Neither the name of the DagMoller nor the names of its contributors
*       may be used to endorse or promote products derived from this software 
*       without specific prior written permission.
* 
* THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
* ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED 
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
* IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
* INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
* BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, 
* DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF 
* LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE 
* OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED 
* OF THE POSSIBILITY OF SUCH DAMAGE.
*/

// Global Vars
var MONAST_COOKIE_KEY = "MONASTCOOKIE";

// Global Functions
String.prototype.trim = function() { return this.replace(/^\s*/, "").replace(/\s*$/, ""); };

// Monast
var Monast = {
	// Globals
	_contextMenu: new YAHOO.widget.Menu("ContextMenu"),
	
	MONAST_CALL_TIME               : true,
	MONAST_BLINK_ONCHANGE          : true,
	MONAST_BLINK_COUNT             : 3,
	MONAST_BLINK_INTERVAL          : 200,
	MONAST_KEEP_CALLS_SORTED       : true,
	MONAST_KEEP_PARKEDCALLS_SORTED : true,
	MONAST_DONGLE_REST             : 40000, // Раз в 10 сек
	MONAST_DONGLE_CHECK            : 50, 		// идем по таблице
	MONAST_DONGLE_TIME_REGISR      : 120, 	// время регистраци донгла в сети и астериске после рестарта
	NEED_DONGLE_RESTART            : false,
	DONGLE_RESTART_INTERVAL_ID     : null,
	DONGLE_CHECK_HASH              : new Hash(),
	DONGLE_RESTART_HASH            : new Hash(),
	
	COLORS: {
		BLACK  : "#000000",
		WHITE  : "#ffffff",
		RED    : "#ffb0b0", 
		YELLOW : "#ffffb0", 
		ORANGE : "#ff9933", 
		BLUE   : "#99ffff", 
		GREEN  : "#b0ffb0", 
		GRAY   : "#dddddd"
	},
	
	// Colors
	getColor: function (status)
	{
		status = status.toLowerCase().trim();
		switch (status)
		{
			// RED
			case 'down':
			case 'disconnect':
			case '----':
			// case 'unregistered':
			case 'unreachable':
			case 'unknown':
			case 'unavailable':
			// case 'unregister':
			case 'not connec':
			case 'not connected':
			case 'not initialized':
			case 'not initializ': 
			// case 'gsm not registered': 
			// case 'gsm not regis':
			case 'stopped':  
			case 'invalid':
			case 'busy':
			case 'logged out':
			case 'red alarm':
				return Monast.COLORS.RED;
			
			// YELLOW
			case 'active': 	
			case 'answer':
			case 'outgoing':
			case 'ring':
			case 'ringing':
			case 'ring, in use':
			case 'in use':
			case 'incoming':
			case 'used':
			case 'dial':
			case 'dialing':
			case 'lagged':
			case 'on hold':
			case 'off hook':
			case 'yellow alarm':
			case 'dnd enabled':
			case 'waiting':
			case 'held': 
			case 'hold':
			case 'sms - sent':   
			case 'ussd - sent':
				return Monast.COLORS.YELLOW;
			
			// BLUE
			case 'blue alarm':
			case 'sms':
			case 'incoming sms':
			case 'incom. sms':
			case 'incom. ussd':
			case 'excellent':
			case 'good':
				return Monast.COLORS.BLUE;
				
			// GREEN
			case '--':
			case '---':
			case 'up':
			case 'link':
			case 'registered':
			case 'register':
			case 'reachable':
			case 'connect':
			case 'unmonitored':
			case 'not in use':
			case 'logged in':
			case 'no alarm':
			case 'on hook':
			case 'free':
			case 'initialize':
			case 'normal':
				return Monast.COLORS.GREEN;

			// RED
			case 'sms - notsent':
			case 'ussd - notsent':
			case 'bad':
			case 'very bad':
			case 'not found':
			case 'loaded': 
			case 'removal':
			case 'port fail':
				return Monast.COLORS.RED;
				
			// ORANGE
			case 'manually restart':
			case 'super':
			case 'unregistered':
			case 'unregister':
			case 'gsm not registered':
			case 'gsm not regis':
			case 'alarm':
				return Monast.COLORS.ORANGE;
				
		}
		// GSM Signal
		if (status.indexOf('signal') != -1)
		{
			var level = status.replace('%', '').replace('signal: ', '');
			if (level >= 70)
				return Monast.COLORS.GREEN;
			if (level >= 40 && level < 70)
				return Monast.COLORS.YELLOW;
			if (level < 40)
				return Monast.COLORS.RED;
		}

		// GSM Dongle
		//      до -75 дБм   отличный сигнал
		//	от -75 дБм до -85 дБм хороший сигнал
		//	от -85 дБм до -95 дБм   удовлетворительный сигнал
		//	от -95 дБм до -100 дБм   плохой сигнал
		//	от -100 дБм  очень плохой сигнал, либо отсутствует

		if (status.indexOf('-') != -1)
		{
			var signal = Number(status);

			if (signal == -51)			// подозрительно отличный сигнал
				return Monast.COLORS.ORANGE;
			if (signal >= -75)
				return Monast.COLORS.BLUE;	// отличный сигнал
			if (signal >= -85 && signal < -75)
				return Monast.COLORS.BLUE;	// хороший сигнал

			if (signal >= -95 && signal < -85)
				return Monast.COLORS.GREEN;	// удовлетворительный сигнал

			if (signal >= -100 && signal < -95)
				return Monast.COLORS.RED;	// плохой сигнал
			if (signal  < -100)
				return Monast.COLORS.RED;	// очень плохой сигнал, либо отсутствует

			var level = status.replace('|&#\d+;|', '');
			if (level  == "--")
				return Monast.COLORS.GREEN;

			return Monast.COLORS.ORANGE
		}

		// Other Alarms
		if (status.indexOf('alarm') != -1)
			return Monast.COLORS.ORANGE;
		
		return Monast.COLORS.GRAY;
	},
	blinkBackground: function (id, color)
	{
		if (!Monast.MONAST_BLINK_ONCHANGE)
		{
			if ($(id)) { $(id).style.backgroundColor = color; }
			return;
		}
		
		var t = 0;
		for (i = 0; i < Monast.MONAST_BLINK_COUNT; i++)
		{
			$A([Monast.COLORS.WHITE, color]).each(function (c) {
				t += Monast.MONAST_BLINK_INTERVAL;
				setTimeout("if ($('" + id + "')) { $('" + id + "').style.backgroundColor = '" + c + "'; }", t);
			});
		}
	},
	blinkText: function (id)
	{
		if (!Monast.MONAST_BLINK_ONCHANGE)
			return;
		
		var t = 0;
		for (i = 0; i < Monast.MONAST_BLINK_COUNT; i++)
		{
			$A([Monast.COLORS.WHITE, Monast.COLORS.BLACK]).each(function (c) {
				t += Monast.MONAST_BLINK_INTERVAL;
				setTimeout("if ($('" + id + "')) { $('" + id + "').style.color = '" + c + "'; }", t);
			});
		}
	},
	
	// Users/Peers
	userspeers: new Hash(),
	processUserpeer: function (u)
	{
		u.id          = md5(u.channel);
		u.status      = u.dnd && u.status == "No Alarm" ? "DND Enabled" : u.status;
		u.statuscolor = this.getColor(u.status);
		u.callscolor  = u.calls > 0 ? this.getColor('in use') : this.getColor('not in use');
		u.latency     = u.time == -1 ? "--" : u.time + " ms";

		if (Object.isUndefined(this.userspeers.get(u.id)))
		{
			/* wlads */
			if (u.channeltype == 'Dongle')
			{
				var clone           = Monast.buildClone("Template::UserpeerDongle", u.id);
			}
			else
			{
				var clone           = Monast.buildClone("Template::Userpeer", u.id);
			}
			clone.className     = "peerTable";
			clone.oncontextmenu = function () { Monast.showUserpeerContextMenu(u.id); return false; };
			
			var group = "";
			if (!Object.isUndefined(u.peergroup))
				group = "-" + u.peergroup;
			
			$('fieldset-' + u.channeltype + group).appendChild(clone);
			
			// Drag & Drop
			this.createDragDrop(u.id, this.dd_userPeerDrop, ['peerTable']);
		}
/* wlads */

		if (u.channeltype == 'Dongle')
		{			
			u.latency     = u.level == -1 ? "--" : u.level;

			if (u.statuscolor == Monast.COLORS.RED)
			{
				u.signalscolor = Monast.COLORS.GRAY;
				u.smscolor = Monast.COLORS.RED;
				u.callscolor  = Monast.COLORS.RED;
			}
			else if (u.alarm != '--')  									/* Alarm  */
			{
				u.signalscolor = this.getColor(u.alarm);
				u.smscolor = this.getColor(u.sms);
			/*	u.smscolor = this.getColor(u.alarm); */
			}
			else
			{
				// u.signalscolor = this.getColor(u.level);
				u.signalscolor = this.getColor(u.quality);
				u.smscolor = this.getColor(u.sms);
			}
			
			if ((u.statuscolor == Monast.COLORS.YELLOW && u.calls == "0" && u.smscolor != Monast.COLORS.YELLOW) || (u.statuscolor == Monast.COLORS.ORANGE && u.calls == "0" && u.smscolor != Monast.COLORS.YELLOW))
			{
				u.latency = "We need smart restart Dongle";
			}
			else
			{
			/*	u.latency     = u.time == -1 ? "--" : u.time;   */
				u.latency     = u.level == -1 ? "--" : u.level;
			}
		}		
		else
		{
			if (u.statuscolor == Monast.COLORS.RED) /* а пир то живой ? */
			{               
				u.callscolor  = Monast.COLORS.RED;
			}
		}


// всплывающие сообщения
		var old = this.userspeers.get(u.id);
		Object.keys(u).each(function (key) {
			var elid = u.id + '-' + key;
			if ($(elid))
			{	
				switch (key)
				{
					case "statuscolor":
						$(elid).style.backgroundColor = u[key];
						if (u.channeltype == 'Dongle')
						{
		
							if ((u.statuscolor == Monast.COLORS.YELLOW && u.calls == "0") || (u.statuscolor == Monast.COLORS.ORANGE && u.calls == "0"))      
							{
								$(elid).title = "We need smart restart Dongle";
							}
							else
							{
								if ((u.reboot == "0") && (u.portfail == "0") && (u.alarmcount == "0"))
								{
									$(elid).title = "Status: " + u.status;
								}
								else
								{
									if (u.portfail == "0")
									{
										if (u.alarm == '--')
										{
											$(elid).title = "Status: " + u.status + " :: " + "Reboot: " + u.reboot + " :: " + "AlarmCount: " + u.alarmcount;
										}
										else
										{
											$(elid).title = "Status: " + u.status + " :: " + "Reboot: " + u.reboot + " :: " + "AlarmCount: " + u.alarmcount + " :: " + "Set Alarm: " + u.alarm;
										}
									}
									else
									{
										if (u.alarm == '--')
										{
											$(elid).title = "Status: " + u.status + " :: " + "Reboot: " + u.reboot + " :: " + "PortFail: " + u.portfail + " :: " + "AlarmCount: " + u.alarmcount;
										}
										else
										{
											$(elid).title = "Status: " + u.status + " :: " + "Reboot: " + u.reboot + " :: " + "PortFail: " + u.portfail + " :: " + "AlarmCount: " + u.alarmcount + " :: " + "Set Alarm: " + u.alarm;
										}
									}
								}
							}
						}
						else
						{
							if (u.time == '-1')
							{
								$(elid).title = "Status: " + u.status;
							}
							else
							{
								$(elid).title = "Status: " + u.status + " :: Latency: " + u.time + " ms";
						/*		$(elid).title = "Status: " + u.status + " :: Latency1: " + u.level + " ms"; */
							}
						}

						if (old && old.status != u.status)
							Monast.blinkBackground(elid, u.statuscolor);
						break;

					case "smscolor":
						$(elid).style.backgroundColor = u[key];
						if (u.channeltype == 'Dongle')
						{ 
							if ((u.statuscolor == Monast.COLORS.YELLOW && u.calls == "0") || (u.statuscolor == Monast.COLORS.ORANGE && u.calls == "0"))
							{
								$(elid).title = "We need smart restart Dongle";
							}
							else
							{
								if (((u.ussdsend == "0") && (u.ussdincom == "0")) && ((u.smssend != "0") || (u.smserror != "0") || (u.smsincom != "0")))
								{
									$(elid).title = "SMS sent: " + u.smssend + " :: " + "SMS sent error: " + u.smserror + " :: " + "SMS incom: " + u.smsincom;
								}
								
								else if (((u.smssend == "0") && (u.smserror == "0") && (u.smsincom == "0")) && ((u.ussdsend != "0") || (u.ussdincom != "0")))
								{
									$(elid).title = "USSD sent: " + u.ussdsend + " :: " + "USSD incom: " + u.ussdincom;
								}
								else if (((u.smssend == "0") && (u.smserror == "0") && (u.smsincom == "0")) && ((u.ussdsend == "0") && (u.ussdincom == "0")))
								{
									if ((u.statuscolor == Monast.COLORS.YELLOW && u.calls == "0") || (u.statuscolor == Monast.COLORS.ORANGE && u.calls == "0"))
									{
										$(elid).title = "We need smart restart Dongle";
									}
									else
									{
										if (u.level == '--')
										{                 
											$(elid).title = "Status: " + u.status
										}
										else
										{
											$(elid).title = "Status: " + u.status + " :: " + Monast.viewMesageSignal(u.level);
										}
									}
								}
								else
								{
									$(elid).title = "SMS sent: " + u.smssend + " :: " + "SMS sent error: " + u.smserror + " :: " + "SMS incom: " + u.smsincom + " :: " + "USSD sent: " + u.ussdsend + " :: " + "USSD incom: " + u.ussdincom;
								}
							}
						}
						else
						{
							$(elid).title = "Status: " + u.status + " :: Latency: " + u.time + " ms";
						}

						if (old && old.sms != u.sms)
							Monast.blinkBackground(elid, u.smscolor);
						break;
					
					case "signalscolor":
						$(elid).style.backgroundColor = u[key];
						if (u.channeltype == 'Dongle')
						{
		/* wlads */
							if ((u.statuscolor == Monast.COLORS.YELLOW && u.calls == "0") || (u.statuscolor == Monast.COLORS.ORANGE && u.calls == "0"))
							{
								$(elid).title = "We need smart restart Dongle";
							}
							else
							{
								if (u.level == '--')
								{                 
									$(elid).title = "Status: " + u.status
								}
								else
								{
									$(elid).title = "Status: " + u.status + " :: " + Monast.viewMesageSignal(u.level);
								}
							}
						}
						else
						{                
							$(elid).title = "Status: " + u.status + " :: Latency: " + u.time + " ms";
						}
						if (old && old.quality != u.quality)
							Monast.blinkBackground(elid, u.signalscolor);

					/*	if (old && old.level != u.level)
							Monast.blinkBackground(elid, u.signalscolor); */

						break;
						
					case "callscolor":
						$(elid).style.backgroundColor = u[key];
						if (u.channeltype == 'Dongle')
						{
							$(elid).title = "Outgoning: " + u.calloutcom + " :: " + "Outgoning not answer: " + (u.calldialing - u.calloutcom) + " :: " + "Incoming: " + u.callincom;
						}
						else
						{
							$(elid).title = u.calls + " call(s)";
						}
						if (old && old.calls != u.calls)
							Monast.blinkBackground(elid, u.callscolor);
						break;
	
					default:
						$(elid).innerHTML = u[key];
						break;
				}				
			}
		});

		this.userspeers.set(u.id, u);
	},
	dd_userPeerDrop: function (e, id)
	{
		var peer = Monast.userspeers.get(this.id);
		switch ($(id).className)
		{
			case "peerTable":
				var dst = Monast.userspeers.get(id);
				var obj = {fromcallerid: peer.callerid, fromchannel: peer.channel, tocallerid: dst.callerid, tochannel: dst.channel};
				Monast.doConfirm(
					new Template($("Template::Userpeer::Form::Originate::InternalCall").innerHTML).evaluate(obj),
					function () {
						new Ajax.Request('action.php', 
						{
							method: 'get',
							parameters: {
								reqTime: new Date().getTime(),
								action: Object.toJSON({action: 'Originate', from: obj.fromchannel, to: obj.tochannel, callerid: obj.fromcallerid, type: 'internalCall'})
							}
						});
					}
				);
				Monast.confirmDialog.setHeader('Originate Call');
				break;
		}
	},
	showUserpeerContextMenu: function (id)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
	
		var originateCall = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				new Template($("Template::Userpeer::Form::Originate::Dial").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Originate', from: p_oValue.channel, to: $('Userpeer::Form::Originate::Dial::To').value, callerid: p_oValue.callerid, type: 'dial'})
						}
					});
				}
			);
			Monast.confirmDialog.setHeader('Originate Call');
		};
		var viewUserpeerCalls = function (p_sType, p_aArgs, p_oValue)
		{
			var peer  = p_oValue;
			var found = false; 
			Monast.channels.keys().each(function (id) {
				var channel = Monast.channels.get(id);
				if (channel.channel.indexOf(peer.channel + "-") != -1)
				{
					found = true;
					Monast.blinkBackground(channel.id, Monast.COLORS.BLUE);
					setTimeout("if ($('" + channel.id + "')) { $('" + channel.id + "').style.backgroundColor = Monast.COLORS.WHITE; }", 10000);
				}
			});
			Monast.bridges.keys().each(function (id) {
				var bridge = Monast.bridges.get(id);
				if (bridge.channel.indexOf(peer.channel + "-") != -1 || bridge.bridgedchannel.indexOf(peer.channel + "-") != -1)
				{
					found = true;
					Monast.blinkBackground(bridge.id, Monast.COLORS.BLUE);
					setTimeout("if ($('" + bridge.id + "')) { $('" + bridge.id + "').style.backgroundColor = Monast.COLORS.WHITE; }", 10000);
				}
			});
			if (found)
			{
				if (Monast._tabPannel.get("activeIndex") == 0 && Monast._stateCookie.buttons["checkBoxTab_chanCallDiv"])
					new YAHOO.util.Scroll(navigator.userAgent.indexOf("AppleWebKit") != -1 ? document.body : document.documentElement, {scroll: {to: YAHOO.util.Dom.getXY($('chanCallDiv'))}}, 0.5).animate();
				else
					Monast._tabPannel.set("activeIndex", 3);
			}
			else
				Monast.doAlert("No Active Channels/Calls for this User/Peer.");
		};



		var DongleTestCalls = function (p_sType, p_aArgs, p_oValue)
		{
			var peer  = p_oValue;
			var found = false; 
			Monast.channels.keys().each(function (id) {
				var channel = Monast.channels.get(id);
				if (channel.channel.indexOf(peer.channel + "-") != -1)
				{
					found = true;
				}
			});
			Monast.bridges.keys().each(function (id) {
				var bridge = Monast.bridges.get(id);
				if (bridge.channel.indexOf(peer.channel + "-") != -1 || bridge.bridgedchannel.indexOf(peer.channel + "-") != -1)
				{
					found = true;
				}
			});
			if (found != true)
			{
				/* 
Wlads
					Monast.doAlert("No Active Channels/Calls for this Dongle. u.status = " + u.status + "; u.statuscolor = "+ u.statuscolor + "; u.calls = "+ u.calls + "; u.callscolor = " + u.callscolor);
				*/

				if ((u.statuscolor == Monast.COLORS.YELLOW && u.calls == "0") || (u.statuscolor == Monast.COLORS.ORANGE && u.calls == "0"))
				{
				/*	Monast.doAlert("Need restart Dongle u.callscolor = " + u.callscolor); */
 
					Monast.cliCommand("dongle restart now " + u.peername, false);

					u.callscolor = Monast.COLORS.RED; 
                                /*	Monast.doAlert("Set = u.callscolor =  " + u.callscolor); */
				}
			}
		};

		var TestSmartRestart = function (p_sType, p_aArgs, p_oValue)
		{
			var peer  = p_oValue;
			var found = false; 
			Monast.channels.keys().each(function (id) {
				var channel = Monast.channels.get(id);
				if (channel.channel.indexOf(peer.channel + "-") != -1)
				{
					found = true;
				}
			});
			Monast.bridges.keys().each(function (id) {
				var bridge = Monast.bridges.get(id);
				if (bridge.channel.indexOf(peer.channel + "-") != -1 || bridge.bridgedchannel.indexOf(peer.channel + "-") != -1)
				{
					found = true;
				}
			});

	/* wlads */
			if (document.getElementById('checkBoxSmartRestart').checked == true)
			{
				Monast.doAlert('checkBoxSmartRestart = true');
			}
			else
			{
				Monast.doAlert('checkBoxSmartRestart = false');
			}
		
		};


		var viewUserpeerInfo = function (p_sType, p_aArgs, p_oValue)
		{
			p_oValue.channelVariables = [];
			
			if (p_oValue.variables.length > 0)
			{
				p_oValue.channelVariables.push('<tr><td colspan="2"><hr></td></tr>');
				p_oValue.channelVariables.push('<tr><td colspan="2" class="key" style="text-align: center;">Channel Variables</td></tr>');
			} 
			
			p_oValue.variables.each(function (v) {
				var item = v.split('=', 2);
				p_oValue.channelVariables.push('<tr><td class="key">' + item[0] + ':</td><td>' + item[1] + '</td></tr>');
			});
			
			Monast.doAlert(new Template($("Template::Userpeer::Info").innerHTML).evaluate(p_oValue));
			$("Template::Userpeer::Info::Table").innerHTML = $("Template::Userpeer::Info::Table").innerHTML + p_oValue.channelVariables.join("\n");
		};
		var addQueueMember = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Turn this User Member of Queue \"" + p_oValue.queue.queuename + "\"?</div><br>" + new Template($("Template::Userpeer::Info").innerHTML).evaluate(p_oValue.peer),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'QueueMemberAdd', queue: p_oValue.queue.queue, location: p_oValue.peer.channel})
						}
					});
				}
			);
		};
		var delQueueMember = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Remove this User Member from Queue \"" + p_oValue.queue.queuename + "\"?</div><br>" + new Template($("Template::Userpeer::Info").innerHTML).evaluate(p_oValue.peer),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'QueueMemberRemove', queue: p_oValue.queue.queue, location: p_oValue.peer.channel})
						}
					});
				}
			);
		};
		
		var u = this.userspeers.get(id);
		var m = [
			[
				{text: "Originate Call", onclick: {fn: originateCall, obj: u}},
				{text: "View User/Peer Channels/Calls", onclick: {fn: viewUserpeerCalls, obj: u}},
				{text: "View User/Peer Info", onclick: {fn: viewUserpeerInfo, obj: u}}
			],
		];
		var addQueue = false;
		switch (u.channeltype)
		{
			case 'SIP':
				m[0].push({text: "Execute 'sip show peer " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "sip show peer " + u.peername}});
				m[0].push({text: "Execute 'sip show peers'", onclick: {fn: Monast.requestInfo, obj: "sip show peers"}});
				m[0].push({text: "Execute 'sip show user " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "sip show peer " + u.peername}});
/*				m[0].push({text: "Execute 'sip show users'", onclick: {fn: Monast.requestInfo, obj: "sip show users"}}); не безопасно */

				addQueue = true;
				break;

			case 'PJSIP':
				m[0].push({text: "Execute 'pjsip show endpoint " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "pjsip show endpoint " + u.peername}});
				m[0].push({text: "Execute 'pjsip show endpoints'", onclick: {fn: Monast.requestInfo, obj: "pjsip show endpoints"}});
				m[0].push({text: "Execute 'pjsip show aor " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "pjsip show aor " + u.peername}});
				m[0].push({text: "Execute 'pjsip show aors'", onclick: {fn: Monast.requestInfo, obj: "pjsip show aors"}});
				m[0].push({text: "Execute 'pjsip show registration " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "pjsip show registration " + u.peername}});
				m[0].push({text: "Execute 'pjsip show registrations'", onclick: {fn: Monast.requestInfo, obj: "pjsip show registrations"}});
				m[0].push({text: "Execute 'pjsip show transport " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "pjsip show transport " + u.peername}});
				m[0].push({text: "Execute 'pjsip show transports'", onclick: {fn: Monast.requestInfo, obj: "pjsip show transports"}});

				m[0].push({text: "Execute 'pjsip list endpoints'", onclick: {fn: Monast.requestInfo, obj: "pjsip list endpoints"}});
				m[0].push({text: "Execute 'pjsip list aors'", onclick: {fn: Monast.requestInfo, obj: "pjsip list aors"}});
				m[0].push({text: "Execute 'pjsip list contacts'", onclick: {fn: Monast.requestInfo, obj: "pjsip list contacts"}});	
				m[0].push({text: "Execute 'pjsip list transports'", onclick: {fn: Monast.requestInfo, obj: "pjsip list transports"}});
				m[0].push({text: "Execute 'pjsip list channels'", onclick: {fn: Monast.requestInfo, obj: "pjsip list channels"}});

				addQueue = true;
				break;
				
			case 'IAX2':
				m[0].push({text: "Execute 'iax2 show peer " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "iax2 show peer " + u.peername}});
				addQueue = true;
				break;
				
			case 'DAHDI':
				m[0].push({text: "Execute 'dahdi show status'", onclick: {fn: Monast.requestInfo, obj: "dahdi show status"}});
				m[0].push({text: "Execute 'dahdi show channels'", onclick: {fn: Monast.requestInfo, obj: "dahdi show channels"}});
				m[0].push({text: "Execute 'dahdi show version'", onclick: {fn: Monast.requestInfo, obj: "dahdi show version"}});
				m[0].push({text: "Execute 'dahdi show channel " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dahdi show channel " + u.peername}});
				break;
			case 'Dongle':
				m[0].push({text: "View 'dongle show device settings " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dongle show device settings " + u.peername}});
				m[0].push({text: "View 'dongle show device state " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dongle show device state " + u.peername}});
				m[0].push({text: "View 'dongle show device statistics " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dongle show device statistics " + u.peername}});
				m[0].push({text: "View 'dongle show devices'", onclick: {fn: Monast.requestInfo, obj: "dongle show devices"}});
				m[0].push({text: "View 'dongle discovery'", onclick: {fn: Monast.requestInfo, obj: "dongle discovery"}});
				m[0].push({text: "Execute 'dongle start " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dongle start " + u.peername}});
				m[0].push({text: "Execute 'dongle stop now " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dongle stop now " + u.peername}});
				m[0].push({text: "Execute 'dongle stop gracefully " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dongle stop gracefully " + u.peername}});
				m[0].push({text: "Execute 'dongle stop when convenient " + u.peername + "'", onclick: {fn: Monast.requestInfo, obj: "dongle stop when convenient " + u.peername}});
				m[0].push({text: "Execute schedue 'Dongle restart now " + u.peername + "'", onclick: {fn: function () {
					Monast.doConfirm("Do you really need to restart this dongle?", function () { Monast.cliCommand("dongle restart now " + u.peername, false); });
 				}}});
				m[0].push({text: "Execute queued 'Dongle reset " + u.peername + "'", onclick: {fn: function () {
					Monast.doConfirm("Do you really need to reset this dongle?", function () { Monast.cliCommand("dongle reset " + u.peername, false); });
				}}});
				m[0].push({text: "Execute 'Dongle reload now'", onclick: {fn: Monast.requestInfo, obj: "dongle reload now"}});
				m[0].push({text: "Smart Restart", onclick: {fn: DongleTestCalls, obj: u}});
				
				//m[0].push({text: "Test wlad", onclick: {fn: TestSmartRestart, obj: u}});

				break;

			case 'Khomp':
				var bc = u.peername.replace('B', '').replace('C', ' ');
				m[0].push({text: "Execute 'khomp channels show " + bc + "'", onclick: {fn: Monast.requestInfo, obj: "khomp channels show " + bc}});
				m[0].push({text: "Send Reset Command to Modem", onclick: {fn: function () {
					Monast.doConfirm("Do you really need to reset this channel?", function () { Monast.cliCommand("khomp send command " + bc + " 244", false); }); 
				}}});
				break;
		}
		
		var queueIdx = 0;
		if (addQueue)
		{
			var queueOptions = [];
			var queueAddList = [];
			var queueDelList = [];
			Monast.queues.keys().each(function (id) {
				var q = Monast.queues.get(id);
				var m = q.members.get(md5("queueMember-" + q.queue + '::' + u.channel));
				if (Object.isUndefined(m))
					queueAddList.push({text: q.queuename, onclick: {fn: addQueueMember, obj: {peer: u, queue: q}}});
				else
					queueDelList.push({text: q.queuename, onclick: {fn: delQueueMember, obj: {peer: u, queue: q}}});
			});
			if (queueAddList.length > 0)
				queueOptions.push({text: "Turn Member of", url: "#addQueue", submenu: { id: "addQueue", itemdata: queueAddList}});
			if (queueDelList.length > 0)
				queueOptions.push({text: "Remove Member from", url: "#delQueue", submenu: { id: "delQueue", itemdata: queueDelList}});
			if (queueOptions.length > 0)
			{
				m.push(queueOptions);
				queueIdx = 1;
			}
		}
		
		var inviteMeetme = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Invite this User/Peer to Meetme \"" + p_oValue.meetme + "\"?</div><br>" + new Template($("Template::Userpeer::Info").innerHTML).evaluate(p_oValue.peer),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Originate', from: p_oValue.peer.channel, to: p_oValue.meetme, callerid: p_oValue.peer.callerid, type: 'meetmeInviteUser'})
						}
					});
				}
			);
			Monast.confirmDialog.setHeader('Meetme Invite');
		};
		var meetmeIdx  = 0;
		var meetmeList = [];
		Monast.meetmes.keys().each(function (id) {
			var m = Monast.meetmes.get(id);
			if (/^\d+$/.match(m.meetme))
				meetmeList.push({text: m.meetme, onclick: {fn: inviteMeetme, obj: {peer: u, meetme: m.meetme}}});
		});
		if (meetmeList.length > 0)
		{
			m.push([{text: "Invite to", url: "#meetme", submenu: { id: "meetme", itemdata: meetmeList}}]);
			meetmeIdx = queueIdx + 1;
		}
		
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("User/Peer: " + u.channel, 0);
		
		if (queueIdx > 0)
			this._contextMenu.setItemGroupTitle("Queues", queueIdx);
		if (meetmeIdx > 0)
			this._contextMenu.setItemGroupTitle("Meetme", meetmeIdx);
		
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	
	// Channels
	channels: new Hash(),
	processChannel: function (c)
	{
		c.id           = c.uniqueid;
		c.statecolor   = this.getColor(c.state);
		c.monitortext  = c.monitor ? "Yes" : "No";
		c.spytext      = c.spy ? "Yes" : "No";
		c.channel      = c.channel.replace('<', '&lt;').replace('>', '&gt;');
		c.calleridname = c.calleridname != null ? c.calleridname.replace('<', '').replace('>', '') : "";
		c.calleridnum  = c.calleridnum != null ? c.calleridnum.replace('<', '').replace('>', '') : "";
		c.callerid     = new Template("#{calleridname} &lt;#{calleridnum}&gt;").evaluate(c);
		
		if (Object.isUndefined(this.channels.get(c.id)))
		{
			var clone           = Monast.buildClone("Template::Channel", c.id);
			clone.className     = "channelDiv";
			clone.oncontextmenu = function () { Monast.showChannelContextMenu(c.id); return false; };
			$("channelsDiv").appendChild(clone);
			
			// Drag & Drop
			this.createDragDrop(c.id, this.dd_channelDrop, ['peerTable']);
		}

		var old = this.channels.get(c.id);
		Object.keys(c).each(function (key) {
			var elid = c.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					case "statecolor":
						$(elid).style.backgroundColor = c[key];
						if (c.subaction == "Update")
							Monast.blinkBackground(elid, c.statecolor);
						break;
						
					case "monitor":
						if (c.monitor) { $(elid).show(); } else { $(elid).hide(); }
						break;
						
					case "spy":
						if (c.spy) { $(elid).show(); } else { $(elid).hide(); }
						break;
						
					default:
						$(elid).innerHTML = c[key];
						break;
				}
			}
		});
		
		this.channels.set(c.id, c);
		$("countChannels").innerHTML = this.channels.keys().length;
	},
	dd_channelDrop: function (e, id)
	{
		var channel = Monast.channels.get(this.id);
		var peer    = Monast.userspeers.get(id);
		switch ($(id).className)
		{
			case "peerTable":
				Monast._contextMenu.clearContent();
				Monast._contextMenu.cfg.queueProperty("xy", Monast.getMousePosition());
				
				var requestTransfer = function (p_sType, p_aArgs, p_oValue)
				{
					var peer = p_oValue.peer;
					var to   = /\<(\d+)\>/.exec(peer.callerid);
					if (to == null)
					{
						Monast.doWarn("This User/Peer does not have a valid callerid number to transfer to.");
						return;
					}
					var obj        = p_oValue.channel;
					obj.tocallerid = peer.callerid;
					obj.tochannel  = peer.channel;
					obj.toexten    = to[1];
					Monast.doConfirm(
						"Do you really want to transfer channel '" + obj.channel + "' to '" + peer.callerid + "'?",
						function () {
							new Ajax.Request('action.php', 
							{
								method: 'get',
								parameters: {
									reqTime: new Date().getTime(),
									action: Object.toJSON({action: 'Transfer', from: obj.channel, to: obj.toexten, type: 'normal'})
								}
							});
						}
					);
					Monast.confirmDialog.setHeader('Transfer Call');
				};
				
				var requestSpyChannel = function (p_sType, p_aArgs, p_oValue)
				{
					var obj    = p_oValue.channel;
					obj.spyer  = p_oValue.peer.callerid;
					Monast.doConfirm(
						"<div style='text-align: center'>Request Spy to this Channel?</div><br>" + new Template($("Template::Channel::Form::Spy::Peer").innerHTML).evaluate(obj),
						function () {
							new Ajax.Request('action.php', 
							{
								method: 'get',
								parameters: {
									reqTime: new Date().getTime(),
									action: Object.toJSON({action: 'SpyChannel', spyer: p_oValue.peer.channel, spyee: p_oValue.channel.channel, type: "peer"})
								}
							});
						}
					);
				};
				
				var m = [
					[
					 	{text: "Transfer", onclick: {fn: requestTransfer, obj: {peer: peer, channel: channel}}},
						{text: "Spy", onclick: {fn: requestSpyChannel, obj: {peer: peer, channel: channel}}}
					]
				];
				
				Monast._contextMenu.addItems(m);
				Monast._contextMenu.setItemGroupTitle("Select Action for Channel " + channel.uniqueid + " (" + channel.channel + ")", 0);
				Monast._contextMenu.render(document.body);
				Monast._contextMenu.show();
				
				break;
		}
	},
	removeChannel: function (c)
	{
		var channel = this.channels.unset(c.uniqueid);
		if (!Object.isUndefined(channel))
			$('channelsDiv').removeChild($(channel.id));
		$('countChannels').innerHTML = this.channels.keys().length;
	},
	showChannelContextMenu: function (id, returnOnly)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
	
		var viewChannelInfo = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doAlert(new Template($("Template::Channel::Info").innerHTML).evaluate(p_oValue));
		};
		var requestMonitor = function (p_sType, p_aArgs, p_oValue)
		{
			var action = p_oValue.monitor ? "Stop" : "Start";
			Monast.doConfirm(
				"<div style='text-align: center'>" + action + " Monitor to this Channel?</div><br>" + new Template($("Template::Channel::Info").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Monitor' + action, channel: p_oValue.channel})
						}
					});
				}
			);
		};
		var requestSpy = function (p_sType, p_aArgs, p_oValue)
		{
			p_oValue.spyer = Monast._lastSpyer;
			Monast.doConfirm(
				"<div style='text-align: center'>Request Spy to this Channel?</div><br>" + new Template($("Template::Channel::Form::Spy::Number").innerHTML).evaluate(p_oValue),
				function () {
					var spyer = $("Template::Channel::Form::Spy::Number::Spyer").value.trim();
					if (!spyer)
					{
						Monast.doWarn("No Spyer Number Specified!");
						return;
					}
					Monast._lastSpyer = spyer;
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'SpyChannel', spyer: spyer, spyee: p_oValue.channel, type: "number"})
						}
					});
				}
			);
		};
		var requestHangup = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Request Hangup to this Channel?</div><br>" + new Template($("Template::Channel::Info").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Hangup', channel: p_oValue.channel})
						}
					});
				}
			);
		};
	
		var c = this.channels.get(id);
		var m = [
			[
				{text: c.monitor ? "Stop Monitor" : "Start Monitor", onclick: {fn: requestMonitor, obj: c}},
				{text: "Spy", onclick: {fn: requestSpy, obj: c}},
				{text: "Hangup", onclick: {fn: requestHangup, obj: c}},
				{text: "View Channel Info", onclick: {fn: viewChannelInfo, obj: c}},
				{text: "Execute 'core show channel " + c.channel + "'", onclick: {fn: Monast.requestInfo, obj: "core show channel " + c.channel}}
			]
		];
		
		if (!Object.isUndefined(returnOnly) && returnOnly)
			return m;
		
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("Uniqueid:  " + c.uniqueid, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	
	// Bridges
	bridges: new Hash(),
	processBridge: function (b)
	{
		if (b.status == "Unlink")
		{
			this.removeBridge(b);
			return;
		}
		
		b.id              = md5(b.uniqueid + "+++" + b.bridgeduniqueid);
		b.statuscolor     = this.getColor(b.status);
		b.channel         = b.channel.replace('<', '&lt;').replace('>', '&gt;');
		b.bridgedchannel  = b.bridgedchannel.replace('<', '&lt;').replace('>', '&gt;');
		b.callerid        = new Template("#{calleridname} &lt;#{calleridnum}&gt;").evaluate(this.channels.get(b.uniqueid));
 /* Wlads */
		if (b.linkedid == "")
		{
			b.bridgedcallerid = new Template("#{calleridname} &lt;#{calleridnum}&gt;").evaluate(this.channels.get(b.bridgeduniqueid));
		}
		else
		{
			b.bridgedcallerid = new Template("#{calleridname} &lt;#{calleridnum}&gt;").evaluate(this.channels.get(b.linkedid));
		}
		
		if (Object.isUndefined(this.bridges.get(b.id)))
		{
			var clone           = Monast.buildClone("Template::Bridge", b.id);
			clone.className     = "callDiv";
			clone.oncontextmenu = function () { Monast.showBridgeContextMenu(b.id); return false; };
			$("callsDiv").appendChild(clone);
			
			// Drag & Drop
			this.createDragDrop(b.id, this.dd_bridgeDrop, ['peerTable']);
		}

		var old = this.bridges.get(b.id);
		Object.keys(b).each(function (key) {
			var elid = b.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					case "statuscolor":
						$(elid).style.backgroundColor = b[key];
						if (b.subaction == "Update")
							Monast.blinkBackground(elid, b.statuscolor);
						break;
						
					default:
						$(elid).innerHTML = b[key];
						break;
				}
			}
		});
		
		if (b.status == "Link")
			this.startChrono(b.id, parseInt(b.seconds));
		
		this.bridges.set(b.id, b);
		$("countCalls").innerHTML = this.bridges.keys().length;
		
		this.sortBridges();
	},
	dd_bridgeDrop: function (e, id)
	{
		var bridge = Monast.bridges.get(this.id);
		var peer   = Monast.userspeers.get(id);
		switch ($(id).className)
		{
			case "peerTable":
				Monast._contextMenu.clearContent();
				Monast._contextMenu.cfg.queueProperty("xy", Monast.getMousePosition());
				
				var requestTransfer = function (p_sType, p_aArgs, p_oValue)
				{
					var peer = p_oValue.peer;
					var to   = /\<(\d+)\>/.exec(peer.callerid);
					if (to == null)
					{
						Monast.doWarn("This User/Peer does not have a valid callerid number to transfer to.");
						return;
					}
					var obj        = p_oValue.bridge;
					obj.tocallerid = peer.callerid;
					obj.tochannel  = peer.channel;
					obj.toexten    = to[1];
					Monast.doConfirm(
						"<div style='text-align: center'>Select Channel to Transfer:</div><br>" + new Template($("Template::Bridge::Form::Transfer::Internal").innerHTML).evaluate(obj),
						function () {
							new Ajax.Request('action.php', 
							{
								method: 'get',
								parameters: {
									reqTime: new Date().getTime(),
									action: Object.toJSON({action: 'Transfer', from: $$("input[name=Template::Bridge::Form::Transfer::Internal::From]:checked")[0].value, to: obj.toexten, type: 'normal'})
								}
							});
						}
					);
					Monast.confirmDialog.setHeader('Transfer Call');
				};
				
				var requestSpyChannel = function (p_sType, p_aArgs, p_oValue)
				{
					var obj    = p_oValue.bridge;
					obj.spyer  = p_oValue.peer.callerid;
					Monast.doConfirm(
						"<div style='text-align: center'>Request Spy to this Call?</div><br>" + new Template($("Template::Bridge::Form::Spy::Peer").innerHTML).evaluate(obj),
						function () {
							new Ajax.Request('action.php', 
							{
								method: 'get',
								parameters: {
									reqTime: new Date().getTime(),
									action: Object.toJSON({action: 'SpyChannel', spyer: p_oValue.peer.channel, spyee: p_oValue.bridge.channel, type: "peer"})
								}
							});
						}
					);
				};
				
				var m = [
					[
					 	{text: "Transfer", onclick: {fn: requestTransfer, obj: {peer: peer, bridge: bridge}}},
						{text: "Spy", onclick: {fn: requestSpyChannel, obj: {peer: peer, bridge: bridge}}}
					]
				];
				
				Monast._contextMenu.addItems(m);
				Monast._contextMenu.setItemGroupTitle("Select Action for Call " + bridge.uniqueid + " -> " + bridge.bridgeduniqueid, 0);
				Monast._contextMenu.render(document.body);
				Monast._contextMenu.show();
				
				break;
		}
	},
	removeBridge: function (b)
	{
		var id     = md5(b.uniqueid + "+++" + b.bridgeduniqueid);
		var bridge = this.bridges.unset(id);
		if (!Object.isUndefined(bridge))
		{
			$('callsDiv').removeChild($(bridge.id));
			this.stopChrono(id);
		}
		this.removeDragDrop(id);
		$('countCalls').innerHTML = this.bridges.keys().length;
	},
	_lastSpyer: "",
	showBridgeContextMenu: function (id)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
		
		var requestPark = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Select Channel to Park:</div><br>" + new Template($("Template::Bridge::Form::Park").innerHTML).evaluate(p_oValue),
				function () {
					var channel  = $$("input[name=Template::Bridge::Form::Park::Channel]:checked")[0].value;
					var announce = p_oValue.channel == channel ? p_oValue.bridgedchannel : p_oValue.channel;
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Park', channel: channel, announce: announce})
						}
					});
				}
			);
		};
		var requestHangup = function (p_sType, p_aArgs, p_oValue)
		{
			p_oValue._duration = $(p_oValue.id + '-chrono').innerHTML;
			Monast.doConfirm(
				"<div style='text-align: center'>Request Hangup to this Call?</div><br>" + new Template($("Template::Bridge::Info").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Hangup', channel: p_oValue.channel})
						}
					});
				}
			);
		};
		var requestSpy = function (p_sType, p_aArgs, p_oValue)
		{
			p_oValue.spyer = Monast._lastSpyer;
			Monast.doConfirm(
				"<div style='text-align: center'>Request Spy to this Call?</div><br>" + new Template($("Template::Bridge::Form::Spy::Number").innerHTML).evaluate(p_oValue),
				function () {
					var spyer = $("Template::Bridge::Form::Spy::Number::Spyer").value.trim();
					if (!spyer)
					{
						Monast.doWarn("No Spyer Number Specified!");
						return;
					}
					Monast._lastSpyer = spyer;
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'SpyChannel', spyer: spyer, spyee: p_oValue.channel, type: "number"})
						}
					});
				}
			);
		};
		var viewCallInfo = function (p_sType, p_aArgs, p_oValue)
		{
			if (p_oValue.status == "Link")
				p_oValue._duration = $(p_oValue.id + "-chrono").innerHTML;
			Monast.doAlert(new Template($("Template::Bridge::Info").innerHTML).evaluate(p_oValue));
		};
		
		var b = this.bridges.get(id);
		var m = [
			[
			 	{text: "Park", onclick: {fn: requestPark, obj: b}},
				{text: "Hangup", onclick: {fn: requestHangup, obj: b}},
				{text: "Spy", onclick: {fn: requestSpy, obj: b}},
				{text: "Source Channel", url: "#SourceChannel", submenu: {id: "SourceChannel", itemdata: Monast.showChannelContextMenu(b.uniqueid, true)}},
				{text: "Destination Channel", url: "#DestinationChannel", submenu: {id: "DestinationChannel", itemdata: Monast.showChannelContextMenu(b.bridgeduniqueid, true)}},
				{text: "View Call Info", onclick: {fn: viewCallInfo, obj: b}},
			]
		];
		
		var inviteMeetme = function (p_sType, p_aArgs, p_oValue)
		{
			p_oValue.bridge._duration = $(p_oValue.bridge.id + '-chrono').innerHTML;
			Monast.doConfirm(
				"<div style='text-align: center'>Invite this Call to Meetme \"" + p_oValue.meetme + "\"?</div><br>" + new Template($("Template::Bridge::Info").innerHTML).evaluate(p_oValue.bridge),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Transfer', from: p_oValue.bridge.channel, extrachannel: p_oValue.bridge.bridgedchannel, to: p_oValue.meetme, type: 'meetme'})
						}
					});
				}
			);
			Monast.confirmDialog.setHeader('Meetme Invite');
		};
		var meetmeList = [];
		Monast.meetmes.keys().each(function (id) {
			var m = Monast.meetmes.get(id);
			if (/^\d+$/.match(m.meetme))
				meetmeList.push({text: m.meetme, onclick: {fn: inviteMeetme, obj: {bridge: b, meetme: m.meetme}}});
		});
		if (meetmeList.length > 0)
		{
			m.push([{text: "Invite to", url: "#meetme", submenu: {id: "meetme", itemdata: meetmeList}}]);
			this._contextMenu.setItemGroupTitle("Meetme", 1);
		}
		
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("Call:  " + b.uniqueid + " -> " + b.bridgeduniqueid, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	sortBridges: function ()
	{
		if (!Monast.MONAST_KEEP_CALLS_SORTED)
			return;
		
		var bridges = [];
		this.bridges.keys().each(function (id) {
			var bridge = Monast.bridges.get(id);
			bridges.push({id: id, time: bridge.status == "Link" ? bridge.linktime : bridge.dialtime * 100});
		});
		bridges.sort(function (a, b) {
			return a.time - b.time;
		});
		bridges.each(function (b) {
			var bridge = $("callsDiv").removeChild($(b.id));
			$("callsDiv").appendChild(bridge);
		});
	},
	
	// Meetmes
	meetmes: new Hash(),
	processMeetme: function (m)
	{
		m.id          = md5("meetme-" + m.meetme);
		m.contextmenu = null; // FAKE
		
		if (Object.isUndefined(this.meetmes.get(m.id))) // Meetme does not exists
		{
			var clone       = Monast.buildClone("Template::Meetme", m.id);
			clone.className = 'meetmeDivWrap';
			$('meetmeDivWrapper').appendChild(clone);
		}
	
		// Clear meetme users
		$(m.id).select('[class="meetmeUser"]').each(function (el) { el.remove(); });
		$(m.id + "-countMeetme").innerHTML = 0;
		
		Object.keys(m).each(function (key) {
			var elid = m.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					case "contextmenu":
						$(elid).oncontextmenu = function () { Monast.showMeetmeContextMenu(m.id); return false; };
						break;
						
					default:
						$(elid).innerHTML = m[key];
						break;
				}
			}
		});
		
		if (!Object.isArray(m.users))
		{
			var keys = Object.keys(m.users).sort();
			keys.each(function (user) {
				var user          = m.users[user];
				user.id           = md5("meetmeUser-" + m.meetme + "::" + user.usernum);
				user.userinfo     = (user.calleridnum && user.calleridname) ? new Template("#{calleridname} &lt;#{calleridnum}&gt;").evaluate(user) : user.channel;
				
				if (!$(user.id))
				{
					var clone       = Monast.buildClone("Template::Meetme::User", user.id);
					clone.className = "meetmeUser";
					clone.oncontextmenu = function () { Monast.showMeetmeUserContextMenu(m.id, user); return false; };
					$(m.id).appendChild(clone);
				}
				
				Object.keys(user).each(function (key) {
					var elid = user.id + '-' + key;
					if ($(elid))
					{
						switch (key)
						{
							default:
								$(elid).innerHTML = user[key];
								break;
						}
					}
				});
			});
			$(m.id + "-countMeetme").innerHTML = keys.length;
		}

		this.meetmes.set(m.id, m);
	},
	removeMeetme: function (m)
	{
		var id     = md5("meetme-" + m.meetme);
		var meetme = this.meetmes.unset(id);
		if (!Object.isUndefined(meetme))
		{
			$('meetmeDivWrapper').removeChild($(meetme.id));
		}
	},
	_meetmeInviteNumbers: function (foo, m)
	{
		if (m == null)
		{
			var d = new Date();
			m     = {meetme: "Monast-" + parseInt(d.getTime() / 1000)};
		}
		Monast.doConfirm(
			new Template($("Template::Meetme::Form::InviteNumbers").innerHTML).evaluate(m),
			function () {
				new Ajax.Request('action.php', 
				{
					method: 'get',
					parameters: {
						reqTime: new Date().getTime(),
						action: Object.toJSON({action: 'Originate', from: $('Meetme::Form::InviteNumbers::Numbers').value, to: $('Meetme::Form::InviteNumbers::Meetme').value, type: 'meetmeInviteNumbers'})
					}
				});
			}
		);
		Monast.confirmDialog.setHeader('Invite Numbers to Meetme');
	},
	showMeetmeContextMenu: function (id)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
		
		var inviteNumbers = function (p_sType, p_aArgs, p_oValue)
		{
			Monast._meetmeInviteNumbers(null, p_oValue);
		};
		
		var meetme = this.meetmes.get(id);
		var m = [
			[
				{text: "Invite Numbers", onclick: {fn: inviteNumbers, obj: meetme}},
			]
		];
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("Meetme:  " + meetme.meetme, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	showMeetmeUserContextMenu: function (id, user)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
		
		var viewUserInfo = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doAlert(new Template($("Template::Meetme::User::Info").innerHTML).evaluate(p_oValue));
		};
		var kickUser = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Request Kick to this User from Meetme \"" + p_oValue.meetme + "\"?</div><br>" + new Template($("Template::Meetme::User::Info").innerHTML).evaluate(p_oValue.user),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'MeetmeKick', meetme: p_oValue.meetme, usernum: p_oValue.user.usernum})
						}
					});
				}
			);
		};
		
		var meetme = this.meetmes.get(id);
		var m = [
			[
				{text: "Kick User", onclick: {fn: kickUser, obj: {meetme: meetme.meetme, user: user}}},
				{text: "View User Info", onclick: {fn: viewUserInfo, obj: user}}
			]
		];
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("Meetme User:  " + user.userinfo, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	
	// Parked Calls
	parkedCalls: new Hash(),
	processParkedCall: function (p)
	{
		p.id = md5("parkedCall-" + p.channel);
		
		if (Object.isUndefined(this.parkedCalls.get(p.id))) // ParkedCall does not exists
		{
			var clone           = Monast.buildClone("Template::ParkedCall", p.id);
			clone.className     = "parkedDiv";
			clone.oncontextmenu = function () { Monast.showParkedCallContextMenu(p.id); return false; };
			$("parkedsDiv").appendChild(clone);
			
			// Drag & Drop
			this.createDragDrop(p.id, this.dd_parkedCallDrop, ['peerTable']);
		}
		
		Object.keys(p).each(function (key) {
			var elid = p.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					default:
						$(elid).innerHTML = p[key];
						break;
				}
			}
		});
		
		this.parkedCalls.set(p.id, p);
		$("countParked").innerHTML = this.parkedCalls.keys().length;
		
		this.sortParkedCalls();
	},
	dd_parkedCallDrop: function (e, id)
	{
		var parked = Monast.parkedCalls.get(this.id);
		switch ($(id).className)
		{
			case "peerTable":
				var peer = Monast.userspeers.get(id);
				var to   = /\<(\d+)\>/.exec(peer.callerid);
				if (to == null)
				{
					Monast.doWarn("This User/Peer does not have a valid callerid number to transfer to.");
					break;
				}
				Monast.doConfirm(
					"<div style='text-align: center'>Request Transfer this Parked Call to User/Peer \"" + peer.callerid + "\"?</div><br>" + new Template($("Template::ParkedCall::Info").innerHTML).evaluate(parked),
					function () {
						new Ajax.Request('action.php', 
						{
							method: 'get',
							parameters: {
								reqTime: new Date().getTime(),
								action: Object.toJSON({action: 'Originate', from: peer.channel, to: parked.exten, type: 'dial'})
							}
						});
					}
				);
				Monast.confirmDialog.setHeader('Transfer Parked Call');
				break;
		}
	},
	removeParkedCall: function (p)
	{
		var id     = md5("parkedCall-" + p.channel);
		var parked = this.parkedCalls.unset(id);
		if (!Object.isUndefined(parked))
		{
			$('parkedsDiv').removeChild($(parked.id));
		}
		$("countParked").innerHTML = this.parkedCalls.keys().length;
	},
	showParkedCallContextMenu: function (id)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
		
		var viewParkedCallInfo = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doAlert(new Template($("Template::ParkedCall::Info").innerHTML).evaluate(p_oValue));
		};
		var requestHangup = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Request Hangup to this Parked Call?</div><br>" + new Template($("Template::ParkedCall::Info").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Hangup', channel: p_oValue.channel})
						}
					});
				}
			);
		};
		
		var parked = this.parkedCalls.get(id);
		var m = [
			[
				{text: "Hangup", onclick: {fn: requestHangup, obj: parked}},
				{text: "View Parked Call Info", onclick: {fn: viewParkedCallInfo, obj: parked}}
			]
		];
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("Parked Call:  " + parked.exten, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	sortParkedCalls: function ()
	{
		if (!Monast.MONAST_KEEP_PARKEDCALLS_SORTED)
			return;
		
		var parkedCalls = [];
		this.parkedCalls.keys().each(function (id) {
			var parkedCall = Monast.parkedCalls.get(id);
			parkedCalls.push({id: id, exten: parkedCall.exten});
		});
		parkedCalls.sort(function (a, b) {
			return a.exten < b.exten ? -1 : (a.exten > b.exten ? 1 : 0);
		});
		parkedCalls.each(function (b) {
			var parkedCall = $("parkedsDiv").removeChild($(b.id));
			$("parkedsDiv").appendChild(parkedCall);
		});
	},
	
	// Queues
	queuesDual: [],
	queues: new Hash(),
	processQueue: function (q)
	{
		q.id                = md5("queue-" + q.queue);
		q.queuename         = q.mapname ? q.mapname : q.queue;
		q.contextmenu       = null; // FAKE
		q.total_calls       = q.completed + q.abandoned;
		q.abandoned_percent = parseInt((q.abandoned / q.total_calls) * 100);
		
		if (Object.isUndefined(this.queues.get(q.id))) // Queue does not exists
		{
			var clone       = Monast.buildClone("Template::Queue", q.id);
			clone.className = "queueDiv";
			
			// Lookup Dual Free
			var dualid = null;
			if (this.queuesDual.length == 0)
			{
				this.queuesDual.push([q.id]);
				dualid = "dual::0";
			}
			else
			{
				var l = this.queuesDual.length;
				if (this.queuesDual[l - 1].length < 2)
				{
					this.queuesDual[l - 1].push(q.id);
					dualid = "dual::" + (l - 1);
				}
				else
				{
					this.queuesDual.push([q.id]);
					dualid = "dual::" + l;
				}
			}
			
			var dual = $(dualid);
			if (!dual)
			{
				dual             = document.createElement('div');
				dual.id          = dualid;
				dual.className   = 'queueDualDiv';
			}
			
			dual.appendChild(clone);
			$('fieldset-queuedual').appendChild(dual);
		}

		var old = this.queues.get(q.id);
		
		Object.keys(q).each(function (key) {
			var elid = q.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					case "contextmenu":
						$(elid).oncontextmenu = function () { Monast.showQueueContextMenu(q.id); return false; };
						break;
				
					default:
						$(elid).innerHTML = q[key];
						if (old && old[key] != q[key])
							Monast.blinkText(elid);
						break;
				}
			}
		});
		
		q.members = old ? old.members : new Hash();
		q.clients = old ? old.clients : new Hash();
		q.ccalls  = old ? old.ccalls : new Hash();
		
		this.queues.set(q.id, q);
	},
	showQueueContextMenu: function (id)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
	
		var viewQueueInfo = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doAlert(new Template($("Template::Queue::Info").innerHTML).evaluate(p_oValue));
		};
		var addExternalMember = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				new Template($("Template::Queue::Form::ExternalMember").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'QueueMemberAdd', queue: p_oValue.queue, membername: $("Template::Queue::Form::ExternalMember::Name").value, location: $("Template::Queue::Form::ExternalMember::Location").value, external: true})
						}
					});
				}
			);
			Monast.confirmDialog.setHeader("Add External Member");
		};
		
		var q = this.queues.get(id);
		var m = [
			[
			 	{text: "Add External Member", onclick: {fn: addExternalMember, obj: q}},
				{text: "View Queue Info", onclick: {fn: viewQueueInfo, obj: q}}
			]
		];
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("Queue:  " + q.queue, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	processQueueMember: function (m)
	{
		m.id          = md5("queueMember-" + m.queue + '::' + m.location);
		m.queueid     = md5("queue-" + m.queue);
		m.statustext_nochrono = m.paused == '1' ? 'Paused' : m.statustext;
		m.statustext  = m.paused == '1' ? 'Paused<br><span style="font-family: monospace;" id="' + m.id + '-chrono"></span>' : m.statustext;
		m.pausedtext  = m.paused == "1" ? "Yes" : "No";
		m.statuscolor = this.getColor(m.statustext); 
				
		if (Object.isUndefined(this.queues.get(m.queueid).members.get(m.id))) // Queue Member does not exists
		{
			var clone           = Monast.buildClone("Template::Queue::Member", m.id);
			clone.className     = "queueMembersDiv";
			clone.oncontextmenu = function () { Monast.showQueueMemberContextMenu(m.queueid, m.id); return false; };
			$(m.queueid + '-queueMembers').appendChild(clone);
		}
		
		var old = this.queues.get(m.queueid).members.get(m.id);
		Object.keys(m).each(function (key) {
			var elid = m.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					case "statuscolor":
						$(elid).style.backgroundColor = m.statuscolor;
						if (old && old.paused != m.paused)
						{
							Monast.blinkBackground(elid, m.statuscolor);
							break;
						}
						if (old && m.paused == "0" && old.status != m.status)
							Monast.blinkBackground(elid, m.statuscolor);
						break;
						
					case "callstaken":
						$(elid).innerHTML = m[key];
						if (old && old[key] != m[key])
							Monast.blinkText(elid);
						break;
						
					default:
						$(elid).innerHTML = m[key];
						break;
				}
			}
		});
		
		this.stopChrono(m.id);
		if (m.paused == '1')
			this.startChrono(m.id, m.pausedur);
		
		this.queues.get(m.queueid).members.set(m.id, m);
		$(m.queueid + '-queueMembersCount').innerHTML = this.queues.get(m.queueid).members.keys().length;
	},
	removeQueueMember: function (m)
	{
		var id       = md5("queueMember-" + m.queue + '::' + m.location);
		var queueid  = md5("queue-" + m.queue);
		var member = this.queues.get(queueid).members.unset(id);
		if (!Object.isUndefined(member))
		{
			this.stopChrono(member.id);
			$(member.queueid + '-queueMembers').removeChild($(member.id));
		}
		$(member.queueid + '-queueMembersCount').innerHTML = this.queues.get(member.queueid).members.keys().length;
	},
	showQueueMemberContextMenu: function (queueid, id)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
	
		var requestMemberPause = function (p_sType, p_aArgs, p_oValue)
		{
			var action = p_oValue.paused == "0" ? "Pause" : "Unpause";
			Monast.doConfirm(
				"<div style='text-align: center'>" + action + " this Queue Member?</div><br>" + new Template($("Template::Queue::Member::Info").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'QueueMember' + action, queue: p_oValue.queue, location: p_oValue.location})
						}
					});
				}
			);
		};
		var requestMemberRemove = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Remove this Member from Queue \"" + p_oValue.queue + "\"?</div><br>" + new Template($("Template::Queue::Member::Info").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'QueueMemberRemove', queue: p_oValue.queue, location: p_oValue.location})
						}
					});
				}
			);
		};
		var viewMemberInfo = function (p_sType, p_aArgs, p_oValue)
		{
			p_oValue.lastcalltext = new Date(p_oValue.lastcall * 1000).toLocaleString();
			Monast.doAlert(new Template($("Template::Queue::Member::Info").innerHTML).evaluate(p_oValue));
		};
		
		var qm = this.queues.get(queueid).members.get(id);
		var m = [
			[
				{text: qm.paused == "0" ? "Pause Member" : "Unpause Member", onclick: {fn: requestMemberPause, obj: qm}},
				{text: "Remove Member", disabled: qm.membership == "static", onclick: {fn: requestMemberRemove, obj: qm}},
				{text: "View Member Info", onclick: {fn: viewMemberInfo, obj: qm}}
			]
		];
		this._contextMenu.addItems(m);
		this._contextMenu.setItemGroupTitle("Queue Member:  " + qm.name, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	processQueueClient: function (c)
	{
		c.id          = md5("queueClient-" + c.queue + '::' + c.uniqueid);
		c.queueid     = md5("queue-" + c.queue);
		c.callerid    = c.channel;
		
		if (c.calleridname)
			c.callerid = c.calleridname + " &lt;" + c.calleridnum + "&gt;";
		
		if (Object.isUndefined(this.queues.get(c.queueid).clients.get(c.id))) // Queue Client does not exists
		{
			var clone           = Monast.buildClone("Template::Queue::Client", c.id);
			clone.className     = "queueClientsDiv";
			clone.oncontextmenu = function () { Monast.showQueueClientContextMenu(c.queueid, c.id); return false; };
			$(c.queueid + '-queueClients').appendChild(clone);
		}
		
		Object.keys(c).each(function (key) {
			var elid = c.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					default:
						$(elid).innerHTML = c[key];
						break;
				}
			}
		});
		
		this.startChrono(c.id, c.seconds);
		
		this.queues.get(c.queueid).clients.set(c.id, c);
		$(c.queueid + '-queueClientsCount').innerHTML = this.queues.get(c.queueid).clients.keys().length;
	},
	removeQueueClient: function (c)
	{
		var id       = md5("queueClient-" + c.queue + '::' + c.uniqueid);
		var queueid  = md5("queue-" + c.queue);
		var client   = this.queues.get(queueid).clients.unset(id);
		if (!Object.isUndefined(client))
		{
			this.stopChrono(client.id);
			$(client.queueid + '-queueClients').removeChild($(client.id));
		}
		$(client.queueid + '-queueClientsCount').innerHTML = this.queues.get(client.queueid).clients.keys().length;
	},
	showQueueClientContextMenu: function (queueid, id)
	{
		this._contextMenu.clearContent();
		this._contextMenu.cfg.queueProperty("xy", this.getMousePosition());
	
		var requestHangup = function (p_sType, p_aArgs, p_oValue)
		{
			Monast.doConfirm(
				"<div style='text-align: center'>Drop this Queue Client?</div><br>" + new Template($("Template::Queue::Client::Info").innerHTML).evaluate(p_oValue),
				function () {
					new Ajax.Request('action.php', 
					{
						method: 'get',
						parameters: {
							reqTime: new Date().getTime(),
							action: Object.toJSON({action: 'Hangup', channel: p_oValue.channel})
						}
					});
				}
			);
		};
		var viewClientInfo = function (p_sType, p_aArgs, p_oValue)
		{
			p_oValue.pausedtext = p_oValue.paused == "1" ? "True" : "False";
			p_oValue.waittime   = new Date(p_oValue.jointime * 1000).toLocaleString();
			Monast.doAlert(new Template($("Template::Queue::Client::Info").innerHTML).evaluate(p_oValue));
		};
		
		var qc = this.queues.get(queueid).clients.get(id);
		var c = [
			[
				{text: "Drop Client (Hangup)", onclick: {fn: requestHangup, obj: qc}},
				{text: "View Client Info", onclick: {fn: viewClientInfo, obj: qc}}
			]
		];
		this._contextMenu.addItems(c);
		this._contextMenu.setItemGroupTitle("Queue Client:  " + qc.callerid, 0);
		this._contextMenu.render(document.body);
		this._contextMenu.show();
	},
	processQueueCall: function (c)
	{
		c.id       = md5("queueCall-" + c.client.uniqueid + "::" + c.member.location);
		c.queueid  = md5("queue-" + c.client.queue);
		c.memberid = md5("queueMember-" + c.member.queue + '::' + c.member.location); 
		c.callerid = c.client.channel;
		
		if (c.client.calleridname)
			c.callerid = c.client.calleridname + " &lt;" + c.client.calleridnum + "&gt;";
		
		if (Object.isUndefined(this.queues.get(c.queueid).ccalls.get(c.id))) // Queue Call does not exists
		{
			var clone           = Monast.buildClone("Template::Queue::Call", c.id);
			clone.className     = "";
			$(c.memberid).appendChild(clone);
		}
		
		var old = this.queues.get(c.queueid).ccalls.get(c.id);		
		Object.keys(c).each(function (key) {
			var elid = c.id + '-' + key;
			if ($(elid))
			{
				switch (key)
				{
					default:
						$(elid).innerHTML = c[key];
						break;
				}
			}
		});
		
		this.startChrono(c.id, c.seconds);
		
		this.queues.get(c.queueid).ccalls.set(c.id, c);
	},
	removeQueueCall: function (c)
	{
		c.id       = md5("queueCall-" + c.uniqueid + "::" + c.location);
		c.queueid  = md5("queue-" + c.queue);
		call       = this.queues.get(c.queueid).ccalls.unset(c.id);
		if (!Object.isUndefined(call))
		{
			this.stopChrono(c.id);
			$(call.memberid).removeChild($(call.id));
		}
	},

	// Process Events
	processEvent: function (event)
	{
		if ($('debugDiv'))
			$('debugDiv').innerHTML += Object.toJSON(event) + "<br>\r\n";
		
		if (!Object.isUndefined(event.objecttype))
		{
			//console.log("ObjectType:", event.objecttype, event);
			switch (event.objecttype)
			{
				case "User/Peer":
					this.processUserpeer(event);
					
					if(Monast.NEED_DONGLE_RESTART)
					{
						Monast.checkDongle(event);
					}
					break;
					
				case "Channel":
					this.processChannel(event);
					break;
					
				case "Bridge":
					this.processBridge(event);
					break;
					
				case "Meetme":
					this.processMeetme(event);
					break;
					
				case "ParkedCall":
					this.processParkedCall(event);
					break;
					
				case "Queue":
					this.processQueue(event);
					break;
					
				case "QueueMember":
					this.processQueueMember(event);
					break;
					
				case "QueueClient":
					this.processQueueClient(event);
					break;
					
				case "QueueCall":
					this.processQueueCall(event);
					break;
			}
		}
		
		if (!Object.isUndefined(event.action))
		{
			//console.log("Action:", event.action, event);
			switch (event.action)
			{
				case "Error":
					this._statusError = true;
					this.doError(event.message);
					return;
					
				case "Reload":
					this._statusReload = true;
					if (this._reloadTimeout != null)
					{
						clearTimeout(this._reloadTimeout);
						this._reloadTimeout = null;
					}
					setTimeout("location.href = 'index.php'", event.time);
					return;
					
				case "RemoveChannel":
					this.removeChannel(event);
					break;
					
				case "RemoveBridge":
					this.removeBridge(event);
					break;
					
				case "RemoveMeetme":
					this.removeMeetme(event);
					break;
					
				case "RemoveParkedCall":
					this.removeParkedCall(event);
					break;
					
				case "RemoveQueueMember":
					this.removeQueueMember(event);
					break;
					
				case "RemoveQueueClient":
					this.removeQueueClient(event);
					break;
					
				case "RemoveQueueCall":
					this.removeQueueCall(event);
					break;
					
				case "CliResponse":
					this.cliResponse(event);
					break;
					
				case "RequestInfoResponse":
					this.requestInfoResponse(event);
					break;
					
				case "RequestError":
					this.doError(event.message);
					break;
			}
		}
	},
	
	// Request Status via AJAX
	_statusError: false,
	_statusReload: false,
	requestStatus: function ()
	{
		if (this._statusError)
		{
			$('_reqStatus').innerHTML = "<font color='red'>Reload needed, Press F5.</font>";
			return;
		}
		if (this._statusReload)
		{
			$('_reqStatus').innerHTML = "Reloading, please wait...";
			return;
		}
			
		new Ajax.Request('status.php', 
		{
			method: 'get',
			parameters: {
				reqTime: new Date().getTime()
			},
			
			onCreate:        function() { $('_reqStatus').innerHTML = 'Create'; },
			onUninitialized: function() { $('_reqStatus').innerHTML = 'Uninitialized'; },
			onLoading:       function() { $('_reqStatus').innerHTML = 'On Line'; },
			onLoaded:        function() { $('_reqStatus').innerHTML = 'Loaded'; },
			onInteractive:   function() { $('_reqStatus').innerHTML = 'Interactive'; },
			onComplete:      function() { $('_reqStatus').innerHTML = 'Complete'; Monast.requestStatus(); },
			
			onSuccess: function(transport)
			{
				var events = transport.responseJSON;
				events.each(function (event) 
				{
					try
					{
						Monast.processEvent(event);						
					}
					catch (e)
					{
						console.log(e.toString(), e, event);
					}
				});
			},
			onFailure: function()
			{
				this._statusError = true;
				doError('!! MonAst ERROR !!\n\nAn error ocurred while requesting status!\nPlease press F5 to reload MonAst.');
			}
		});
	},
	
	// Alerts & Messages
	doAlert: function (message)
	{
		Monast.alertDialog.setHeader('Information');
		Monast.alertDialog.setBody("<table><tr><td valign='top'><span class='yui-icon infoicon'></span></td><td>" + message + "</td></tr></table>");
		Monast.alertDialog.cfg.setProperty("fixedcenter", true);
		Monast.alertDialog.cfg.setProperty("constraintoviewport", true);
		Monast.alertDialog.render();
		Monast.alertDialog.show();
	},
	doError: function (message)
	{
		Monast.alertDialog.setHeader('Error');
		Monast.alertDialog.setBody("<table><tr><td valign='top'><span class='yui-icon blckicon'></span></td><td>" + message + "</td></tr></table>");
		Monast.alertDialog.cfg.setProperty("fixedcenter", true);
		Monast.alertDialog.cfg.setProperty("constraintoviewport", true);
		Monast.alertDialog.render();
		Monast.alertDialog.show();
	},
	doWarn: function (message)
	{
		Monast.alertDialog.setHeader('Warning');
		Monast.alertDialog.setBody("<table><tr><td valign='top'><span class='yui-icon warnicon'></span></td><td>" + message + "</td></tr></table>");
		Monast.alertDialog.cfg.setProperty("fixedcenter", true);
		Monast.alertDialog.cfg.setProperty("constraintoviewport", true);
		Monast.alertDialog.render();
		Monast.alertDialog.show();
	},
	doConfirm: function (message, handleYes, handleNo)
	{
		if (!handleNo)
			handleNo = function () { };
	
		var buttons = [
			{text: "Yes", handler: function () { this.hide(); handleYes(); }},
			{text: "No", handler: function () { this.hide(); handleNo(); }}
		];
		
		Monast.confirmDialog.setHeader('Confirmation');
		Monast.confirmDialog.setBody("<table><tr><td valign='top'><span class='yui-icon hlpicon'></span></td><td>" + message + "</td></tr></table>");
		Monast.confirmDialog.cfg.setProperty("buttons", buttons); 
		Monast.confirmDialog.render();
		Monast.confirmDialog.show();
	},
	
	// Monast INIT
	init: function ()
	{
		YAHOO.util.DDM.mode = YAHOO.util.DDM.POINT;
		
		// Dialogs
		Monast.alertDialog =  new YAHOO.widget.SimpleDialog("_alertDialog", {
			zindex: 10,
			fixedcenter: true,
			visible: false,
			draggable: true,
			close: true,
			constraintoviewport: true,
			modal: true,
			buttons: [{text: "OK", handler: function() { this.hide(); }}]
		});
		Monast.alertDialog.render(document.body);
		
		Monast.confirmDialog = new YAHOO.widget.SimpleDialog("_confirmDialog", {
			zindex: 10,
			fixedcenter: true,
			visible: false,
			draggable: true,
			close: true,
			constraintoviewport: true,
			modal: true
		});
		Monast.confirmDialog.render(document.body);
		
		if ($('authentication') || $('error'))
			return;
		
		// CheckBox Buttons for Mixed Pannels
		Monast._checkBoxTabButtons = [];
		var tabs = [
		    ["peersDiv", "Peers/Users"],
		    ["meetmesDiv", "Meetme Rooms"],
		    ["chanCallDiv", "Channels/Calls"],
		    ["parkedCallsDiv", "Parked Calls"],
		    ["queuesDiv", "Queues"]
		];
		tabs.each(function (tab) {
			var name  = tab[0];
			var title = tab[1];
			if ($("checkBoxTab_" + name))
			{
				var button = new YAHOO.widget.Button("checkBoxTab_" + name, { label: title });
				button.addListener('checkedChange', Monast.showHidePannels);
				Monast._checkBoxTabButtons.push(button);
			}
		});
		
		// Cookie to save View state
		Monast._stateCookie = YAHOO.util.Cookie.get(MONAST_COOKIE_KEY);		
		if (!Monast._stateCookie)
		{
			//Monast.doAlert("Куков не было!");
			Monast._stateCookie = {					
					activeIndex: 1,
					stateRestartCheckbox: Monast.NEED_DONGLE_RESTART,
					buttons: {}
			};
			tabs.each(function (tab) {
				Monast._stateCookie.buttons["checkBoxTab_" + tab[0]] = false;
			});
		}
		else
		{			
			Monast._stateCookie = Monast._stateCookie.evalJSON();			
		}
		
		// TabPannel and Listeners
		Monast._tabPannel = new YAHOO.widget.TabView('TabPannel');
		Monast._tabPannel.addListener('beforeActiveTabChange', function(e) {
			tabs.each(function (tab) {
				$(tab[0]).className = 'yui-hidden';
			});
		
			var _tabs = this.get('tabs');
			_tabs.each(function (tab, i) {
				if (tab.get('label') == e.newValue.get('label'))
				{
					Monast._stateCookie.activeIndex = i;
					YAHOO.util.Cookie.set(MONAST_COOKIE_KEY, Object.toJSON(Monast._stateCookie));
				}
			});
		});
		Monast._tabPannel.getTab(0).addListener('click', function(e) {
			Monast._checkBoxTabButtons.each(function (button) {
				button.set('checked', Monast._stateCookie.buttons[button.get('id')]);
			});
		});
		Monast._tabPannel.set('activeIndex', Monast._stateCookie.activeIndex);
		if (Monast._stateCookie.activeIndex == 0)
		{
			Monast._checkBoxTabButtons.each(function (button) {
				button.set('checked', Monast._stateCookie.buttons[button.get('id')]);
			});
		}
		
		if (!Monast.IE)
			document.captureEvents(Event.MOUSEMOVE);
		document.onmousemove = Monast.followMousePos;
		
		if (Monast.MONAST_CALL_TIME)
			setInterval("Monast._runChrono()", 500);
			
		our_checkbox = document.getElementById("checkBoxSmartRestart");
		our_checkbox.checked = Monast._stateCookie.stateRestartCheckbox;
		Monast.checkBoxSmartRestartListener("checkBoxSmartRestart");
	},
	
	showHidePannels: function (e)
	{
		$(this.get('value')).className = (e.newValue ? '' : 'yui-hidden');
		Monast._stateCookie.buttons[this.get('id')] = e.newValue;
		YAHOO.util.Cookie.set(MONAST_COOKIE_KEY, Object.toJSON(Monast._stateCookie));
	},
	
	hideTab: function (tabName)
	{
		var tabs = {
			"Mixed Pannels"  : "mixed",
			"Peers/Users"    : "peersDiv",
			"Meetme Rooms"   : "meetmesDiv",
			"Channels/Calls" : "chanCallDiv",
			"Parked Calls"   : "parkedCallsDiv",
			"Queues"         : "queuesDiv",
			"Asterisk CLI"   : "cliDiv",
			"Debug"          : "debugDiv"
		};
		if (!Object.isUndefined(tabs[tabName]))
		{
			if ($("liTab_" + tabs[tabName]))
			{
				$(tabs[tabName]).hide();
				$("liTab_" + tabs[tabName]).hide();
				if ($('checkBoxTab_' + tabs[tabName]))
					setTimeout("$('checkBoxTab_" + tabs[tabName] + "').hide()", 1000);
			}
		}
	},
	
	buildClone: function (id, newid)
	{
		var clone = $(id).cloneNode(true);
		clone.id  = newid;
		clone.select('[monast]').each(function (e) {
			e.id = newid + "-" + e.readAttribute('monast');
		});
		return clone;
	},
	
	// Drag&Drop
	dd: new Hash(),
	createDragDrop: function (id, onDragDrop, validTargets)
	{
		var dd = new YAHOO.util.DD(id);
		dd.onMouseDown   = this.dd_setStartPosition;
		dd.onMouseUp     = this.dd_backToStartPosition;
		dd.onDragOver    = this.dd_dragOver;
		dd.onDragOut     = this.dd_dragOut;
		dd.onDragDrop    = onDragDrop;
		dd.validTargets  = validTargets;
		this.dd.set(id, dd);
	},
	removeDragDrop: function (id)
	{
		this.dd.unset(id);
	},	
	dd_setStartPosition: function (e)
	{
		var el          = $(this.id);
		this.startPos   = YAHOO.util.Dom.getXY(YAHOO.util.Dom.get(this.id));
		this.origZindex = el.getStyle('z-index') == null ? 1 : el.getStyle('z-index');
		el.setStyle({'z-index': 2});
	},
	dd_backToStartPosition: function (e)
	{
		var dd = Monast.dd.get(this.id);
		new YAHOO.util.Motion(  
				this.id, {  
				points: {
					to: dd.startPos
				}
			},
			0.5,
			YAHOO.util.Easing.easeOut
		).animate();

		if (dd.origZindex)
			$(this.id).setStyle({zIndex: dd.origZindex});

		if (dd.lastOver)
			$(dd.lastOver).setStyle({opacity: 1});
	},
	dd_dragOver: function (e, id)
	{
		var dd = Monast.dd.get(this.id);
		if (dd.validTargets.indexOf($(id).className) != -1)
		{
			$(id).setStyle({opacity: 0.5});
			this.lastOver = id;
		}
	},
	dd_dragOut: function (e, id)
	{
		$(id).setStyle({opacity: 1});
	},
	
	// Chrono
	_chrono: new Hash(),
	startChrono: function (id, seconds)
	{
		if (!Monast.MONAST_CALL_TIME)
			return;
		var now = new Date();
		var sec = now - (seconds * 1000);
		this._touchChrono(id, new Date(now - sec));
		this._chrono.set(id, sec);
	},
	stopChrono: function (id)
	{
		this._chrono.unset(id);
	},
	_touchChrono: function (id, d)
	{
		var s = d.getUTCSeconds();
		var m = d.getUTCMinutes();
		var h = d.getUTCHours();
		if ($(id + "-chrono"))
			$(id + "-chrono").innerHTML = (h < 10 ? "0" + h : h) + ":" + (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
	},
	_runChrono: function ()
	{
		var now = new Date();
		this._chrono.keys().each(function (id) {
			var d = new Date(now - Monast._chrono.get(id));
			Monast._touchChrono(id, d);
		});
	},
	
	// Extra Utils
	IE: document.all ? true : false,
	mouseX: 0,
	mouseY: 0,
	followMousePos: function (e)
	{
		if (Monast.IE)
		{
			Monast.mouseX = event.clientX + document.body.scrollLeft;
			Monast.mouseY = event.clientY + document.body.scrollTop;
		}
		else
		{
			Monast.mouseX = e.pageX;
			Monast.mouseY = e.pageY;
		}
		if (Monast.mouseX < 0) {Monast.mouseX = 0;}
		if (Monast.mouseY < 0) {Monast.mouseY = 0;}
		return true;
	},
	getMousePosition: function ()
	{
		return [Monast.mouseX, Monast.mouseY];
	},
	
	// User Actions
	doLogin: function ()
	{
		var username = $('_username').value;
		var secret   = $('_secret').value;
		
		if (!username)
		{
			Monast.doAlert('You must define an user.');
			$('_reqStatus').innerHTML = "<font color='red'>User not defined!</font>";
		}
		else
		{
			new Ajax.Request('login.php', {
				method: 'post',
				parameters: {
					reqTime: new Date().getTime(),
					username: username,
					secret: secret
				},
				onCreate: function () {
					$('_reqStatus').innerHTML = 'Authenticating, please wait...';
				},
				onSuccess: function (r) {
					var json = r.responseJSON;
					if (json['error'])
					{
						$('_reqStatus').innerHTML = "<font color='red'>Monast Error!</font>";;
						Monast.doError(json['error']);
					}
					if (json['success'])
					{
						$('_reqStatus').innerHTML = "Authenticated, reloading...";
						setTimeout("location.href = 'index.php'", 1000);
					}
				}
			});
		}
		return false;
	},
	doLogout: function ()
	{
		$('_reqStatus').innerHTML = "Logging out, please wait...";
		new Ajax.Request('action.php', 
		{
			method: 'get',
			parameters: {
				reqTime: new Date().getTime(),
				action: Object.toJSON({action: 'Logout'})
			}
		});
	},
	
	_reloadTimeout: null,
	doReload: function ()
	{
		this._reloadTimeout = setTimeout("$('_reqStatus').innerHTML = 'Reloading, please wait...'; location.href = 'index.php';", 5000);
		$('_reqStatus').innerHTML = "Reload requested, please wait...";
		new Ajax.Request('action.php', 
		{
			method: 'get',
			parameters: {
				reqTime: new Date().getTime(),
				action: Object.toJSON({action: 'Reload'})
			}
		});
	},
	
	changeServer: function (server)
	{
		if (this._statusError)
		{
			this.doError("Can not change server, Monast is offline...<br>Please reload...");
			return;
		}
		$('_reqStatus').innerHTML = "Changing Server...";
		new Ajax.Request('action.php', 
		{
			method: 'get',
			parameters: {
				reqTime: new Date().getTime(),
				action: Object.toJSON({action: 'ChangeServer', server: server})
			}
		});
	},
	
	onKeyPressCliCommand: function (e)
	{
		if (e.keyCode == 13 && $('cliCommand').value.trim()) //Enter
			Monast.cliCommand();
	},
	cliCommand: function (command, updatecli)
	{
		if (Object.isUndefined(command))
		{
			command = $('cliCommand').value.trim();
			$('cliCommand').value = '';
		}
		
		if (Object.isUndefined(updatecli) || updatecli)
		{
			$('cliResponse').value += '\r\n> ' + command;
			new YAHOO.util.Scroll('cliResponse', {scroll: {to: [0, $('cliResponse').scrollHeight]}}, 0.5).animate();
		}
		
		if (command)
		{
			new Ajax.Request('action.php', 
			{
				method: 'get',
				parameters: {
					reqTime: new Date().getTime(),
					action: Object.toJSON({action: 'CliCommand', command: command})
				}
			});
		}
	},
	cliResponse: function (r)
	{
		r.response.each(function (line) {
			$('cliResponse').value += '\r\n' + line;
		});
		$('cliResponse').value += '\r\n';
		new YAHOO.util.Scroll('cliResponse', {scroll: {to: [0, $('cliResponse').scrollHeight]}}, 0.5).animate();
	},
	
	requestInfo: function (p_sType, p_aArgs, p_oValue)
	{
		var command = p_oValue;
		new Ajax.Request('action.php', 
		{
			method: 'get',
			parameters: {
				reqTime: new Date().getTime(),
				action: Object.toJSON({action: 'RequestInfo', command: command})
			}
		});
	},
	requestInfoResponse: function (r)
	{
		this.doAlert("<table class='requestInfo'><tr><td><pre>" + r.response.join("\n").replace(/\</g, '&lt;').replace(/\>/g, '&gt;') + "</pre></td></tr></table>");
		Monast.alertDialog.cfg.setProperty("fixedcenter", false);
		Monast.alertDialog.cfg.setProperty("constraintoviewport", false);
	}, 

	checkBoxSmartRestartListener: function(our_id)
	{
		our_checkbox = document.getElementById(our_id);
		Monast.NEED_DONGLE_RESTART = our_checkbox.checked;

		// Сохранение куков
		Monast._stateCookie.stateRestartCheckbox = our_checkbox.checked;
		YAHOO.util.Cookie.set(MONAST_COOKIE_KEY, Object.toJSON(Monast._stateCookie));		
		
		if (our_checkbox.checked)
		{
			Monast.DONGLE_RESTART_INTERVAL_ID = setInterval(Monast.restartDongle, Monast.MONAST_DONGLE_REST); // Раз в 10 сек
			Monast.cliCommand("dongle show devices", false);
			// Monast.doAlert("Send CLI comand");
		}
		else
		{
			clearInterval(Monast.DONGLE_RESTART_INTERVAL_ID);
			Monast.DONGLE_RESTART_INTERVAL_ID = null;
			// clear DONGLE_CHECK_HASH
			// for (var member in Monast.DONGLE_CHECK_HASH) delete myObject[member];
			
			// clear DONGLE_RESTART_HASH
			var keys = Monast.DONGLE_RESTART_HASH.keys();		
			for(var k = 0; k < keys.length; k++)
			{	
				var key = keys[k];
				Monast.DONGLE_RESTART_HASH.unset(key);
			}
		}				
	},
	
	checkDongle: function(event)
	{
		if (event.channeltype == 'Dongle')
		{
			// Monast.doAlert(event.peername);
			// Monast.cliCommand("dongle restart now " + event.peername, false);
			var our_el = Monast.DONGLE_RESTART_HASH.get(md5(event.channel));			
			// Monast.doAlert(our_el);
			// event.smscolor != Monast.COLORS.ORANGE запрет авто перезагр во время отправки СМС
			if ((event.statuscolor == Monast.COLORS.YELLOW && event.calls == 0 && event.smscolor != Monast.COLORS.YELLOW) || (event.statuscolor == Monast.COLORS.ORANGE && event.calls == 0 && event.smscolor != Monast.COLORS.YELLOW))      
			{				
				if (our_el == undefined)
				{
					// Monast.doAlert("Добавляем - " + event.peername);
					var our_el = new Array(new Date().getTime(), event.peername, 0, 0); // время, peername, статус , время перезагрузки модема
					Monast.DONGLE_RESTART_HASH.set(md5(event.channel), our_el);
					// Monast.DONGLE_RESTART_HASH.set("1", new Array(new Date().getTime(), "Проверка", 0));
				}
			}
			else
			{	
				// Monast.doAlert("Проверка перед удалением - " + event.peername);
				if (our_el != undefined)
				{
					// Удаляем элемент из массива. Это не зависший или уже перезагруженный
					// Monast.doAlert("Удаляем - " + event.peername);
					Monast.DONGLE_RESTART_HASH.unset(md5(event.channel));
				}
			}
		}
	},
	
	restartDongle: function()
	{
		// сравнивать будем по дате
		// Monast.doAlert("В проверку зашли!");
		var keys = Monast.DONGLE_RESTART_HASH.keys();
		
		for(var k = 0; k < keys.length; k++)
		{	
			var key = keys[k];						
			// Monast.doAlert(Monast.DONGLE_RESTART_HASH.get(key)[1]); // Должна быть проверка!
			
			our_el = Monast.DONGLE_RESTART_HASH.get(key);
			// Если прошло больше 30 секунд и времени регистрации модема в сети, тогда обновляем статус
			if ((new Date().getTime() - our_el[0]) > Monast.MONAST_DONGLE_CHECK && (new Date().getTime() - our_el[3]) > Monast.MONAST_DONGLE_TIME_REGISR )
			{
				our_el[2]++;
				
				// if (our_el[2] >= 2){Monast.cliCommand("dongle restart now " + our_el[1], false);}
				// if (our_el[2] >= 2){Monast.doAlert("dongle need restart " + our_el[1]);}
				
				// Если больше или равно 4, тогда значит что перезапускали уже 2 раза точно. 
				// Надо выводить алерт и статус устанавливать
				if (our_el[2] >= 4)
				{									
					Monast.doAlert("Dongle " + our_el[1] + " can't be restart. Need restart it manually!");
				//	Monast.userspeers.get(key).status = "Manually restart";  // Не работает 
				//	Monast.userspeers.get(key).statuscolor = Monast.COLORS.ORANGE;
				//	Monast.userspeers.get(key).smscolor = Monast.COLORS.ORANGE;
				}
				else if (our_el[2] >= 2) // Если больше или равно 2, тогда перезапускаем.
				{
					Monast.cliCommand("dongle restart now " + our_el[1], false);
					our_el[3] = new Date().getTime(); // время перезагрузки модема 
					// Monast.doAlert("Send restart Dongle: " + our_el[1] + " (" + (our_el[2]-1) + ") time restart: " + our_el[3]);
				}	
			}			
		}
	},
		
	viewMesageSignal: function (level) 
	{	
		var signal = Number(level);
		var title;
		if (signal == -51)	// подозрительно отличный сигнал
			{title = "Signal level: >= " + level + " dBm" + " - suspiciously good signal";}
		if (signal >= -75 && signal < -51)	// отличный сигнал
			{title = "Signal level: " + level + " dBm" + " - excellent signal";}
		if (signal >= -85 && signal < -75)	// хороший сигнал
			{title = "Signal level: " + level + " dBm" + " - good signal";}
		if (signal >= -95 && signal < -85)	// удовлетворительный сигнал
			{title = "Signal level: " + level + " dBm" + " - normal signal";}
		if (signal >= -100 && signal < -95)	// плохой сигнал
			{title = "Signal level: " + level + " dBm" + " - bad signal";}
		if (signal  < -100)	// очень плохой сигнал, либо отсутствует
			{title = "Signal level: " + level + " dBm" + " - very bad or no signal";}
	
		return title;
	}
};
