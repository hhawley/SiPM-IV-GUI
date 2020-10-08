import h5py
import time
import os
import datetime
from enum import Enum

# Processes enum
class Process(Enum):
	NONE = 1
	ARDUINO = 2
	GRAPHER = 3
	IV = 4
	SECRETARY = 5
	ALL = 6

class sipmFileManager:

	def __init__(self, filedir, numSiPMs = 1):
		self.filedir = filedir
		self.database_name = ''
		self.HTsize = 0
		self.IVsize = 0
		self.TotalPreCooling = 0
		self.TotalPostCooling = 0
		self.NumSiPMs = numSiPMs

		if os.path.isfile(filedir):
			print(f'[File] Opening database {filedir} in append mode.')

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
		
			print(f'[File] Adding key \'{key}\' with value \'{value}\' to database.')
		else:
			print(f'[File] Failed to add key \'{key}\' with value \'{value}\' to database.')

	def rename_and_save(self, name):
		no_problem = False
		i = 0

		while not no_problem:
			
			# zfill adds zeroes to the left. Ex. 1 -> 01
			new_name = f'{name}_{str(i).zfill(2)}'

			try:
				self.curr_meas = self.sipm_group.create_group(new_name)
				self.database_name = new_name
				print(f'[File] File renamed to {new_name}.')

				no_problem = True
			except ValueError as err:
				no_problem = False
				i += 1


	def create_dataset(self, dbName, n=1):
		self.database_name = dbName

		print(f'[File] Creating group with name {dbName}.')

		# Trying to create file with this name.
		try:
			self.curr_meas = self.sipm_group.create_group(dbName)
		except ValueError as err:
			# If fails to create file with this name rename it by adding _XX until it succeds
			# maybe not the most efficient way to do it.
			print('[File] File with that name already exists. Renaming.')
			self.rename_and_save(dbName)
			
		self.curr_meas.attrs['Date'] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
		self.curr_meas.attrs['Author'] = 'Queens SiPM Group'

		# Create an array of IV measurements 1 item for each SiPM
		self.IVsize = [n for i in range(1, self.NumSiPMs + 1)]
		self.IV_measurements = [self.curr_meas.create_dataset(f'IV_{i}', (n, 3), maxshape=(None, 3)) \
			for i in range(1, self.NumSiPMs + 1)]

		# All the SiPMs share the HT measurements
		self.HT_measurements = self.curr_meas.create_dataset('HT', (1, 3), maxshape=(None, 3))

	def add_IV(self, meas, numSiPM=0):
		self.IVsize[numSiPM] += 1
		newSize = self.IVsize[numSiPM]

		self.IV_measurements[numSiPM].resize((newSize, 3))
		self.IV_measurements[numSiPM][ newSize - 1 ] = meas

	def add_HT(self, meas):
		self.HTsize += 1
		self.HT_measurements.resize((self.HTsize,3))
		self.HT_measurements[self.HTsize - 1] = meas

	def reset(self):
		print('[File] Resetting database.')
		self.create_dataset(self.database_name)

	def close(self):
		self.file.close()

	def delete_dataset(self):
		if self.curr_meas and self.database_name is not None:
			del self.sipm_group[self.database_name]
