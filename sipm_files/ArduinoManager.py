import serial
import time
import datetime

# Arduino expects to receive commands with the next format:
#				{INDEX, R/W, VAL}
# where INDEX is the index of the value as states in the arduino code
# set to R if it meant to read the variable, this ignores VAL.
# set to W to write the value, and val being its new value

# a successful write will return an 'OK\r\n' and possibly other values
# depending on the command. See retrieveMeasurements for an example.

# a successful read will return the value.
#
#######################################
#
# The arduino currently has 4 registers:
# from most significant bit to lower:
# COMMAND_REGISTER
# XXXX XXXX XXXX RESET_ERROR[1] TOGGLE_STATE[1] SEND_HT[1] READ_HUMIDIY[1]
# READ_HUMIDIY[1] -> Starts a hum measurement
# SEND_HT[1] -> Send a temperature (RTD) and humidity measurement
# TOGGLE_STATE[1] -> Toggles between STANDBY and RUNNING
# RESET_ERROR[1] -> Resets error part of the status flag
#
# CURR_TEMP_REGISTER
# Saves the current temperature
# 
# DESI_TEMP_REGISTER
# Saves the desired temperature
#
# STATUS_FLAG
# XXXX STATUS[1] DAC_ERR[1] DHT_ERR[1] VT_ERR[1] RTD_ERR[8]  
# No error checking for the ina219 (wattmeter) available
# STATUS[1] -> Current status of the arduino: STANBY or RUNNING
# DAC_ERR[1] -> If true, dac has presented an error
# DHT_ERR[1] -> "", DHT22 "
# VT_ERR[1] -> "", the protocol to communicate to the arduino has  presented an error
# RTD_ERR[8] -> Error from the RTD
#
#######################################

class sipmArduino:
	def __init__(self, portName='COM4'):
		self.port = serial.Serial()
		self.port.port = portName
		self.port.baudrate = 115200
		self.port.timeout = 30

		self.temperature = 0.0
		self.humidity = 0.0
		self.timestamp = 0

		self.startTime = time.time()

	# Open the arduino port.
	def setup(self):
		self.port.open()

		if not self.port.is_open:
			raise Exception('Arduino port not open.')

	def format_cmd(self, cmd):
		return (cmd + '\n').encode()

	# Write command with all the trash included for easier
	# readability
	def m_write(self, cmd):
		self.port.write(self.format_cmd(cmd))

	# Same as m_write
	def m_read(self):
		return self.port.readline().decode('ASCII')

	# An exclusive read command to check if the write cmd
	# was received
	def verify_write(self):
		if not self.m_read() == 'OK\r\n':
			raise Exception('Failed to communicate with the Arduino.')

	# Intiialize a humidity measurement
	def initMeasurement(self):
		# Command to start a humidity measurement
		# COMMAND_REGISTER -> SEND_HT bit
		self.m_write('{0,W,1}')
		self.port.flush()

		if self.m_read() == 'OK\r\n':
			# https://stackoverflow.com/questions/13890935/does-pythons-time-time-return-the-local-or-utc-timestamp
			self.timestamp = time.time() - self.startTime
			 # self.timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
		else:
			raise Exception('Arduino did not complete the variable transfer.')

	def retrieveMeasurements(self):
		if self.timestamp == 0:
			raise Exception('No measurement taken before retrieving a measurement.')

		# 2 = 0b0010
		# Command to read a H/T measurement
		self.m_write('{0,W,2}')

		if self.m_read() == 'OK\r\n':
			values = self.m_read()
			if values != '\r\n':
				values = values.split(',', 2)

				self.humidity = float(values[0])
				self.temperature = float(values[1])

				return [self.timestamp, self.humidity, self.temperature]
			else:
				raise Exception('Arduino returned an empty measurement string.')

	def setTemperature(self, temperature):
		# Need to turn temperature to an equivalent
		# uint16_t as thats what the Arduino sees
		u_temp = int((temperature+10)*(65535/45))
		# Command to set the desired temperature
		self.m_write('{2,W,%d}' % u_temp)
		self.verify_write()

	def retrieveStatus(self):
		# Command to read the current STATUS flag
		# STATUS_FLAG
		self.m_write('{3,R,0}')
		out = self.m_read()

		if out != '\r\n':
			status = int(out)
			# Extract -> STATUS bit
			# 2048 = 0b0000 1000 0000 0000
			status = status & 2048

			return status > 0
		else:
			raise Exception('Arduino returned an empty string in retrieveStatus().')

	def startCooling(self):
		running = self.retrieveStatus()

		if not running:
			print("[Arduino] Starting cooling.")
			# COMMAND_REGISTER -> TOGGLE_STATE bit
			self.m_write('{0,W,4}')
			self.verify_write()

	def stopCooling(self):
		running = self.retrieveStatus()

		if running:
			print("[Arduino] stopped cooling.")
			self.m_write('{0,W,4}')
			self.verify_write()

	def close(self):
		if self.port.is_open:
			running = self.retrieveStatus()

			if not running:
				self.m_write('{0,W,4}')
				self.verify_write()

			# Close port to open resources
			self.port.close()

	def retrieveError(self):
		# Command to read the current STATUS flag
		self.m_write('{3,R,0}')

		error = self.m_read()

		if error != '\r\n':
			print('[Arduino] Arduino returned with an error = %s' % error)
			return error
		else:
			raise Exception('Arduino returned an empty string in retrieveError().')

	def resetError(self):
		# COMMAND_REGISTER -> RESET_ERROR bit
		# 8 = 0b1000
		# Command to reset the error
		self.m_write('{0,W,8}')
		self.verify_write()

		print('[Arduino] Reseted the arduino error flag.')

