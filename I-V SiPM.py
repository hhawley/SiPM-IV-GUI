import sipm_setup
import sipm_measurements
import sipm_voltage
import sipm_dataTaking

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
import numpy as np
import time
from itertools import count

# plt.style.use('fivethirtyeight')
fileManager = sipm_dataTaking.sipmDataTaking("../../Data/sipm_Test_longtermstability.csv")
time_vals = []
current_vals = []
voltage_vals = []

index = count()

volt = 0.0
curr = 0.0

def animation(i):
	plt.cla()
	plt.plot(voltage_vals, current_vals, 'ro')

def measurementRoutine(meas):
	meas.prepMeasurements()
	meas.triggerInstruments()

	time, volt, curr = meas.makeFullMeasurement()

	if isinstance(curr, str):
		if curr == 'Overflow':
			meas.raisePicoammeterRange()

	while curr == 'Overflow':
		meas.prepMeasurements()
		meas.triggerInstruments()

		time, volt, curr = meas.makeFullMeasurement()

		if isinstance(curr, str):
			if curr == 'Overflow':
				meas.raisePicoammeterRange()

	return time, volt, curr

def BackgroundOverTime(meas, voltMan, port):
	#Prep DMM
	voltMan.setVoltage(0.001)

	for i  in range(0, 100):

		meas.prepMeasurements()
		meas.triggerInstruments()

		time, volt, curr = meas.makeFullMeasurement()

		if isinstance(curr, str):
			if curr == 'Overflow':
				meas.raisePicoammeterRange()

		while curr == 'Overflow':
			meas.prepMeasurements()
			meas.triggerInstruments()

			time, volt, curr = meas.makeFullMeasurement()

			if isinstance(curr, str):
				if curr == 'Overflow':
					meas.raisePicoammeterRange()

		print(volt)
		print(curr)

		voltage_vals.append(volt)
		current_vals.append(curr)

	voltMan.setVoltage(0)

	ani = FuncAnimation(plt.gcf(), animation, interval=100)
	# time.sleep(1)

	plt.tight_layout()
	plt.show()

def IVRoutine(meas, voltMan):
	dV = 0.25
	Vf = 40
	n = 5000

	## This was measured to be 300us
	C = 4*1.28e-9
	R = 500e3
	tauSiPM = 6*R*C
	tauInstrument = 333e-3 # Wort case settling time for 486 instrument

	tau = np.sqrt(tauSiPM*tauSiPM + tauInstrument*tauInstrument)

	Vi = 40

	ni = 0
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

	measManager = sipm_measurements.sipmMeasurements(port, rp_port)
	voltManager = sipm_voltage.sipmVoltage(port)

	#BackgroundOverTime(meas, port)
	IVRoutine(measManager, voltManager)

	sipm_setup.close(port, rp_port)
	print('Done!')
	

if __name__ == '__main__':
    main()