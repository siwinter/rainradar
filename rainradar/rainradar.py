#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
#
#  rainAlarm.py
#  Holt alle 5 min von https://wetter.com die aktuellen Regenradarwerte für einen bestimmten Ort
#  Ausgewertet wird dazu eine Tabelle in der Regenwerte bestimmten Farben zugeordnet sind. 
#  Diese Werte werden in das dictionary rains eingetragen
#  
#  Copyright 2021 swinter <swinter@swinter-ThinkPad-T420>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#
#  rudimentäre WebApp, basierend auf Tornado-Framework
#  liefert zwei Seiten aus
#  Mainhandler für '/' sagt "Hello Rain"
#  Rainhandler für '/now' liefert aktuelle Regenwerte in JSON-Format
#
#  Minütlich wird eine Webseite von www.wetter.com aufgerufen, die eine Regenradarauswertung für die nächsten zwei Stunden enthält.
#  Aus der Seite werden die erwarteten Regenmengen im fünf Minutenraster ermittel
#  Bereits 15 Minuten vor eintreffen des Regen, wird eine entsprechende MQTT-Meldung erzeugt (Payload = "on").
#  Nach dem Ende des Regens wird noch 15 min gewartet, bevor die Meldung zurückgenommen wird. (Payload = "off")
#  Der Alarm bleibt jedoch bestehen, wenn innerhalb der nächsten Stunde neuer Regen vorhergesagt ist
#  
import sys
import time
import tornado.ioloop
from tornado.httpclient import AsyncHTTPClient
import tornado.web
import paho.mqtt.publish as publish
import logging
from systemd import journal
from configparser import ConfigParser

#-----------------------------------------------------------------------
#  Config
#  
#-----------------------------------------------------------------------


serverPort  = 8095
mqttIP      = 'localhost'
mqttPort    = 1883
mqttTopic   = 'inf/rainAlarm'
logLev      = 'INFO'
logLevel    = logging.INFO
locationURI = '/deutschland/niederkruechten/kapelle/DE3205889.html#niederschlag'
log_txt = "run with default settings"


config = ConfigParser()

try:
	config.read(sys.argv[1])
	log_txt="run with setting from config file " + str(sys.argv[1])

except:
	log_txt="could not read config file " + str(sys.argv[1])
else:
	try:
		serverPort = int(config["SERVER"]["Port"])
	except:
#		serverPort = 8880
		log_txt="error reading config from file " + str(sys.argv[1])
	try:
		mqttIP = config["MQTT"]["IP"]
	except:
#		mqttIP = "localhost"
		log_txt="error reading config from file " + str(sys.argv[1])
	try:
		mqttPort = int(config["MQTT"]["Port"])
	except:
#		mqttPort    = 1884
		log_txt="error reading config from file " + str(sys.argv[1])
	try:
		mqttTopic = config["MQTT"]["Topic"]
	except:
#		mqttTopic    = 'RainAlarm'
		log_txt="error reading config from file " + str(sys.argv[1])
	try:
		logLev    = config["LOGGING"]["level"]
		if logLev == "DEBUG":
			logLevel    = logging.DEBUG
		if logLev == "INFO":
			logLevel    = logging.INFO
		if logLev == "WARNING":
			logLevel    = logging.WARNING
		if logLev == "ERROR":
			logLevel    = logging.ERROR
		if logLev == "CRITICAL":
			logLevel    = logging.CRITICAL
	except:
#		logLev      = "DEBUG"
#		logLevel    = logging.DEBUG
		log_txt="error reading config from file " + str(sys.argv[1])
	try:
		locationURI = config["LOCATION"]["URI"]
	except:
#		locationURI = '/deutschland/niederkruchten/overhetfeld/DE0007509013.html#niederschlag'
		log_txt="error reading config from file " + str(sys.argv[1])
	

#-----------------------------------------------------------------------
#  Logger
#
#-----------------------------------------------------------------------

log_format = ('[%(asctime)s] %(levelname)-8s %(name)-12s %(message)s')

logging.basicConfig(
	# Define logging level
	level=logLevel,
	# Declare the object we created to format the log messages
	format=log_format,
	# Declare handlers
	handlers=[
		journal.JournaldLogHandler()
	]
)

log = logging.getLogger(__name__)

log.info("start rainradar")
log.info(log_txt)
log.info("logLev: " + logLev)
log.info("locationURI: " + locationURI)
log.info("serverPort: " + str(serverPort))
log.info("mqttIP: " + mqttIP)
log.info("mgttPort: " + str(mqttPort))

