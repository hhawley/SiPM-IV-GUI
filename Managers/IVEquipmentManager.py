import serial
import time
import dependencies.redpitaya_scpi as scpi

from Managers.IVEquipmentHelpers.SCPIPort import SCPIPort
from Managers.IVEquipmentHelpers.IVSetupHelper import SetupHelper
from Managers.IVEquipmentHelpers.IVVoltageSupplyHelper import VoltageSupplyHelper
from Managers.IVEquipmentHelpers.IVErrorHelper import ErrorHelper
# Wrapper of the available commands to the I-V Equipment.
# No experiment running logic is found here.

class IVEquipmentManager:
	def __init__(self, config):

		self.port = SCPIPort(port=config['Port'], baudrate=19200, timeout=15)
		self.rpport = scpi.scpi(config['PitayaIP'])

		if not self.port.is_open:
			raise Exception('SCPI port not open.')

		if self.port.in_waiting:
			self.port.reset_input_buffer()

		if self.port.out_waiting:
			self.port.reset_output_buffer()

		# 0 = lowest range
		self.currentPicoRange = 0

		# Max is 8 but the 2mA range is not calibrated, dont use
		self.maxPicorange = 7
		self.startTime = time.time()
		self.measTime = time.time()

		self.errorhelper = ErrorHelper(self.port, self.rpport)
		self.setuphelper = SetupHelper(self.errorhelper)
		self.voltagehelper = VoltageSupplyHelper(self.errorhelper)

		self.ranges = {1: '2nA', 2: '20nA', 3: '200nA', 4: '2uA', 5: '20uA', 6: '200uA', 7: '2mA'}

		

	# Raises the range in the picoammeter by 1 order of magnitude
	def RaisePicoammeterRange(self):
		self.port.SetToPicoammter()

		if self.currentPicoRange >= self.maxPicorange:
			self.currentPicoRange = self.maxPicorange
		else:
			self.currentPicoRange = self.currentPicoRange + 1

		print('[Electrometer] Increasing range on the picoammeter.')
		print(f'[Electrometer] Current range is {self.ranges[self.currentPicoRange + 1]}')

		cmd = f'R{(self.currentPicoRange + 1)}X'

		self.port.SCPIWrite(cmd)
		self.port.Wait487CommandDone()

	# Lowers the range in the picoammeter by 1 order of magnitude
	def LowerPicoammeterRange(self):
		self.port.SetToPicoammter()

		if self.currentPicoRange <= 0:
			self.currentPicoRange = 0
		else:
			self.currentPicoRange = self.currentPicoRange - 1

		print('[Electrometer] Decreasing range on the picoammter.')
		print(f'[Electrometer] Current range is {self.ranges[self.currentPicoRange + 1]}')

		cmd = f'R{(self.currentPicoRange + 1)}X'

		self.port.SCPIWrite(cmd)
		self.port.Wait487CommandDone()

	def SetToLowestRange(self):
		self.port.SetToPicoammter()

		self.currentPicoRange = 0

		print(f'[Electrometer] Current range is {self.ranges[self.currentPicoRange + 1]}')

		cmd = f'R{(self.currentPicoRange + 1)}X'

		self.port.SCPIWrite(cmd)
		self.port.Wait487CommandDone()

	def PrepVoltageMeasurement(self):
		self.port.SetTo34401A()
		self.port.SCPIWrite('++auto 0')
		self.port.SCPIWrite('INIT')
		self.port.SCPIWrite('++auto 1')
		# self.port.WaitCMDDone()

	def PrepCurrentMeasurement(self):
		self.port.SetToPicoammter()
		self.port.SCPIWrite('N1X')
		self.port.Wait487CommandDone()

	def PrepMeasurements(self):
		# The order DOES matter
		# There is a time issue where the current measurement
		# is not ready even if it says it is. By putting it
		# first it actually works better
		self.PrepCurrentMeasurement()
		self.PrepVoltageMeasurement()


	# Triggers all the instruments by sending a pulse
	def TriggerInstruments(self):
		## Making sure its at HIGH
		self.measTime = time.time() - self.startTime
		self.rpport.tx_txt('DIG:PIN DIO7_P, 1')
		time.sleep(0.000001) # 1 us
		self.rpport.tx_txt('DIG:PIN DIO7_P, 0')
		time.sleep(0.000005) # 5 us Atleast 2 us required for all instruments
		self.rpport.tx_txt('DIG:PIN DIO7_P, 1')
		# Then wait 1 PLC + 0.01ms for the values to be ready
		time.sleep((1/60.0) + 0.01)

	# Read HP 34401A manual for the commands used.
	def RetrieveVoltageMeasurement(self):
		self.port.SetTo34401A()

		self.port.SCPIWrite('FETC?')

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
	def RetrievePicoMeasurement(self):
		self.port.SetToPicoammter()
		# B0 = Readings from A/D
		# B1 = Single data store reading
		self.port.SCPIWrite('B1X')

		value = self.port.readline()
		value = value.decode('ASCII')

		if value == '':
			raise Exception('Failed to retrieve the current measurement.')

		value_float = float(value)

		return value_float

	# Gets the current, and voltages
	# time is retrieved when TriggerInstruments is called
	def MakeFullMeasurement(self):
		curr = self.RetrievePicoMeasurement()
		volt = self.RetrieveVoltageMeasurement()

		return self.measTime, volt, curr

#######################################################################

	def Setup(self, zeroCheck=False):
		try:
			# See IVSetupHelper for more info
			# GPIB has to be the first one.
			self.setuphelper.SetupGPIBController()

			# The order of these do not matter only rule: picoammeter first
			# then power supply
			self.setuphelper.SetupPicoammeter(zeroCheck)
			self.setuphelper.SetupPicoammeterPowerSupply()

			self.setuphelper.SetupMultimeter()
			self.setuphelper.SetupRedPitaya()

			print('[Electrometer] Done with the setup!')
		except Exception as e:
			raise e

	# This measurement routine checks if the measurements has overflow
	# or underflow and changes the range.
	def MeasurementRoutine(self):

		time, volt, curr = 0.0, 0.0, 0.0

		try:
			while True:
				self.PrepMeasurements()
				self.TriggerInstruments()

				time, volt, curr = self.MakeFullMeasurement()

				if abs(curr) == 9.87e37:
					self.RaisePicoammeterRange()
				elif curr == 9.87e-37:
					self.LowerPicoammeterRange()
				else:
					break

			return time, volt, curr
		except Exception as e:
			raise e

	# This function will be used a lot so a small
	# function allows avoiding to write a bit too much.
	def SetVoltage(self, volt, limit=False):
		try:
			self.voltagehelper.SetVoltage(volt, limit)
		except Exception as e:
			raise e

	def VoltageOn(self):
		self.voltagehelper.SetVoltageSupplyState(True)

	def VoltageOff(self):
		self.voltagehelper.SetVoltageSupplyState(False)

	def CheckStatus(self):
		try:
			# Picoammeter check
			status, errorPICO = self.errorhelper.CheckPicoammeterStatus()
			if status:
				raise Exception(errorPICO)

			# Power Supply checking
			status, errorPS =  self.errorhelper.CheckPowerSupplyStatus()
			if status:
				raise Exception(f'{errorPICO} {errorPICO}.')

			status, errorDMM = self.errorhelper.CheckDMMStatus()
			if status:
				raise Exception(f'{errorPICO} {errorPICO}. {errorDMM}.')

			# Need DMM checking
		except Exception as e:
			raise e
		
	def Close(self):
		if self.port is not None:
			if self.port.is_open:
				self.port.close()

		if self.rpport is not None:
			self.rpport.close()