import serial
import time

# Keithley 487 has an internal HV power supply that ranges from
# 0V to 500V. This class helps manage the voltage supply.

class VoltageSupplyHelper:

	def __init__(self, errorhelper):
		self.range = False # 0 = 50V, 1 = 500V
		self.currentValue = 0
		self.maxVoltage = 70
		self.minVoltage = -0.5
		self.isON = False
		self.currentLimit = False # False = 25uA, True = 25mA

		self.port = errorhelper.port
		self.errorhelper = errorhelper


	def SetVoltageSupplyState(self, state):
		self.port.SetToPicoammter()
		self.isON = state

		if self.isON:
			print('[Electrometer] Voltage supply is ON.')
			self.port.SCPIWrite('O1X')
		else:
			print('[Electrometer] Voltage supply is OFF.')
			self.port.SCPIWrite('O0X')

		self.port.Wait487CommandDone()

	def SetVoltageRange(self, volt):
		self.port.SetToPicoammter()

		if volt > 50.5 and not self.range:
			self.range = True
			self.port.SCPIWrite('V,1X')
		elif volt <= 50.5 and self.range:
			self.range = False
			self.port.SCPIWrite('V,0X')

	def SetCurrentLimit(self, state):
		self.port.SetToPicoammter()
		self.currentLimit = state

		if self.currentLimit:
			self.port.SCPIWrite('V,,1X')
		else:
			self.port.SCPIWrite('V,,0X')

		self.port.Wait487CommandDone()

	# Sets the voltage and verifies it
	def SetVoltage(self, volt):
		self.port.SetToPicoammter()

		if volt > self.maxVoltage:
			err = f'Tried to set voltage higher than the maximum \
			 allowed voltage {self.maxVoltage}'
			print(f'[Electrometer] {err}.')
			raise Exception(f'{err}')

		if volt < self.minVoltage:
			err = f'[Electrometer] Tried to set voltage lower than the minimum \
			allowed voltage {self.minVoltage}'
			print(f'[Electrometer] {err}.')
			raise Exception(f'{err}')

		# Change voltimeter range if necessary
		self.SetVoltageRange(volt)

		volt_s = ''
		if volt == 0:
			volt_s = 'V0X'
		else:
			# Rounds to 2 decimal places. 
			# 487 can reach 3 digits of precision on the 50V range
			# but we are not interested in going that down in precision.
			volt_s = ('V%.2fX' % volt)

		self.port.SCPIWrite(volt_s)
		self.port.Wait487CommandDone()

		# Returns current voltage output
		self.port.SCPIWrite('U8X')
		volt_received = self.port.readline()

		if volt_received == b'\r\n':
			err = f'Failed retrieving the current voltage value'
			print(f'[Electrometer] {err}.')
			raise Exception(f'{err}')

		# String comes as VS=[VALUE]V\r\n

		volt_received = volt_received[3:-3]
		volt_received = float(volt_received)

		# Check if value is within 1%
		if self.range:
			error = 500*(1/100)
		else:
			error =  50*(1/100)

		# We verify the value is within the error
		v_minus = volt - error
		v_plus = volt + error
		if v_minus < volt_received and volt_received < v_plus:
			self.currentValue = volt_received
			print(f'[Electrometer] Current output voltage is {self.currentValue}')
		else:
			err = f'Value read is not currently the set value'
			print(f'[Electrometer] {err}.')
			raise Exception(f'{err}')