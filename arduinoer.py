from sipm_files import sipm_arduino

from multiprocessing import Process, Queue
from queue import Empty

import time
import configparser

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

# TODO: include temperature intialization
def set_temperature(queue, man):
	pass

# Main loop of this process. Similar to Arduino loop, get it?
def loop(iv_queue, file_queue, man):
	total = 0
	onGoing = True
	while onGoing:
		man.initMeasurement()

		# Sleep to wait for the next measurements
		time.sleep(2)

		vals = man.retrieveMeasurements()
		file_queue.put([vals, total])
		total = total + 1

		try:
			item = iv_queue.get_nowait()
			onGoing	= False
		except AttributeError:
			# Error that gets executed if iv_queue is None
			pass
		except Empty as err:
			onGoing	= True

# Arduino code that measures the humidity/temperature measurements
def arduino_process_main(toFile, toIV=None):
	arduinoManager = None

	configs = read_config()
	temperature = float(configs['Temperature'])

	try:
		print('[Arduino] Initializing Arduino.')
		arduinoManager = sipm_arduino.sipmArduino()
		arduinoManager.setup()

		time.sleep(5)

		# Start cooling immediately 
		print('[Arduino] Starting cooling.')
		arduinoManager.startCooling()

		# This part might be deprecated soon keeping it for now
		if toIV:
			wait_for_main(toIV)
		else:
			print('[Arduino] No I-V process detected. Going to loop.')

		# Start taking measurements of temperature/humidity
		print('[Arduino] Starting measurements.')
		loop(toIV, toFile, arduinoManager)
	except Exception as err:
		print('[Arduino] Error: %s' % err)

	finally:
		if arduinoManager is not None:
			# Stop cooling if program is stopped in any way
			# and open resources
			arduinoManager.close()


# config = configparser.ConfigParser()

# with open('file.cfg') as f:
# 	config.read_file(f)

# print(config['DEFAULT']['ServerAliveInterval'])