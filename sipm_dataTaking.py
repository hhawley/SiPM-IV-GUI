import pandas as pd
import time
import os

class sipmDataTaking:

	def __init__(self, filedir):
		self.filedir = filedir
		self.measurements = ''

		if os.path.isfile(filedir):
			self.measurements = pd.read_csv(filedir, names=['time', 'voltage', 'current'], header=0)
		else:
			open(filedir, 'w')
			self.measurements = pd.read_csv(filedir, names=['time', 'voltage', 'current'], header=0)

	def add(self, meas):
		ttt = {'time': meas[0], 'voltage': meas[1], 'current': meas[2]}

		self.measurements = self.measurements.append(ttt, ignore_index=True)

	def save(self):
		self.measurements.to_csv(self.filedir, mode='w', index=False)
