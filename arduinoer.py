from Managers import ArduinoManager
from Managers.LoggerManager import Logger
from Managers.FileManager import Process

from multiprocessing import Queue
from queue import Empty

import time
import configparser
import numpy as np
import logging

from enum import Enum

import sys, traceback

# How this works:
# arduino_process_main is the main function of this thread. It opens the 
# arduino port, setups, and finally starts the loop
# 			main -> setup -> loop
#
# The loop is where the real magic happens. It automatically starts the 
# arduino in STANDBY mode which main function is to listen to the secretary
# and log any errors. Only by a command coming from the secretary, the 
# the RUNNING state will start (or INIT_RUNNING). Any error that happens in 
# RUNNING (or INIT_RUNNING) will revert the state back to STANDBY and will 
# only allow to go back to RUNNING unless the errors are cleared by reseting
# them from a direct order coming from the secretary.
#
#			STANDBY -(if err = empty)-> INIT_RUNNING -> RUNNING
#				^											| (if error)
#				|___________________________________________|
#
# 			Secretary -('restart' cmd)-> Arduinoer
#				^							| (sends error)
#				|___________________________| (clears error)
#
# STATES INFORMATION:
# STANDBY 		: 	Listens to secreatry, and logs errors.
# INIT_RUNNING 	: 	Turns on the peltier, sets the desired temperature,
#					and starts the RUNNING state + all STANDBY functions
# RUNNING 		:   Intitialize a humidity measurement, retrieves the H/T
# 					measurement, and sends the data to the secretary + STANDBY
# END_RUNNING	: 	Turns off the peltier, and changes to STANDBY
class STATES(Enum):
	STANDBY 			= 0
	RUNNING 			= 1
	INIT_RUNNING 		= 2
	UNEXPECTED_END 		= 3
	INIT_PRE_COOLING 	= 4
	PRE_COOLING 		= 5
	INIT_COOLING 		= 6
	COOLING 			= 7
	INIT_POST_COOLING 	= 8
	POST_COOLING 		= 9
	SETUP 				= 10

def read_config():
	config = configparser.ConfigParser()

	with open('test_file.cfg') as f:
		config.read_file(f)

	return config['Peltier']

# Routine to grab humidity and temperature values.
def run_measurements(*, status, err):
	try:
		status['Manager'].initMeasurement()

		# Sleep to wait for the next measurements
		time.sleep(2)

		vals = status['Manager'].retrieveMeasurements()
		
		error = status['Manager'].retrieveError()
		if error is not None:
			raise Exception(error)

		status['OutQueue'].put({\
			'Data' : vals,
			'Error' : None, \
			'FatalError' : None,
			'CMD' : None})
			
		status['LatestTime'] 		= vals[0]
		status['LatestHumidity'] 	= vals[1]
		status['LatestTemp'] 		= vals[2]

		# Add values to buffers so loop can
		# analyze them
		index = status['BufferIndex']
		status['TimeBuffer'][index]		= vals[0]
		status['HumidityBuffer'][index] = vals[1]
		status['TempBuffer'][index] 	= vals[2]

		status['BufferIndex'] = index + 1
		if status['BufferIndex'] >= 200:
			status['BufferIndex'] = 0

		return (status, err)
	except Exception as error:
		print(f'[Arduino] Error while running measurements: {error}.')
		err = f'{err} {error}.'
		status['State'] = STATES.UNEXPECTED_END
		return (status, err)

