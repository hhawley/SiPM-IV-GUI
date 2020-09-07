import serial
import time

# My own serial port manager that uses the progologix ver 6.X
# GPIB to USB converter and assumed that the
# Keithley 487 and a HP 34401A are connected
class SCPIPort(serial.Serial):
	def __init__(self, \
		port=None, baudrate=9600, bytesize=serial.EIGHTBITS, \
		parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, \
		timeout=None, xonxoff=False, rtscts=False, \
		write_timeout=None, dsrdtr=False, inter_byte_timeout=None):

		super().__init__(port, baudrate, bytesize, parity, stopbits,
			timeout, xonxoff, rtscts, write_timeout, dsrdtr,
			inter_byte_timeout)

		self.currentDevice = 'NONE'


	def FormatCMD(self, cmd):
		return (cmd + '\n').encode()

	def SCPIWrite(self, cmd):
		self.write(self.FormatCMD(cmd))

	# The Keithley 487 is old and has different standards...
	def Wait487CommandDone(self, timeout=5):
		srq = False
		startTime = time.time()
		timeoutCounter = 0.0

		# self.SCPIWrite('M16X')
		# self.SCPIWrite('++srq')
		# s = self.readline()

		# print('Starting the wait for cmd')
		if self.in_waiting > 0:
			self.reset_input_buffer()

		while not (srq or timeoutCounter > timeout): 
			self.SCPIWrite('++srq')
			srq = self.readline()
			
			srq = srq.decode('ASCII') == '1\r\n'
			# print(srq)

			if not srq:
				time.sleep(0.1)
				timeoutCounter = (time.time() - startTime) 

		return srq


	def WaitCMDDone(self):
		self.SCPIWrite('*OPC?')
		s = self.readline()

		status = (s.decode('ASCII') == '1\n')

		return status

	# This is a confirmation of command that does not block.
	# works only for the Keitheley.
	def WaitLongCommand(self, timeout=30):
		esr = False
		startTime = time.time()
		timeoutCounter = 0.0

		self.SCPIWrite('*CLS')
		self.SCPIWrite('*OPC')
		# self.flush()

		while not (esr or timeoutCounter > timeout): 
			self.SCPIWrite('*ESR?')
			esr = self.readline()
			esr = int(s.decode('ASCII')) & 1

			if not srq:
				time.sleep(0.1)
				timeoutCounter = (time.time() - startTime) 

		return esr or (timeoutCounter < timeout)

	# Sets the GPIB address (HP 34401A Addr = 1)
	def SetTo34401A(self):

		if self.currentDevice != '1':
			self.SCPIWrite('++addr 1')
			self.currentDevice = '1'
		# self.flush()

		# So THIS was the reason it was taking too long!
		#self.WaitCommandDone()

	# Sets the GPIB address (Keithley 487 Addr = 22)
	def SetToPicoammter(self):
		if self.currentDevice != '22':
			self.SCPIWrite('++addr 22')
			self.currentDevice = '22'
		# self.flush()

		# So THIS was the reason it was taking too long!
		# self.Wait487CommandDone()

	# TODO: not really needed in the near future
	def read_esr(self):
		self.SCPIWrite('*ESR?')

		ESR = self.readline()
		ESR = int(ESR.decode('ASCII'))

		return ESR