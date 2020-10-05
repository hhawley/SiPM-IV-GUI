from Managers import IVEquipmentManager

from multiprocessing import Process, Queue
from queue import Empty

import time
import configparser
import numpy as np

from enum import Enum

import sys, traceback

# How this works:
# electrometer_process_main is the main function of this thread. It opens the
# port to the DMM, RPi, and picoammeter, setups, then starts in the loop
# that goes like
# 		main -> setup -> loop
#
# Loop is similar to Arduino loop or the main logic of the adquisition happens
# 

# Processes enum
class Process(Enum):
	NONE = 1
	ARDUINO = 2
	GRAPHER = 3
	IV = 4
	SECRETARY = 5
	ALL = 6

class STATES(Enum):
	STANDBY 			= 0
	RUNNING 			= 1
	INIT_RUNNING 		= 2
	UNEXPECTED_END 		= 3
	SETUP 				= 4
	FINISH_SIPMS		= 5

def read_config():
	config = configparser.ConfigParser()

	with open('file.cfg') as f:
		config.read_file(f)

	return config['ELECTROMETER']

# Once inside the electrometer_routine the electrometer is locked in it.
def electrometer_routine(*, status, err):

	print('[Electrometer] Starting measurement routine.')

	dV = float(status['Config']['dV'])
	Vi = float(status['Config']['Vi'])
	Vf = float(status['Config']['Vf'])
	n  = int(status['Config']['n'])
	ni = 0
	total = 0

	## This was measured to be 300us
	C = 4*1.28e-9
	R = 500e3
	tauSiPM = 6*R*C 		# 6 = For a good settling time below 1%
	tauInstrument = 333e-3 	# Wort case settling time for 486 instrument

	tau = np.sqrt(tauSiPM*tauSiPM + tauInstrument*tauInstrument)

	status['Manager'].VoltageOn()

	while Vi <= Vf:
		status['Manager'].SetVoltage(Vi)

		# Wait for settling time.
		time.sleep(tau)

		while ni < n:

			# Take measurements.
			t, volt, curr = status['Manager'].MeasurementRoutine()
			status['OutQueue'].put({ \
					'Data' : [t, volt, curr], \
					'Error' : None, \
					'FatalError' : None })
			

			ni = ni + 1
			total = total + 1

		ni = 0
		Vi = Vi + dV


	status['Manager'].VoltageOff()

	print('[Electrometer] Finished measurements.')
	return (status, err)

# Listens to command from the boss (you)
def listen_to_Boss(*, status, err):
	man = status['Manager']
	inQueue = status['InQueue']
	outQueue = status['OutQueue']

	try:
		response = inQueue.get_nowait()

		if response['close']:
			print('[Electrometer] Closing.')

			status['State'] = STATES.UNEXPECTED_END
			status['EndFlag'] = True

			return (status, err)

		# setState Command
		# Only two states to change:
		# Running (which start by going to INIT_PRE_COOLING)
		# and standby, which is required to go from setup
		elif response['cmd'] == 'setState':
			if response['value'] == 'RUNNING' and err == '':
				print(f'[Electrometer] Changing to { response["value"] }.')
				status['State'] = STATES.INIT_RUNNING

			elif response['value'] == 'STANDBY':
				print(f'[Electrometer] Changing to { response["value"] }.')
				status['State'] = STATES.UNEXPECTED_END

		# Retrieves errors, send to secretary, and resets them
		# only possible in standby mode
		elif response['cmd'] == 'restart':
			if status['State'] == STATES.STANDBY:
				err = f'{err} {man.retrieveError()}.'
				man.resetError()

				outQueue.put({\
					'Data' : None, \
					'Error' : err, \
					'FatalError' : False })
				err = ''

		return (status, err)

	except Empty:
		return (status, err)
	except Exception as error:
		print(f'[Electrometer] Error while listening to boss: {error}.')
		err = f'{err} {error}.'
		status['State'] = STATES.UNEXPECTED_END

		return (status, err)


def loop(*, status, err):
	
	numSiPMsTested = 0
	outQueue = status['OutQueue']

	while True:

		state = status['State']

		# Only stops if boss says so
		# and ALWAYS listens to you ;)
		status, err = listen_to_Boss(status=status, err=err)

		# Init running just waits until the arduino is done
		# with the temperature and humidity.
		# In DEBUG mode it goes straight into running.
		if state == STATES.INIT_RUNNING:
			if status['Debug']:
				status['State'] = STATES.RUNNING

		# I-V Measurements start
		elif state ==  STATES.RUNNING and numSiPMsTested < 4:
			numSiPMsTested += 1
			electrometer_routine(status=status, err=err)
			status['State'] = STATES.STANDBY

		elif state == STATES.UNEXPECTED_END:
			status['State'] = STATES.STANDBY

		elif state == STATES.FINISH_SIPMS:
			finishCommand = {\
				'process'	: Process.ARDUINO,	\
				'close' 	: False,			\
				'cmd' 		: 'done',			\
				'value' 	: ''}

			outQueue.put({\
				'Data' 			: None, \
				'Error' 		: None, \
				'FatalError' 	: None,
				'CMD' 			: finishCommand })

			status['State'] = STATES.STANDBY

		if numSiPMsTested == 4:
			# This can be considered as INIT_FINISH_SIPMS
			status['State'] =  STATES.FINISH_SIPMS



		if status['EndFlag']:
			status['EndFlag'] = False
			break

def electrometer_process_main(*, inQueue, outQueue):

	status = {
		'Manager' : None,
		'Config' : None,
		'InQueue' : inQueue,
		'OutQueue' : outQueue,

		# Loop related items
		'State' : STATES.SETUP,
		'EndFlag' : False,
		'Debug' : True
	}

	status['Manager'] = None
	commulativeError = ''

	status['Config'] = read_config()

	try:
		print('[Electrometer] Initializing electrometer.')
		status['Manager'] = IVEquipmentManager.IVEquipmentManager(\
			status['Config'])

		# Enabled zero check
		status['Manager'].Setup(True)

		commulativeError = loop(status=status, err=commulativeError)

	# Runs if any fatal error is seen.
	except Exception as err:
		
		print(f'[Electrometer] Fatal Error: {err}.')
		outQueue.put({\
			'Data' : None,
			'Error' : f'{commulativeError} {err}.', \
			'FatalError' : True})
		# traceback.print_exc(file=sys.stdout)

	# No fatal errors, send any errors if present.
	else:
		print(f'[Electrometer] Closing with error: {commulativeError}')
		outQueue.put({\
			'Data' : None,
			'Error' : f'{commulativeError}', \
			'FatalError' : False})

	finally:
		if status['Manager'] is not None:
			status['Manager'].Close()

