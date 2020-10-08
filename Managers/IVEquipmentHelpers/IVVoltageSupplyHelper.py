import serial
import time

# Keithley 487 has an internal HV power supply that ranges from
# 0V to 500V. This class helps manage the voltage supply.

class VoltageSupplyHelper:

	def __init__(self, errorhelper):
		self.MAX_VOLTAGE = 70
		self.MIN_VOLTAGE = -0.3
		
		
		self.range = False # 0 = 50V, 1 = 500V
		self.currentValue = 0
		self.isON = False
		self.currentLimit = False # False = 25uA, True = 25mA

		self.port = errorhelper.port
		self.errorhelper = errorhelper


	def SetVoltageSupplyState(self, state):
		self.port.SetToPicoammter()
		self.isON = state

		if self.isON:
			print('[Electrometer] Voltage supply has been turned ON.')
			self.port.SCPIWrite('O1X')
		else:
			print('[Electrometer] Voltage supply has been turned OFF.')
			self.port.SCPIWrite('O0X')

		self.port.Wait487CommandDone()

	def SetCurrentLimit(self, state):
		self.port.SetToPicoammter()
		self.currentLimit = state

		if self.currentLimit:
			self.port.SCPIWrite('V,,1X')
		else:
			self.port.SCPIWrite('V,,0X')

		self.port.Wait487CommandDone()

	def VerifyVoltage(self):
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
		v_minus = self.currentValue - error
		v_plus = self.currentValue + error
		if v_minus < volt_received and volt_received < v_plus:
			print(f'[Electrometer] Current output voltage is {self.currentValue}')
		else:
			err = f'Value read is not currently the set value'
			print(f'[Electrometer] {err}.')
			raise Exception(err)

	# Sets the voltage.
	# limit sets the current limit on the power supply, default us 25uA
	def SetVoltage(self, volt, limit=False):
		self.port.SetToPicoammter()

		if volt > self.MAX_VOLTAGE:
			err = f'Tried to set voltage higher than the maximum \
			 allowed voltage {self.MAX_VOLTAGE}'
			print(f'[Electrometer] {err}.')
			raise Exception(err)

		if volt < self.MIN_VOLTAGE:
			err = f'[Electrometer] Tried to set voltage lower than the minimum \
			allowed voltage {self.MIN_VOLTAGE}'
			print(f'[Electrometer] {err}.')
			raise Exception(err)

		# Change voltimeter range if necessary
		# self.SetVoltageRange(volt)

		currentRange = ''
		if limit:
			currentRange = '1'
		else:
			currentRange = '0'

		self.currentValue = volt

		volt_s = ''
		if volt == 0:
			volt_s = 'V0,0,0X'
		elif volt <= 50.0:
			# Rounds to 2 decimal places. 
			# 487 can reach 3 digits of precision on the 50V range
			# but we are not interested in going that down in precision.
			volt_s = ('V%.2f,0,%sX' % (volt, currentRange))
		elif volt > 50.0:
			volt_s = ('V%.2f,1,%sX' % (volt, currentRange))

		self.port.SCPIWrite(volt_s)
		self.port.Wait487CommandDone()

		