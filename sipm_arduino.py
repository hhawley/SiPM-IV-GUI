import serial
import time
import datetime

class sipmArduino:
	def __init__(self, portName='COM4'):
		self.port = serial.Serial()
		self.port.port = portName
		self.port.baudrate = 9600
		self.port.timeout = 15

		self.temperature = 0.0
		self.humidity = 0.0
		self.timestamp = 0

	def setup(self):
		self.port.open()

		if not self.port.is_open:
			raise Exception('Arduino port not open.')

	def format_cmd(self, cmd):
		return (cmd + '\n').encode()

	def initMeasurement(self):
		self.port.write(self.format_cmd('{0,W,1}'))
		self.port.flush()


		if self.port.readline().decode('ASCII') == 'OK\r\n':
			# https://stackoverflow.com/questions/13890935/does-pythons-time-time-return-the-local-or-utc-timestamp
			self.timestamp = time.time()
			 # self.timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
			return True
		else:
			raise Exception('Arduino did not complete the variable transfer.')

	def retrieveMeasurements(self):
		if self.timestamp == 0:
			raise Exception('No measurement taken before retrieving a measurement.')

		self.port.write(self.format_cmd('{1,W,1}'))
		

		if self.port.readline().decode('ASCII') == 'OK\r\n':
			values = self.port.readline().decode('ASCII')
			if values != '\r\n':
				values = values.split(',', 2)

				self.humidity = float(values[0])
				self.temperature = float(values[1])

				return [self.timestamp, self.humidity, self.temperature]
			else:
				raise Exception('Arduino returned an empty measurement string.')

	def close(self):
		self.port.close()