import serial
import time

# My own serial port manager that uses the progologix ver 6.X
# GPIB to USB converter and assumed that the
# Keithley 487 and a HP 34401A are connected
class SCPI_port(serial.Serial):
	def __init__(self, \
		port=None, baudrate=9600, bytesize=serial.EIGHTBITS, \
		parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, \
		timeout=None, xonxoff=False, rtscts=False, \
		write_timeout=None, dsrdtr=False, inter_byte_timeout=None):

		super().__init__(port, baudrate, bytesize, parity, stopbits,
			timeout, xonxoff, rtscts, write_timeout, dsrdtr,
			inter_byte_timeout)


	def format_cmd(self, cmd):
		return (cmd + '\n').encode()

	def scpi_write(self, cmd):
		self.write(self.format_cmd(cmd))

	# The Keithley 487 is old and has different standards...
	def wait_cmd_done_487(self, timeout=5):
		srq = False
		startTime = time.time()
		timeoutCounter = 0.0

		# self.scpi_write('M16X')
		# self.scpi_write('++srq')
		# s = self.readline()

		# print('Starting the wait for cmd')
		if self.in_waiting > 0:
			self.reset_input_buffer()

		while not (srq or timeoutCounter > timeout): 
			self.scpi_write('++srq')
			srq = self.readline()
			
			srq = srq.decode('ASCII') == '1\r\n'
			# print(srq)

			if not srq:
				time.sleep(0.1)
				timeoutCounter = (time.time() - startTime) 

		return srq


	def wait_cmd_done(self):
		self.scpi_write('*OPC?')
		s = self.readline()

		status = (s.decode('ASCII') == '1\n')

		return status

	def wait_long_cmd(self, timeout=30):
		esr = False
		startTime = time.time()
		timeoutCounter = 0.0

		self.scpi_write('*CLS')
		self.scpi_write('*OPC')
		# self.flush()

		while not (esr or timeoutCounter > timeout): 
			self.scpi_write('*ESR?')
			esr = self.readline()
			esr = int(s.decode('ASCII')) & 1

			if not srq:
				time.sleep(0.1)
				timeoutCounter = (time.time() - startTime) 

		return esr or (timeoutCounter < timeout)

	# HP 34401A Addr
	def set_to_DMM(self):
		self.scpi_write('++addr 1')
		# self.flush()

		# So THIS was the reason it was taking too long!
		#self.wait_cmd_done()

	# Keithley 487
	def set_to_pico(self):
		self.scpi_write('++addr 22')
		# self.flush()

		# So THIS was the reason it was taking too long!
		# self.wait_cmd_done_487()

	# TODO: not really needed in the near future
	def read_esr(self):
		self.scpi_write('*ESR?')

		ESR = self.readline()
		ESR = int(ESR.decode('ASCII'))

		return ESR



# times = b'2\n'

# times = int(times.decode('ASCII'))

# print(times & 1)