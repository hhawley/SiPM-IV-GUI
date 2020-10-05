from Managers import FileManager
from Managers.LoggerManager import Logger

from multiprocessing import Process, Queue
from queue import Empty
from enum import Enum

import time
import configparser
import os
import sys

# Secretary is meants as a main hub for the entire software.
# It mediates communication between the processes.
# 
# Commands between processes are lists, not strings.
# If the list has 1 element it is always assumed to be an
# error, otherwise, it is process specific.

def read_config():
	config = configparser.ConfigParser()

	with open('file.cfg') as f:
		config.read_file(f)

	return config['FILE']

# Processes enum
class Process(Enum):
	NONE = 1
	ARDUINO = 2
	GRAPHER = 3
	IV = 4
	SECRETARY = 5
	ALL = 6

# Read the the stdin/boss and prepares the data to be ran in the loop
# Commands from the CMD are expected to have the 
# following form:
# 1) One word. General command that is expected to do
# one single thing for the entire software. Ex.
# "close" prepares and closes all processes.
# 2) Two words. Command aimed at a specific process.
# Ex. "ARDUINO retrieveErrors" sends the command
# "retrieveErrors" to the arduinoer process.
# 3) Three words. Same as two words command with the
# addition of a value parameter. Ex. "ARDUINO setTemperature 10"
def listen_to_boss(*, queue, err):
	response = { \
		'process'	: Process.NONE, \
		'close' 	: False, 		\
		'cmd' 		: '', 			\
		'value'		: ''}

	try:
		cmd = queue.get_nowait()

		if len(cmd) == 1:
			response['cmd'] = cmd[0]
		elif len(cmd) == 2:
			response['process'] = Process[cmd[0]]
			response['cmd'] = cmd[1]
		elif len(cmd) >= 3:
			response['process'] = Process[cmd[0]]
			response['cmd'] = cmd[1]
			response['value'] = cmd[2]

		response['close'] = (response['cmd'] == 'close')
			
		return (response, err)
		
	except Empty as error:
		return (None, err)
	except Exception as error:
		raise error

def listen_to_queue(*, queue, err):
	if queue is None:
		return (None, err)

	try:
		items = queue.get_nowait()
		return (items, err)
	except Empty as error:
		return (None, err)
	except Exception as error:
		raise error

# Grabs the response or command and relays to the
# other processes.
def relay_message(*, response, queues):
	ardOutQueue = queues['ArduinoOut']
	ivOutQueue = queues['ElectrometerOut']
	graQueue = queues['Grapher']

	if response is not None:
		if response['process'] == Process.ARDUINO:
			if ardOutQueue is not None:
				ardOutQueue.put(response)
		elif response['process'] == Process.IV:
			if ivOutQueue is not None:
				ivOutQueue.put(response)
		elif response['process'] == Process.GRAPHER:
			graQueue.put(response)
		elif response['process'] == Process.SECRETARY:
			pass # What to do here
		elif response['process'] == Process.ALL:
			graQueue.put(response)
			if ardOutQueue is not None:
				ardOutQueue.put(response)
			if ivOutQueue is not None:
				ivOutQueue.put(response)

def loop(file, graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, \
	ivInQueue, commErr):
	### Saving data to file while-loop ###
	print('[File] Starting listening.')
	onGoing = True
	isRunning = False

	# Loop config bits
	config = read_config()
	
	endRunByTime = config.getboolean('EndRunTimeCondition')
	startTime = time.time()
	endTime = float(config['EndRunTime'])

	while onGoing:
		# Run at ~100 Hz
		time.sleep(1.0/100)

		#   BOSS LOOP  #
		# Listens to CMD, parses the command, and sends it around.
		response, commErr = listen_to_boss(queue=bossQueue, err=commErr)

		relay_message(response = response, queues = { \
			'ArduinoOut' : ardOutQueue, \
			'ElectrometerOut' : ivOutQueue, \
			'Grapher' : graQueue })

		if response is not None:
			if response['close']:
				close(file, \
					graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, \
						ivInQueue, commErr)
				# Only way to stop the while loop
				onGoing = False

			# One word commands
			# Restarts the system in case of an error.
			if response['cmd'] == 'restart':
				commErr = restart(file, \
					graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, \
						ivInQueue, commErr)
			# Sets the arduino and electrometer in standby mode.
			elif response['cmd'] == 'standby':
				standbyCMD = { \
					'process'	: Process.ALL, 	\
					'close' 	: False, 		\
					'cmd' 		: 'setState', 	\
					'value'		: 'STANDBY'}

				if ardOutQueue is not None:
					ardOutQueue.put(standbyCMD)

				if ivOutQueue is not None:
					ivOutQueue.put(standbyCMD)

			# Starts the system.
			elif response['cmd'] == 'run':
				isRunning = True

				runCMD = { \
					'process'	: Process.ALL, 	\
					'close' 	: False, 		\
					'cmd' 		: 'setState', 	\
					'value'		: 'RUNNING'}

				if ardOutQueue is not None:
					ardOutQueue.put(runCMD)

				if ivOutQueue is not None:
					ivOutQueue.put(runCMD)

			# Debug command to let the arduino know we are done with the
			# measurements.
			elif response['cmd'] == 'done':
				cmd = { \
					'process'	: Process.ARDUINO, 	\
					'close' 	: False, 			\
					'cmd' 		: 'done', 			\
					'value'		: ''}

				if ardOutQueue is not None:
					ardOutQueue.put(cmd)


		################

		#   IV LOOP    #
		items, commErr = listen_to_queue(queue=ivInQueue, err=commErr)
		if items is not None:
			if items['Data'] is not None:
				data = items['Data']

				# data[0] = time
				# data[1] = voltage
				# data[2] = current
				file.add_IV(data)
				graQueue.put([data[0], None, data[1], data[2], None, None])

			if items['Error'] is not None:
				commErr = f'{commErr} Electrometer returned error: {items["Error"]}'

			if items['FatalError'] is not None:
				if items['FatalError']:
					# If a fatal error is present in any of the
					# other threads. We close. 
					raise Exception('Electrometer returned with a fatal error.')

			if items['CMD'] is not None:
				cmd = items['CMD']

				relay_message(response = cmd, queues = { \
					'ArduinoOut' : ardOutQueue, \
					'ElectrometerOut' : ivOutQueue, \
					'Grapher' : graQueue })

		################

		# ARDUINO LOOP #
		items, commErr = listen_to_queue(queue=ardInQueue, err=commErr)
		if items is not None:
			if items['Data'] is not None:
				data = items['Data']

				file.add_HT(data)
				graQueue.put([None, data[0], None, None, data[1], data[2]])

			if items['Error'] is not None:
				commErr = f'{commErr} Arduino returned error: {items["Error"]}'


			if items['FatalError'] is not None:
				if items['FatalError']:
					# If a fatal error is present in any of the
					# other threads. We close. 
					raise Exception('Arduino returned with a fatal error.')

			if items['CMD'] is not None:
				cmd = items['CMD']

				relay_message(response = cmd, queues = { \
					'ArduinoOut' : ardOutQueue, \
					'ElectrometerOut' : ivOutQueue, \
					'Grapher' : graQueue })


		################

		# RUNNING LOOP #
		################ Things done in the loop of secretary.

		# Nothing to see for now.

		################