# Listen to the secretary commands
def listen_to_secretary(*, status, err):
	man = status['Manager']
	inQueue = status['InQueue']
	outQueue = status['OutQueue']

	try:
		response = inQueue.get_nowait()

		if response['close']:
			print('[Arduino] Closing.')

			status['State'] = STATES.UNEXPECTED_END
			status['EndFlag'] = True

			return (status, err)

		# setState Command
		# Only two states to change:
		# Running (which start by going to INIT_PRE_COOLING)
		# and standby, which is required to go from setup
		elif response['cmd'] == 'setState':
			if response['value'] == 'STANDBY':
				status['State'] = STATES.UNEXPECTED_END

		# Retrieves errors, send to secretary, and resets them
		# only possible in standby mode
		elif response['cmd'] == 'restart':
			if status['State'] == STATES.STANDBY:
				err = f'{err} {man.retrieveError()}.'
				man.resetError()

				outQueue.put({\
					'Data' : None,
					'Error' : f'{err}', \
					'FatalError' : False,
					'CMD' : None})

				# Reset buffers, and related stuff
				status['TimeBuffer'] = np.zeros(200)
				status['TempBuffer'] = np.zeros(200)
				status['HumidityBuffer'] = np.zeros(200)
				status['LatestTime'] = 0.0
				status['LatestHumidity'] = 0.0
				status['LatestTemp'] = 0.0
				status['BufferIndex'] = 0


				err = ''

		# Commands that start with _ are commands that are not ment to be sent
		# by the user, only by other pieces of the software
		# Command -> '_donePreCoolingSiPMs'
		# The electrometer is done with all the SiPM pre-cooling measurements.
		elif response['cmd'] == '_donePreCoolingSiPMs':
			status['State'] = STATES.INIT_PRE_COOLING
		# Command -> '_doneMeasuringSiPMs'
		# The electrometer is done with all the SiPM I-V measurements.
		elif response['cmd'] == '_doneMeasuringSiPMs':
			status['State'] = STATES.INIT_POST_COOLING

		return (status, err)

	except Empty:
		return (status, err)
	except Exception as error:
		print(f'[Arduino] Error while listening to boss: {error}.')
		traceback.print_exc(file=sys.stdout)
		err = f'{err} {error}.'
		status['State'] = STATES.UNEXPECTED_END

		return (status, err)


# Main loop of this process. Similar to Arduino loop, get it?
def loop(*, status, commErr):
	TPC = float(status['Config']['Tpc'])
	TPC_TIME = float(status['Config']['TpcTime'])
	TC = float(status['Config']['Tc'])
	TC_TIME = float(status['Config']['TcTime'])
	HUMIDITY_THRESHOLD = int(status['Config']['HumidityThreshold'])

	outQueue = status['OutQueue']

	while True:

		# Listen to the secretary commands
		status, commErr = listen_to_secretary(status=status, err=commErr)

		state = status['State']

		# All states except setup measure the humidity/temp
		if state != STATES.SETUP:
			status, commErr = run_measurements(status=status, err=commErr)

		# Changes temperature to Tpc and starts the peltier.
		if state == STATES.INIT_PRE_COOLING:
			print('[Arduino] Changing to pre-cooling phase.')

			status['Manager'].setTemperature(TPC)
			status['Manager'].startCooling()
			status['State'] = STATES.PRE_COOLING

		# Monitors the humidity and temperature. If humidity below 5% 
		# and T = Tp stable for ~14 mins changes to COOLING phase
		elif state == STATES.PRE_COOLING:
			times = status['TimeBuffer']
			temps = status['TempBuffer']

			temps = temps[times > (status['LatestTime'] - TPC_TIME)]

			diff = np.sqrt((1/len(temps))*np.sum((temps-TPC)**2))
			# diff = np.abs(np.mean(temps) - Tpc) / Tpc

			if status['LatestHumidity'] < HUMIDITY_THRESHOLD and diff < 0.1: # in C
				status['State'] =  STATES.INIT_COOLING

		# Changes temperature to Tc
		elif state == STATES.INIT_COOLING:
			print('[Arduino] Changing to cooling phase.')

			status['Manager'].setTemperature(TC)
			status['State'] = STATES.COOLING

		# Monitors humidity. If hum higher than 5%, throw error
		# Monitors Temperature, checks if its stable at Tc
		# for ~1 min
		elif state == STATES.COOLING:
			times = status['TimeBuffer']
			temps = status['TempBuffer']

			temps = temps[times > (status['LatestTime'] - TC_TIME) ]

			diff = np.sqrt((1/len(temps))*np.sum((temps-TC)**2))
			# diff = np.abs(np.mean(temps) - Tpc) / Tpc

			if diff < 0.1: # In degrees
				status['State'] = STATES.INIT_RUNNING

			if status['LatestHumidity'] > HUMIDITY_THRESHOLD:
				print('[Arduino] Humidity reached unexpected high levels\
					during cooling phase. Moving to standby.')
				commErr = f'{commErr} Humidity reached unexpected high levels \
					during cooling phase. Moving to standby.'
				status['State'] = STATES.UNEXPECTED_END

		# Sends a command to the secretary and the secretary relies
		# the message to the electrometer if possible. Then, it starts
		# the measurements.
		elif state == STATES.INIT_RUNNING:
			print('[Arduino] Changing to running phase.')
			readyCommand = {\
				'process'			: Process.IV, \
				'close' 			: False, \
				'cmd' 				: '_temperatureReady', \
				'value'				: ''}

			outQueue.put({\
					'Data' 			: None, \
					'Error' 		: None, \
					'FatalError' 	: None,
					'CMD' 			: readyCommand })


			status['State'] = STATES.RUNNING

		# Only use here is to check for humidity levels.
		elif state == STATES.RUNNING:

			if status['LatestHumidity'] > HUMIDITY_THRESHOLD:
				print('[Arduino] Humidity reached unexpected high levels \
					during running phase. Moving to standby.')
				commErr = f'{commErr} Humidity reached unexpected high levels \
					during running phase. Moving to standby.'
				status['State'] = STATES.UNEXPECTED_END

		# Stops cooling.
		elif state == STATES.INIT_POST_COOLING:
			print('[Arduino] Changing to post-cooling phase.')
			status['Manager'].stopCooling()
			status['State'] = STATES.POST_COOLING

		# After I-V or H-T measurements are done
		# start the post_cooling or warming state.
		# Humidity is not meant to increase here either.
		elif state == STATES.POST_COOLING:
			if status['LatestHumidity'] > HUMIDITY_THRESHOLD:
				print('[Arduino] Humidity reached unexpected high levels \
					during post-cooling phase. Moving to standby.')
				commErr = f'{commErr} Humidity reached unexpected high levels \
					during post-cooling phase. Moving to standby.'
				status['State'] = STATES.UNEXPECTED_END

			# Lets say room temp is 20, change to standby,
			# and let the electrometer know we are in post-cooling.
			if status['LatestTemp'] > 20.0:

				postCoolCMD = {\
					'process'			: Process.IV, \
					'close' 			: False, \
					'cmd' 				: '_postcooling', \
					'value'				: ''}

				outQueue.put({\
					'Data' 			: None, \
					'Error' 		: None, \
					'FatalError' 	: None,
					'CMD' 			: postCoolCMD })


				print('[Arduino] Changing to standby.')
				status['State'] = STATES.STANDBY

		# Only meant to run if the run was interrupted or
		# ended abruptly
		elif state == STATES.UNEXPECTED_END:
			status['Manager'].stopCooling()
			status['State'] = STATES.STANDBY

		if status['EndFlag']:
			status['EndFlag'] = False
			break


		# Running at ~100 Hz
		time.sleep(1.0/100)

	return commErr



