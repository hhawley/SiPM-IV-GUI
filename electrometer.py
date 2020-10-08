from Managers import IVEquipmentManager
from Managers.FileManager import Process 

from multiprocessing import Queue
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

class STATES(Enum):
	STANDBY 			= 0
	RUNNING 			= 1
	INIT_RUNNING 		= 2
	UNEXPECTED_END 		= 3
	SETUP 				= 4
	FINISH_SIPMS		= 5
	PRE_COOLING 		= 6
	POST_COOLING		= 7

def read_config():
	config = configparser.ConfigParser()

	with open('test_file.cfg') as f:
		config.read_file(f)

	return config['ELECTROMETER']

# Listen to the secretary commands
def listen_to_secretary(*, status, err):
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
				status['State'] = STATES.PRE_COOLING
			if response['value'] == 'STANDBY':
				print(f'[Electrometer] Changing to { response["value"] }.')
				status['State'] = STATES.UNEXPECTED_END

		# Retrieves errors, send to secretary, and resets them
		# only possible in standby mode
		elif response['cmd'] == 'restart':
			if status['State'] == STATES.STANDBY:
				err = f'{err} {man.retrieveError()}.'
				man.resetError()

				outQueue.put({\
					'Data' 			: None, 	\
					'Error' 		: err, 		\
					'FatalError' 	: False, 	\
					'CMD' 			: None })
				err = ''

		# Command -> 'next'
		# Allows to move to the next SiPM if the arduinoer authorized it.
		elif response['cmd'] == 'next':
			if status['TemperatureReady'] and not status['PostCoolingReady']:
				status['State'] = STATES.INIT_RUNNING
			elif not status['TemperatureReady'] and status['PostCoolingReady']:
				status['State'] = STATES.POST_COOLING
			elif not status['TemperatureReady'] and not status['PostCoolingReady']:
				status['State'] = STATES.PRE_COOLING

			print('[Electrometer] Moving to the next SiPM cell.')

		# Commands that start with _ are commands that are not ment to be sent
		# by the user, only by other pieces of the software
		elif response['cmd'] == '_postcooling':
			status['PostCoolingReady'] = True
			status['State'] = STATES.POST_COOLING
		
		elif response['cmd'] == '_temperatureReady':
			status['TemperatureReady'] = True
			status['State'] = STATES.INIT_RUNNING
			print('[Electrometer] Arduino has authorized the SiPM measurements.')

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

	# Voltage routine constants #
	NUM_SIPMS_TEST = int(status['Config']['NumSiPMsToTest'])
	DIFF_VOLT 	= float(status['Config']['dV'])
	INIT_VOLT 	= float(status['Config']['Vi'])
	FINAL_VOLT	= float(status['Config']['Vf'])
	NUM_MEAS_PER_DV  = int(status['Config']['n'])

	Vi = INIT_VOLT
	ni = 0
	total = 0

	## This was measured to be 300us
	SYST_C = 4*1.28e-9
	SYST_R = 500e3
	SIPM_TAU = 6*SYST_R*SYST_C	# 6 = For a good settling time below 1%
	SYST_TAU = 333e-3 		# Worst case settling time for 486 instrument

	TOTAL_TAU = np.sqrt(SIPM_TAU*SIPM_TAU + SYST_TAU*SYST_TAU)
	#	

	while True:

		state = status['State']

		# Listen to the secretary commands
		status, err = listen_to_secretary(status=status, err=err)

		# Pre-cooling phase where all the SiPM cells are measured,
		# then the arduinoer is let known to start the pre-cooling phase
		# only if all the cells have been measured.
		if state == STATES.PRE_COOLING:

			print('[Electrometer] Taking pre-cooling measurements. This blocks \
the electrometer and arduinoer.')
			
			# status['Manager'].SetVoltage(53.5, limit=True)
			status['Manager'].SetVoltage(0, limit=True)
			status['Manager'].VoltageOn()

			# Let the voltage supply settle for a it.
			time.sleep(5)

			for i in range(0, 10):
				t, volt, curr = status['Manager'].MeasurementRoutine()
				status['OutQueue'].put({ \
						'Data' 			: [t, volt, curr, numSiPMsTested], \
						'Error' 		: None, \
						'FatalError' 	: None,
						'CMD' 			: None })

			# Set the power supply to standby
			status['Manager'].SetVoltage(0.0)
			status['Manager'].VoltageOff()
			
			numSiPMsTested += 1
			status['State'] = STATES.STANDBY

			if numSiPMsTested >= NUM_SIPMS_TEST:
				numSiPMsTested = 0
				print('[Electrometer] Finished the pre-cooling measurements for \
all SiPMs.')

				precoolCMD = {\
					'process'	: Process.ARDUINO,			\
					'close' 	: False,					\
					'cmd' 		: '_donePreCoolingSiPMs',	\
					'value' 	: ''}

				outQueue.put({\
					'Data' 			: None, \
					'Error' 		: None, \
					'FatalError' 	: None,
					'CMD' 			: precoolCMD })

			else:
				print(f'[Electrometer] Finished pre-cooling measurements for SiPM {numSiPMsTested}')
				print('[Electrometer] Type \'next\' to start measuring the next SiPM.')
		# Init running just waits until the arduino is done
		# with the temperature and humidity.
		elif state == STATES.INIT_RUNNING and status['TemperatureReady']:

			# Set current limit to 25mA
			print('[Electrometer] Starting measurement routine. Electrometer \
is blocking.')

			status['Manager'].SetToLowestRange()
			status['Manager'].SetVoltage(0.0)
			status['Manager'].VoltageOn()

			status['State'] = STATES.RUNNING


		# I-V Measurements
		elif state == STATES.RUNNING and numSiPMsTested < NUM_SIPMS_TEST:

			## Measurement routine ##
			while Vi <= FINAL_VOLT:
				status['Manager'].SetVoltage(Vi, limit=True)

				# Wait for settling time.
				time.sleep(TOTAL_TAU)

				# Take measurements for the given voltage.
				while ni < NUM_MEAS_PER_DV:
					
					t, volt, curr = status['Manager'].MeasurementRoutine()
					status['OutQueue'].put({ \
							'Data' 			: [t, volt, curr, numSiPMsTested], \
							'Error' 		: None, \
							'FatalError' 	: None,
							'CMD' 			: None })
					
					ni += 1
					total += 1
				# Once voltages are finished, raise voltage level
				
				ni = 0
				Vi += DIFF_VOLT
			
			# Once the measurements are done, raise num pmts,
			# reset variables.
			numSiPMsTested += 1

			Vi = INIT_VOLT
			ni = 0
			total = 0

			# Set the power supply to standby
			status['Manager'].SetVoltage(0)
			status['Manager'].VoltageOff()

			status['State'] = STATES.STANDBY

			print(f'[Electrometer] Finished measurements for SiPM #{numSiPMsTested}')

			if numSiPMsTested >= NUM_SIPMS_TEST:
				status['TemperatureReady'] = False
				numSiPMsTested = 0

				finishCommand = {\
					'process'	: Process.ARDUINO,			\
					'close' 	: False,					\
					'cmd' 		: '_doneMeasuringSiPMs',	\
					'value' 	: ''}

				outQueue.put({\
					'Data' 			: None, \
					'Error' 		: None, \
					'FatalError' 	: None,
					'CMD' 			: finishCommand })
			else:
				print('[Electrometer] Type \'next\' to start measuring the next SiPM.')

			## END Measurement routine##
		
		# This only gets executed if the arduinoer says its on post-cooling.
		elif state == STATES.POST_COOLING:
			print('[Electrometer] Taking post-cooling measurements. This blocks \
the electrometer.')

			status['Manager'].SetVoltage(0, limit=True)
			status['Manager'].VoltageOn()
			
			# Let the voltage supply settle for a it.
			time.sleep(5)

			for i in range(0, 10):
				t, volt, curr = status['Manager'].MeasurementRoutine()
				status['OutQueue'].put({ \
						'Data' 			: [t, volt, curr, numSiPMsTested], \
						'Error' 		: None, \
						'FatalError' 	: None,
						'CMD' 			: None })

			# Set the power supply to standby
			status['Manager'].SetVoltage(0.0)
			status['Manager'].VoltageOff()
			
			numSiPMsTested += 1
			status['State'] = STATES.STANDBY

			if numSiPMsTested >= NUM_SIPMS_TEST:
				numSiPMsTested = 0
				status['PostCoolingReady'] = False
				print('[Electrometer] Finished the post-cooling measurements for \
all SiPMs.')
				print('[Electrometer] All done!')

			else:
				print(f'[Electrometer] Finished post-cooling measurements for SiPM {numSiPMsTested}.')
				print('[Electrometer] Type \'next\' to start measuring the next SiPM.')


		elif state == STATES.UNEXPECTED_END:
			status['State'] = STATES.STANDBY

			# Never too sure.
			# Set the power supply to standby
			status['Manager'].SetVoltage(0.0)
			status['Manager'].VoltageOff()



		if status['EndFlag']:
			status['EndFlag'] = False
			break