# Sends a command and listens for a reply from the arduino and
# electrometer.
def send_and_listen(cmd, graQueue, bossQueue, ardOutQueue, ardInQueue, \
	ivOutQueue, ivInQueue, commErr):

	if ardOutQueue is not None:
		ardOutQueue.put(cmd)

		try:
			response = ardInQueue.get(timeout=5)
			if response is not None:
				if response['Error'] is not None:
					commErr = f'{commErr} {response['Error']}'

		except Empty:
			commErr = f'{commErr} Arduino did not return a response.'
		except Exception as err:
			commErr = f'{commErr} {err}.'
			print(f'[File] Error while listening to Arduino: {err}.')

	if ivOutQueue is not None:
		ivOutQueue.put(cmd)

		try:
			response = ivInQueue.get(timeout=5)
			if response is not None:
				if response['Error'] is not None:
					commErr = f'{commErr} {response['Error']}'

		except Empty:
			commErr = f'{commErr} Electrometer did not return a response.'
		except Exception as err:
			commErr = f'{commErr} {err}.'
			print(f'[File] Error while listening to Electroemeter: {err}.')

	if graQueue is not None:
		graQueue.put(cmd)

	return commErr

# Sends a close command to all processes 
def close(file, graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, \
	ivInQueue, commErr):
	print('[File] Closing everything.')

	closeResponse = { \
		'process'	: Process.ALL, 	\
		'close' 	: True, 		\
		'cmd' 		: 'close', 		\
		'value'		: '' }

	commErr = send_and_listen(closeResponse, \
		graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, ivInQueue, commErr)

	# Finally, add any errors that were
	# present in the run.
	if file is not None:
		file.add_attribute('Error', commErr)

	return commErr

def restart(file, graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, \
	ivInQueue, commErr):
	print('[File] Restarting everything.')

	restartResponse = { \
		'process'		: Process.ALL, 	\
		'close' 		: False, 		\
		'cmd' 			: 'restart', 	\
		'value'			: '' }

	# Retrieve the errors from all the processes.
	commErr = send_and_listen(restartResponse, \
		graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, ivInQueue, commErr)

	# Save errors to file.
	if file is not None:
		file.add_attribute('Error', commErr)

	# Reset the error as it was saved to previous 'run'.
	commErr = ''

	# 'resets' file but in reality it starts another run.
	if file is not None:
		file.reset()

	# Should be empty but we are keeping a standard.
	return commErr

def file_process_main(*, bossQueue, graQueue, ardOutQueue=None, ardInQueue=None, \
	ivOutQueue=None, ivInQueue=None):
	
	# Makes sure all output gets written to a log and console.
	sys.stdout = Logger()

	file = None
	commulativeError = ''

	# Only three config for now. Database name, file name and comment
	# Maybe expand to include number of data points, time, etc
	configs = read_config()
	db_name = configs['DBName']
	name_of_measurements = configs['FileName']
	comment = configs['Comment']

	try:
		# File creation/initialization
		print('[File] Setting up database.')
		file = FileManager.sipmFileManager(db_name)
		file.create_dataset(name_of_measurements)
		file.add_attribute('Comment', comment)

		loop(file, graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, \
			ivInQueue, commulativeError)
		
	# If an error occurred during secretary, the best thing to do 
	# is to delete everything and restart the software.
	# Before closing, we retrieve all the errors if possible.
	except Exception as err:
		print('[File] Error with the file manager. Deleting previous data base.')
		print(f'[File] Error: {err}.')
		commulativeError = f'{commulativeError} {err}.'
		
		# If the file broke the error will not be saved.
		# In fact, nothing will.
		close(file, graQueue, bossQueue, ardOutQueue, ardInQueue, ivOutQueue, \
			ivInQueue, commulativeError)

		if file is not None:
			file.delete_dataset()
			
	# Open resources.
	finally:
		if file is not None:
			file.close()