# Arduino code that measures the humidity/temperature measurements
# and controls the PID
# Intializes the arduino, waits for IV (might not be used later)
# and starts the main loop logic
#
# NOTE: the * at the begginning forces the function to be of the form:
# arduino_process_main(inQueue=smth, outQueue=other)
def arduino_process_main(*, inQueue, outQueue):

	# Makes sure all output gets written to a log and console.
	sys.stdout = Logger()

	status = {
		'Manager' : None,
		'Config' : None,
		'InQueue' : inQueue,
		'OutQueue' : outQueue,

		# Loop related items
		'State' : STATES.SETUP,
		'EndFlag' : False,
		'LatestTime' : None,
		'LatestTemp' : None,
		'LatestHumidity' : None,
		'TimeBuffer' : np.zeros(200),
		'TempBuffer' : np.zeros(200),
		'HumidityBuffer' : np.zeros(200),
		'BufferIndex' : 0
	}

	status['Manager'] = None
	status['Config'] = read_config()

	commulativeError = ''

	try:
		print('[Arduino] Initializing Arduino.')
		status['Manager'] = ArduinoManager.sipmArduino()
		status['Manager'].setup()

		# There needs to be some time bewteen the setup and loop
		# to allow the arduino to setup.
		time.sleep(5)

		# Start taking measurements of temperature/humidity
		print('[Arduino] Arduino starting in standby.')
		status['State'] = STATES.STANDBY
		commulativeError = loop(status=status, commErr=commulativeError)

	# Runs if any fatal error is seen.
	except Exception as err:
		print(f'[Arduino] Fatal Error: {err}.')
		outQueue.put({\
			'Data' : None,
			'Error' : f'{commulativeError} {err}.', \
			'FatalError' : True,
			'CMD' : None})
		traceback.print_exc(file=sys.stdout)

	# No fatal errors, send any errors if present.
	else:
		print(f'[Arduino] Closing with error: {commulativeError}')
		outQueue.put( {\
			'Data' 			: None, 					\
			'Error' 		: f'{commulativeError}.', 	\
			'FatalError' 	: False, 					\
			'CMD' 			: None })

	# If the arduinoer is closed in any way, open resources
	finally:

		if status['Manager'] is not None:
			# Stop cooling if program is stopped in any way
			# and open resources
			status['Manager'].close()
