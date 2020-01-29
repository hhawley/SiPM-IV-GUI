import sipm_setup
import sipm_measurements
import sipm_voltage
import sipm_dataTaking
import sipm_arduino

from multiprocessing import Process, Queue

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
import numpy as np
import time
from itertools import count

# plt.style.use('fivethirtyeight')
fileManager = sipm_dataTaking.sipmDataTaking("../../Data/test.csv")
time_vals = []
current_vals = []
voltage_vals = []
onGoing = True

index = count()

volt = 0.0
curr = 0.0

def animation(i):
	plt.cla()
	plt.plot(voltage_vals, current_vals, 'ro')

def IVRoutine(meas, voltMan):
	dV = 0.25	# Voltage jump
	Vi = 40		# Initial Voltage
	Vf = 40.25 	# Final Voltage
	n = 10 		# Number of samples per voltage
	ni = 0 		# Should always start at 0

	## This was measured to be 300us
	C = 4*1.28e-9
	R = 500e3
	tauSiPM = 6*R*C 		# 6 = For a good settling time below 1%
	tauInstrument = 333e-3 	# Wort case settling time for 486 instrument

	tau = np.sqrt(tauSiPM*tauSiPM + tauInstrument*tauInstrument)

	while Vi <= Vf:
		voltMan.setVoltage(Vi)
		time.sleep(tau)

		while ni < n:

			t, volt, curr = measurementRoutine(meas)
			fileManager.add((t, volt, curr))

			time_vals.append(t)
			voltage_vals.append(volt)
			current_vals.append(curr)

			ni = ni + 1

		ni = 0
		Vi = Vi + dV


	voltMan.multimeterState(False)
	voltMan.setVoltage(0)

	fileManager.save()

	plt.subplot(2, 2, 1)
	plt.plot(voltage_vals, current_vals, 'ro')
	plt.xlabel('Voltage (V)')
	plt.ylabel('Current (A)')

	plt.subplot(2, 2, 2)
	plt.plot(time_vals, current_vals)
	plt.xlabel('time (s)')
	plt.ylabel('Current (A)')

	plt.subplot(2, 2, 4)
	plt.plot(time_vals, voltage_vals)
	plt.xlabel('time (s)')
	plt.ylabel('Voltage (V)')

	plt.show()
		

def main():
	port, rp_port = sipm_setup.setup(zeroCheck=False)

	try:
		measManager = sipm_measurements.sipmMeasurements(port, rp_port)
		voltManager = sipm_voltage.sipmVoltage(port)

		IVRoutine(measManager, voltManager)
		
		print('Done!')
	finally:
		print('Closing ports...')
		sipm_setup.close(port, rp_port)

if __name__ == '__main__':
    main()