def electrometer_process_main(*, inQueue, outQueue):

	status = {
		'Manager' 	: None,
		'Config' 	: None,
		'InQueue' 	: inQueue,
		'OutQueue' 	: outQueue,

		# Loop related items
		'State' 	: STATES.SETUP,
		'EndFlag' 	: False, # If code should end or not.
		'Debug' 	: False, # If in debug mode or not.
		'TemperatureReady'		: False, # Ready flag to start SiPM measurements.
		'PostCoolingReady'		: False  # Ready flag to allow post-cooling measurements.
	}

	status['Manager'] = None
	commulativeError = ''

	status['Config'] = read_config()

	try:
		print('[Electrometer] Initializing electrometer.')
		status['Manager'] = IVEquipmentManager.IVEquipmentManager(\
			status['Config'])

		# Enabled zero check
		status['Manager'].Setup(False)

		print('[Electrometer] Electrometer starting in standby.')
		print('[All] Type \'run\' to start the procedure.')

		commulativeError = loop(status=status, err=commulativeError)

	# Runs if any fatal error is seen.
	except Exception as err:
		
		print(f'[Electrometer] Fatal Error: {err}.')
		outQueue.put( {\
			'Data' 			: None, 						\
			'Error' 		: f'{commulativeError} {err}.', \
			'FatalError' 	: True, 						\
			'CMD' 			: None })

		traceback.print_exc(file=sys.stdout)

	# No fatal errors, send any errors if present.
	else:
		print(f'[Electrometer] Closing with error: {commulativeError}')
		outQueue.put( {\
			'Data' 			: None, 					\
			'Error' 		: f'{commulativeError}', 	\
			'FatalError' 	: False, 					\
			'CMD' 			: None })

	finally:
		if status['Manager'] is not None:
			status['Manager'].Close()

