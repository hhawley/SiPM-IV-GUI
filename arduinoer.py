from sipm_files import ArduinoManager

from multiprocessing import Process, Queue
from queue import Empty

import time
import configparser

from enum import Enum

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
# from the secretary.
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

class STATES(Enum):
	STANDBY=0
	RUNNING=1
	INIT_RUNNING=2

def read_config():
	config = configparser.ConfigParser()

	with open('file.cfg') as f:
		config.read_file(f)

	return config['Peltier']

def run_measurements(state, total, man, outQueue, err):
	try:

		man.initMeasurement()

		# Sleep to wait for the next measurements
		time.sleep(2)

		vals = man.retrieveMeasurements()
		outQueue.put([vals, total])

		total = total + 1

		return (True, STATES.RUNNING, err)
	except Exception as error:
		print(f'[Arduino] Error while running measurements {error}.')
		err = f'{err}. {error}'
		return (True, STATES.STANDBY, err)

# Listens to command from the boss (you)
def listen_to_Boss(state, man, inQueue, outQueue, err):
	outState = state
	try:
		response = inQueue.get_nowait()
		print(response)

		if response['close']:
			print('[Arduino] Closing.')
			inQueue.task_done()
			return (False, STATES.STANDBY, err)
		
		elif response['cmd'] == 'setTemperature':
			man.setTemperature(float(response['value']))

		# Only change the state to RUNNING if there are no errors	
		elif response['cmd'] == 'setState':
			if response['value'] == 'RUNNING' and err == '':
				print(f'[Arduino] Changing to { response["value"] }')
				outState = STATES.INIT_RUNNING
			elif response['value'] == 'STANDBY':
				print(f'[Arduino] Changing to { response["value"] }')
				outState = STATES.STANDBY

		# Retrieves errors, send to secretary, and resets them
		# only possible in standby mode
		elif response['cmd'] == 'restart':
			if state == STATES.STANDBY:
				err = f'{err}. {man.retrieveError()}'
				man.resetError()

				outQueue.put([err])
				# Waits until secretary finishes processing
				# outQueue.join()
				err = ''

		inQueue.task_done()

		return (True, outState, err)

	except Empty:
		return (True, outState, err)
	except Exception as error:
		print(f'[Arduino] Error while listening to boss: {error}')
		err = f'{err}. {error}'
		return (True, STATES.STANDBY, err)


# Main loop of this process. Similar to Arduino loop, get it?
def loop(man, inQueue, outQueue, commErr):
	total = 0
	onGoing = True
	status = True
	state = STATES.STANDBY

	while onGoing:

		if state == STATES.RUNNING:
			status, state, commErr = run_measurements(state, total, man, outQueue, commErr)
			onGoing = (onGoing and status)
		elif state == STATES.INIT_RUNNING:
			man.startCooling()
			state = STATES.RUNNING

		# Only stops if boss says so
		# and ALWAYS listens to you ;)
		status, state, commErr = listen_to_Boss(state, man, inQueue, outQueue, commErr)
		onGoing = (onGoing and status)

		# Running at 100 Hz
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
	arduinoManager = None
	commulativeError = ''

	configs = read_config()
	temperature = float(configs['Temperature'])

	try:
		print('[Arduino] Initializing Arduino.')
		arduinoManager = ArduinoManager.sipmArduino()
		arduinoManager.setup()

		time.sleep(5)

		# Start taking measurements of temperature/humidity
		print('[Arduino] Arduino starting in standby.')
		commulativeError = loop(arduinoManager, inQueue, outQueue, commulativeError)

	except Exception as err:
		print(f'[Arduino] Error: {err}')
		commulativeError = f'{commulativeError}. {err}'

	# If the arduinoer is closed in any way, send all errors (if any)
	# and open resources
	finally:
		toFile.put([commulativeError])

		if arduinoManager is not None:
			# Stop cooling if program is stopped in any way
			# and open resources
			arduinoManager.close()
