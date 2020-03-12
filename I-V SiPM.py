from sipm_files import sipm_setup, sipm_arduino, sipm_measurements, sipm_voltage, sipm_dataTaking
from grapher import grapher_process
from arduinoer import ArduinoRoutine_process

from multiprocessing import Process, Queue
from queue import Empty

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
import numpy as np
import time
from itertools import count


		

# I-V equipment routine
def IVRoutine_process(toArd, toFile):
	port, rp_port = None, None

	try:
		port, rp_port = sipm_setup.setup(zeroCheck=True)

		meas = sipm_measurements.sipmMeasurements(port, rp_port)
		voltMan = sipm_voltage.sipmVoltage(port)

		time_vals = []
		current_vals = []
		voltage_vals = []
		total = 0
		dV = 0.25	# Voltage jump
		Vi = 0.0 	# Intial Voltage
		Vf = 0.0 	# Final Voltage
		n = 1000 	# Number of samples per voltage
		ni = 0 		# Should always start at 0

		## This was measured to be 300us
		C = 1.28e-9
		R = 500e3
		tauSiPM = 6*R*C 		# 6 = For a good settling time below 1%
		tauInstrument = 333e-3 	# Wort case settling time for 486 instrument

		tau = np.sqrt(tauSiPM*tauSiPM + tauInstrument*tauInstrument)

		# For the no voltage measurement.
		voltMan.multimeterState(False)
		voltMan.setVoltage(0)

		# Warm up
		# time.sleep(15*60)

		toArd.put(True)
		toFile.put([True, n*(1+(Vf-Vi)/dV)])
		while Vi <= Vf:
			voltMan.setVoltage(Vi)

			# Waiting for the voltage to settle
			time.sleep(tau)

			while ni < n:

				t, volt, curr = meas.measurementRoutine()

				toFile.put([[t, volt, curr], total, True])

				# time_vals.append(t)
				# voltage_vals.append(volt)
				# current_vals.append(curr)

				ni = ni + 1
				total = total + 1

			ni = 0
			Vi = Vi + dV


		voltMan.multimeterState(False)
		voltMan.setVoltage(0)

		toArd.put(False)
		toFile.put([None, None, False])

		# plt.subplot(2, 2, 1)
		# plt.plot(voltage_vals, current_vals, 'ro')
		# plt.xlabel('Voltage (V)')
		# plt.ylabel('Current (A)')

		# plt.subplot(2, 2, 2)
		# plt.plot(time_vals, current_vals)
		# plt.xlabel('time (s)')
		# plt.ylabel('Current (A)')

		# plt.subplot(2, 2, 4)
		# plt.plot(time_vals, voltage_vals)
		# plt.xlabel('time (s)')
		# plt.ylabel('Voltage (V)')

		# plt.show()
	finally:
		print('Closing ports...')
		if port is not None and rp_port is not None:
			sipm_setup.close(port, rp_port)
		
def FileRoutine_process(toIv, toArd, toGraph):
	file = None
	nameofMeasurements = 'ps_off_0v_nosipm_no_res'

	try:
		file = sipm_dataTaking.sipmFileManager('SiPMDataDB.hdf5')

		### Initial while-loop to start the program ###
		timeout = 60 # secs
		timeoutCounter = 0
		startTime = time.time()
		
		onGoing = False
		while not onGoing:
			time.sleep(1)
			timeoutCounter = (time.time() - startTime) 

			if timeoutCounter > timeout:
				raise Exception('Timeout from main process. (FileManager)')

			try:
				items = toIv.get_nowait()
				# item[0] -> start
				# item[1] -> num of elements
				onGoing	= items[0]
				file.create_dataset(items[1], nameofMeasurements)
			except Empty as err:
				pass

		###
		### Saving data to file while-loop ###

		while onGoing:
			time.sleep(0.1)
			try:
				items = toIv.get_nowait()
				# item[0] -> value to save
				# item[1] -> index
				# item[2] -> should stop
				if items[0] is not None:
					file.add_IV(items[0], items[1])
					toGraph.put([items[0][0], None, items[0][1], items[0][2], None, None, True])

				onGoing = items[2]
			except Empty as err:
				pass

			try:
				items = toArd.get_nowait()
				# item[0] -> value to save
				# item[1] -> index
				file.add_HT(items[0], items[1])
				toGraph.put([None, items[0][0], None, None, items[0][1], items[0][2], True])
			except Empty as err:
				pass
	except:
		print('Error with the file manager. Deleting previous data base.')
		file.delete_dataset()
	finally:
		if file is not None:
			file.close()

def main():
	try:
		iv_ard_Queue = Queue()
		iv_file_Queue = Queue()
		file_ard_Queue = Queue()
		file_graph_Queue = Queue()

		iv_process = Process(target=IVRoutine_process, args=(iv_ard_Queue, iv_file_Queue))
		# Arduino code that measures the humidity/temperature measurements
		humtemp_process = Process(target=ArduinoRoutine_process, args=(iv_ard_Queue, file_ard_Queue))
		file_process = Process(target=FileRoutine_process, args=(iv_file_Queue, file_ard_Queue, file_graph_Queue))
		# Code that plots every data avaliable
		g_process = Process(target=grapher_process, args=(file_graph_Queue,))
		
		iv_process.start()
		humtemp_process.start()
		file_process.start()
		g_process.start()

		iv_process.join()
		humtemp_process.join()
		file_process.join()
		g_process.join()

		# IVRoutine(measManager, voltManager)

		print('Done!')
	finally:
		print('Uhhhh')

if __name__ == '__main__':
    main()