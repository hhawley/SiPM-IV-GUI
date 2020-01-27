import serial
import time

class sipmVoltage:
	def __init__(self, port):
		self.range = False # 0 = 50V, 1 = 500V
		self.currentValue = 0
		self.maxVoltage = 70
		self.minVoltage = -0.5
		self.isON = False
		self.currentLimit = False # False = 25uA, True = 25mA

		self.port = port


	def multimeterState(self, isON):
		self.port.set_to_pico()
		self.isON = isON

		if isON:
			self.port.scpi_write('O1X')
		else:
			self.port.scpi_write('O0X')

		self.port.flush()
		self.port.wait_cmd_done()

	def setCurrentLimitHigh(self, wantHigh):
		self.port.set_to_pico()
		self.currentLimit = wantHigh

		if wantHigh:
			self.port.scpi_write('V,,1X')
		else:
			self.port.scpi_write('V,,0X')

		self.port.flush()
		self.port.wait_cmd_done()

	# Sets the voltage and verifies it
	def setVoltage(self, volt):
		self.port.set_to_pico()

		if volt > self.maxVoltage:
			print('Tried to set voltage higher than the maximum allowed voltage (%.2f).' % self.maxVoltage)
			return False

		if volt < self.minVoltage:
			print('Tried to set voltage lower than the minimum allowed voltage (%.2f)' % self.minVoltage)
			return False

		# Change voltimeter range if necessary
		if volt > 50.5 and not self.range:
			self.range = True
			self.port.scpi_write('V,1X')
		elif volt <= 50.5 and self.range:
			self.range = False
			self.port.scpi_write('V,0X')

		volt_s = ''
		if volt == 0:
			volt_s = 'V0X'
		else:
			volt_s = 'V%.2fX' % volt

		print('Current output voltage is %s' % volt_s)

		self.port.scpi_write(volt_s)
		self.port.wait_cmd_done()

		# Returns current voltage output
		self.port.scpi_write('U8X')
		volt_received = self.port.readline()
		

		if volt_received == b'':
			raise Exception('Failed retrieving the current voltage value.')

		# String comes as VS=[VALUE]V\r\n

		volt_received = volt_received[3:-3]
		volt_received = float(volt_received)

		if self.range:
			error = 500*5/100
		else:
			error =  50*5/100

		# We verify the value is within the error
		v_minus = volt - error
		v_plus = volt + error
		if v_minus < volt_received and volt_received < v_plus:
			self.currentValue = volt
			return True
		else:
			raise Exception('Value read is not currently the set value.')



	# st = 'lets test thisV'


	# print(st[3:-1])
testF = 0

print('Test %.2f' % testF)