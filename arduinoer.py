from sipm_files import ArduinoManager

from multiprocessing import Process, Queue
from queue import Empty

import time
import configparser

from enum import Enum

class STATES(Enum):
	STANDBY=0
	RUNNING=1

def read_config():
	config = configparser.ConfigParser()

	with open('file.cfg') as f:
		config.read_file(f)

	return config['Peltier']

# If timeout = 0, never times out and waits forever.
def wait_for_main(queue, timeout=15*60):
	timeoutCounter = 0
	startTime = time.time()
	onGoing = False

	while not onGoing:
		time.sleep(0.5)

		if timeout != 0:
			timeoutCounter = (time.time() - startTime) 

			if timeoutCounter > timeout:
				raise Exception('Timeout from main process. (FileManager)')

		try:
			item = queue.get_nowait()
			onGoing	= True
		except Empty as err:
			onGoing	= False
	

def runMeasurements(state, error, file_queue, man, total):
	try:
		print('[Arduino] Starting cooling.')

		man.startCooling()
		man.initMeasurement()

		# Sleep to wait for the next measurements
		time.sleep(2)

		vals = man.retrieveMeasurements()
		file_queue.put([vals, total])
		total = total + 1

		return True
	except Exception as e:
		print('[Arduino] Error while running measurements %s' % e)
		error = error + ('%s' % e)
		state = STATES.STANDBY

# Listens to command from the boss (you)
def listenToBoss(state, error, file_queue, man):
	try:
		response = file_queue.get_nowait()

		if response['close']:
			print('[Arduino] Closing.')
			return False
		
		elif response['cmd'] == 'setTemperature':
			man.setTemperature(float(response['value']))

		# Only change the state to RUNNING if there are no errors	
		elif response['cmd'] == 'setState':
			if response['value'] == 'RUNNING' and error == '':
				state = STATES.RUNNING
			elif response['value'] == 'STANDBY':
				state = STATES.STANDBY

		elif response['cmd'] == 'retrieveErrors':
			if state == STATES.STANDBY:
				error = error + man.retrieveError()
				man.resetError()

				file_queue.put([error])
				error = ''

		return True

	except Empty as err:
		return True
	except Exception as e:
		print('[Arduino] Error while listening to boss: %s' % e)
		error = error + ('%s' % e)
		state = STATES.STANDBY


# Main loop of this process. Similar to Arduino loop, get it?
def loop(iv_queue, file_queue, man):
	total = 0
	onGoing = True
	status = True
	state = STATES.STANDBY
	error = ''

	while onGoing:

		if state == STATES.RUNNING:
			status = runMeasurements(state, error, file_queue, man, total)
			onGoing = (onGoing and status)

		# Only stops if boss says so
		# and ALWAYS listens to you ;)
		status = listenToBoss(state, error, file_queue, man)
		onGoing = (onGoing and status)

		try:
			item = iv_queue.get_nowait()
			onGoing	= False
		except AttributeError:
			# Error that gets executed if iv_queue is None
			pass
		except Empty as err:
			pass
		except Exception as e:
			error = error + ('%s' % e)



# Arduino code that measures the humidity/temperature measurements
# and controls the PID
def arduino_process_main(toFile, toIV=None):
	arduinoManager = None

	configs = read_config()
	temperature = float(configs['Temperature'])

	try:
		print('[Arduino] Initializing Arduino.')
		arduinoManager = ArduinoManager.sipmArduino()
		arduinoManager.setup()

		time.sleep(5)

		# This part might be deprecated soon keeping it for now
		if toIV:
			wait_for_main(toIV)
		else:
			print('[Arduino] No I-V process detected. Going to loop.')

		# Start taking measurements of temperature/humidity
		print('[Arduino] Arduino starting in standby.')
		loop(toIV, toFile, arduinoManager)

	except Exception as err:
		print('[Arduino] Error: %s' % err)

	finally:
		if arduinoManager is not None:
			# Stop cooling if program is stopped in any way
			# and open resources
			arduinoManager.close()