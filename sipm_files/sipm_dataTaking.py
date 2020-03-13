import h5py
import time
import os
import datetime

class sipmFileManager:

	def __init__(self, filedir):
		self.filedir = filedir
		self.dbName = ''

		if os.path.isfile(filedir):
			print('[File] Opening database %s in append mode' % filedir)
			self.file = h5py.File(filedir, 'a', libver='latest')
			self.sipm_group = self.file['SiPMs Measurements']

		else:
			print('[File] Database does not exist. Creating...')
			self.file = h5py.File(filedir, 'w', libver='latest')
			self.sipm_group = self.file.create_group('SiPMs Measurements')

		# self.file.swmr_mode = True

	def add_options(self, options):
		if self.curr_meas:
			curr_meas.attrs.update(options)

	def add_attribute(self, key, value):
		if self.curr_meas:
			self.curr_meas.attrs[key] = value
		print('[File] Adding key \'%s\' with value \'%s\' to database' % (key, value))

	def create_dataset(self, dbName, n=1):
		self.dbName = dbName
		print('[File] Creating group with name %s' % dbName)
		self.curr_meas = self.sipm_group.create_group(dbName)
		self.curr_meas.attrs['Date'] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
		self.curr_meas.attrs['Author'] = 'Hector Hawley Herrera'

		self.IV_measurements = self.curr_meas.create_dataset('%s_IV' % dbName, (n, 3), maxshape=(None, 3))
		self.HT_measurements = self.curr_meas.create_dataset('%s_HT' % dbName, (1, 3), maxshape=(None, 3))

	def add_IV(self, meas, i):
		self.IV_measurements.resize((i+1,3))
		self.IV_measurements[i] = meas

	def add_HT(self, meas, i):
		self.HT_measurements.resize((i+1,3))
		self.HT_measurements[i] = meas

	def close(self):
		self.file.close()

	def delete_dataset(self):
		if self.curr_meas:
			del self.sipm_group[self.dbName]

# import numpy as np
# f = sipmFileManager('TestDB.hdf5')

# a = np.random.rand(2,3)
# print(a)

# f.createDataSet(2, 'test')

# print(f.IV_measurements[:])

# for i in range(0, 2):
# 	f.add_IV(a[i], i)


# print(f.IV_measurements[:])


# f.close()