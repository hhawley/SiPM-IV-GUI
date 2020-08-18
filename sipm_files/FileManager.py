import h5py
import time
import os
import datetime

class sipmFileManager:

	def __init__(self, filedir):
		self.filedir = filedir
		self.database_name = ''

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

	def rename_and_save(self, name):
		no_problem = False
		i = 0

		while not no_problem:
			
			# zfill adds zeroes to the left. Ex. 1 -> 01
			new_name = '%s_%s' % (name, str(i).zfill(2))

			try:
				self.curr_meas = self.sipm_group.create_group(new_name)
				self.database_name = new_name
				print('[File] File renamed to %s' % new_name)

				no_problem = True
			except ValueError as err:
				no_problem = False
				i += 1


	def create_dataset(self, dbName, n=1):
		self.database_name = dbName
		print('[File] Creating group with name %s' % dbName)

		# Trying to create file with this name.
		try:
			self.curr_meas = self.sipm_group.create_group(dbName)
		except ValueError as err:
			# If fails to create file with this name rename it by adding _XX until it succeds
			# maybe not the most efficient way to do it.
			print('[File] File with that name already exists. Renaming.')
			self.rename_and_save(dbName)
			
		self.curr_meas.attrs['Date'] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
		self.curr_meas.attrs['Author'] = 'Hector Hawley Herrera'

		self.IV_measurements = self.curr_meas.create_dataset('%s_IV' % self.database_name, (n, 3), maxshape=(None, 3))
		self.HT_measurements = self.curr_meas.create_dataset('%s_HT' % self.database_name, (1, 3), maxshape=(None, 3))

	def add_IV(self, meas, i):
		self.IV_measurements.resize((i+1,3))
		self.IV_measurements[i] = meas

	def add_HT(self, meas, i):
		self.HT_measurements.resize((i+1,3))
		self.HT_measurements[i] = meas

	def reset(self):
		print('[File] Resetting database.')
		create_dataset(self.database_name)

	def close(self):
		self.file.close()

	def delete_dataset(self):
		if self.curr_meas:
			del self.sipm_group[self.dbName]