rains = {}

rainVals = {
  "fff": 0,
  "bfd4ff": 1,
  "6699ff": 2,
  "004ce5": 3,
  "002673": 4,
  "ffa800": 5,
  "e60000": 6 }

delayTimer = 0		# to wait 15 min after rain ends then send "alarm off"
state = 0			# init, not raining

def mqttAlarm() :

	global delayTimer
	global state
	
	now = (time.localtime().tm_hour *60) + (time.localtime().tm_min // 5 *5) #Anzahl der Minuten des Tages auf 5min gerundet
	

	for nextRain in range(12) :
		nowString = str(now//60).zfill(2) + ":" + str(now%60).zfill(2)           #zfill für führende Nullen (1:2 -> 01:02)
		try:
			log.debug("at " + nowString + " rainvalue: " + str(rains[nowString]))
			if rains[nowString] > 0 :
				break
		except:
			log.warning("no rainvalue found")
		now = (now + 5) % (24*60) # Werte 00:00 - 23:59 (Falls durch Addition nächster Tag erreicht wird)
		
	log.debug("mqttAlarm: nextRain: " + str(nextRain))
	alarm = "off"
	if nextRain < 3 :
		state = 1	# raining
		alarm = "on"
		delayTimer = 15
		
	else :
		if state == 1 :						#raining
			alarm = "on"
			if nextRain > 10 :
				state = 2	# delay
				
		elif state == 2 :					# delay
			alarm = "on"
			if delayTimer < 1 :
				if nextRain > 10 :
					alarm = "off"
					state = 0   # init
			else :
				delayTimer = delayTimer - 1
				
		
	log.info("mqttAlarm: %s", alarm)
	try:
		publish.single(mqttTopic, alarm, hostname=mqttIP, port=mqttPort)
	except:
		log.warning("could not publish to " + mqttIP + " Port: " + str(mqttPort))
		

async def asynchronous_fetch():
	tornado.ioloop.IOLoop.current().add_timeout(time.time() + 60, lambda:asynchronous_fetch())   # call this function again in 60 secs 
	url = 'https://www.wetter.com' + locationURI
	try :
		response = await AsyncHTTPClient().fetch(url)                                            # fetch rainforcast
	except :
		log.warning("error fetch url")
	else: 
		if response.code == 200 :
			txt = str(response.body)
			global rains
			rains.clear()
			i= 0
			while True:
				i = txt.find("nowcast-table-item", i)
				if i>0 :
					i = txt.find("<span>", i) + 6	# find time  (17:20)
					j = txt.find("</span>", i)
					t = (txt[i:j])
					i = txt.find("#", i) + 1		# find rain colour
					j = txt.find(";", i)
					try :
						r = rainVals[txt[i:j]]		# get rain value from local table of values
					except :
						r = 1
					rains[t]=r						# add new key:vallue (exp: "17:20" : 2)
					
				else :
					mqttAlarm()
					break
		else:
			log.warning("fetch url return code " + str(response.code))


class RainHandler(tornado.web.RequestHandler):                           # webpage to deliver actual rain values in json-Format 
	def get(self):
		now = (time.localtime().tm_hour *60) + (time.localtime().tm_min // 5 *5) #Anzahl der Minuten des Tages auf 5min gerundet
	
		answer = "{ "
		for x in range(4) :
			nowString = str(now//60).zfill(2) + ":" + str(now%60).zfill(2)           #zfill für führende Nullen (1:2 -> 01:02)
			answer = answer + nowString + " : " + str(rains[nowString]) + "\n"
			now = (now + 5) % (24*60) # Werte 00:00 - 23:59 (Falls durch Addition nächster Tag erreicht wird)
		answer = answer + " }"
		self.write(answer)

class MainHandler(tornado.web.RequestHandler):                           # webpage says "Hello Rain"
	def get(self):
		self.write("Hello Rain")

def main():
	app = tornado.web.Application([ (r"/", MainHandler),(r"/now", RainHandler) ])
	app.listen(serverPort)    # Port Number
	log.info("start RainAlarm-App on Port " + str(serverPort))
	tornado.ioloop.IOLoop.current().add_timeout(time.time() + 60, lambda:asynchronous_fetch())
	tornado.ioloop.IOLoop.current().start()
	return 0

if __name__ == '__main__':
	import sys
	sys.exit(main())
