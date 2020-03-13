import serial
import time
import dependencies.redpitaya_scpi as scpi

class sipmMeasurements:
	def __init__(self, port, rpport):
		self.port = port
		# 0 = lowest range
		self.currentPicoRange = 0
		self.rpport = rpport
		# Max is 8 but the 2mA range is not calibrated, dont use
		self.maxPicorange = 7
		self.startTime = time.time()
		self.measTime = time.time()


	def raisePicoammeterRange(self):
		self.port.set_to_pico()

		if self.currentPicoRange >= self.maxPicorange:
			self.currentPicoRange = self.maxPicorange
		else:
			self.currentPicoRange = self.currentPicoRange + 1

		print('Increasing range on the picoammeter.')

		cmd = 'R%dX' % (self.currentPicoRange + 1)

		self.port.scpi_write(cmd)
		self.port.wait_cmd_done_487()

	def lowerPicoammeterRange(self):
		self.port.set_to_pico()

		if self.currentPicoRange <= 0:
			self.currentPicoRange = 0
		else:
			self.currentPicoRange = self.currentPicoRange - 1

		print('Decreasing range!')
		cmd = 'R%dX' % (self.currentPicoRange + 1)

		self.port.scpi_write(cmd)
		self.port.wait_cmd_done_487()

	def prepVoltageMeasurement(self):
		self.port.set_to_DMM()
		self.port.scpi_write('INIT')
		self.port.wait_cmd_done()

		# TODO: check status
		# port.readline()

	def prepCurrentMeasurement(self):
		self.port.set_to_pico()
		self.port.scpi_write('N1X')
		self.port.wait_cmd_done_487()

		# TODO: check status
		# port.readline()

	def prepMeasurements(self):
		# The order DOES matter
		# There is a time issue where the current measurement
		# is not ready even if it says it is. By putting it
		# first it actually works better
		self.prepCurrentMeasurement()
		self.prepVoltageMeasurement()




	# Triggers all the instruments by sending a pulse
	def triggerInstruments(self):
		## Making sure its at HIGH
		self.measTime = time.time() - self.startTime
		self.rpport.tx_txt('DIG:PIN DIO7_P, 1')
		time.sleep(0.000001) # 1 us
		self.rpport.tx_txt('DIG:PIN DIO7_P, 0')
		time.sleep(0.000005) # 5 us Atleast 2 us required for all instruments
		self.rpport.tx_txt('DIG:PIN DIO7_P, 1')
		# Then wait 1 PLC + 0.01ms for tha values to be ready
		time.sleep((1/60.0) + 0.01)

	# Read HP 34401A manual for the commands used.
	def retrieveVoltageMeasurement(self):
		self.port.set_to_DMM()

		self.port.scpi_write('FETC?')

		val_word = self.port.readline()
		val_word = val_word.decode('ASCII')

		if val_word == '':
			raise Exception('Failed to retrieve the voltage measurement.')

		val = float(val_word)

		return val

	# Retrieves the current measurement
	# If overflown it returns a string
	# If measurement failed it returns False
	# Otherwise it returns a number
	def retrievePicoMeasurement(self):
		self.port.set_to_pico()
		# B0 = Readings from A/D
		# B1 = Single data store reading
		self.port.scpi_write('B1X')

		value = self.port.readline()
		value = value.decode('ASCII')

		if value == '':
			raise Exception('Failed to retrieve the current measurement.')

		value_float = float(value)

		if abs(value_float) == 9.87e37:
			print("Overflow value! Check System?")
			return "Overflow"
		elif value_float == 9.87e-37:
			print("Underflow value! Check System, please?")
			return "Underflow"

		return value_float

	# Gets the current, and voltages
	# time is retrieved when triggerInstruments is called
	def makeFullMeasurement(self):
		curr = self.retrievePicoMeasurement()
		volt = self.retrieveVoltageMeasurement()

		return self.measTime, volt, curr

	# This measurement routine checks
	# if the measurements has overflow/underflow
	# and changes the range
	def measurementRoutine(self):
		time, volt, curr = 0.0, 0.0, 'Overflow'

		while curr == 'Overflow' or curr == 'Underflow':
			self.prepMeasurements()
			self.triggerInstruments()

			time, volt, curr = self.makeFullMeasurement()

			if isinstance(curr, str):
				if curr == 'Overflow':
					self.raisePicoammeterRange()
				elif curr == 'Underflow':
					self.lowerPicoammeterRange()

		return time, volt, curr