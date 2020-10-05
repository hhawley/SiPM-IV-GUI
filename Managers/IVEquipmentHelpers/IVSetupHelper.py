import serial
import time
import dependencies.redpitaya_scpi as scpi


# Helps managing all the setup for all the IV-Equipment
# Does not manage the ports or anything else.

class SetupHelper():
	def __init__(self, errorhelper):
		self.port = errorhelper.port
		self.rpport = errorhelper.rpport
		self.errorhelper = errorhelper

		self.ranges = {1: '2nA', 2: '20nA', 3: '200nA', 4: '2uA', 5: '20uA', 6: '200uA', 7: '2mA'}

	# GPIB controller is a device that translated the GPIB to USB.
	# It is currently connected to the picoammeter and DMM
	def SetupGPIBController(self):
		print('[Electrometer] Performing GPIB controller setup...')
		self.port.SCPIWrite('++rst')
		# Should not be doing this... but no opc command
		time.sleep(5) 
		# port.write(b'++opc?\n')

		self.port.SCPIWrite('++mode 1') # Sets in CONTROLLER mode
		self.port.SCPIWrite('++auto 1') # Read-After-Write
		self.port.SCPIWrite('++eos 2')  # Append LF to instrument commands

		s = ""
		while s != "":
			self.port.SCPIWrite('++ver') 
			s = self.port.readline()
			s = s.decode('ASCII')
			print(f'[Electrometer] GPIB ver = { s.decode("ASCII") }.')

		print('[Electrometer] Done with GPIB controller setup!')

	# How the Keithley 487 commands work:
	# A command is like the next:
	# 	YZYZYZYZYZX
	# where YZ is a command
	# X is the end of list of commands, so the previous command
	# implies several commands being sent and executed.
	
	# Raises an exception if failed.
	def SetupPicoammeter(self, zeroCheck=False):
		print('[Electrometer] Performing 487 Picoammeter setup...')
		self.port.SetToPicoammter()

		self.port.SCPIWrite('M16X')
		self.port.Wait487CommandDone()

		print('[Electrometer] Clearing device.')
		self.port.SCPIWrite('++clr')
		self.port.Wait487CommandDone()

		print('[Electrometer] Sending init config command.')
		## C2 = Enable zero check and perform zero correction (must be done for
		## 		each range)
		## G1 = ASCII readings without prefix
		## L2 = return to saved default conditions (I will assume the 
		##		calibration is done....)
		## O0 = Place voltage source in standby (never too sure)
		## R1 = Select 2nA Range
		## T7 = One shot on External Trigger
		## W0 = No trigger delay
		## N1 = Buffer holds 1 value
		self.port.SCPIWrite('K0W0G1O0R1T7X')
		self.port.flush()
		# Some time to wait for the last, then ask for status
		self.port.Wait487CommandDone()

		# self.port.write(b'W0X\n')
		# U1 = Send machine error status word
		# If zerocheck is true run a zero check test
		# for each range.
		if zeroCheck:
			for i in range(1, 8):

				status, error = self.errorhelper.CheckPicoammeterStatus()

				if status:
					range_str = f'R{i}X'
					print(f"[Electrometer] Zero checking for range {self.ranges[i]}")
					self.port.SCPIWrite(range_str)
					self.port.SCPIWrite('C2X')
					# timeout is raised to 60 secs here as the zero correction can take a long time
					# depending on the range
					self.port.Wait487CommandDone(timeout=60)
				else:
					raise Exception(f'{error}. Zero check failed at range {self.ranges[i]}')

			status, error = self.errorhelper.CheckPicoammeterStatus()
			if status:
				print("[Electrometer] Picoammeter setup!")
				# Return to 2nA after all the zero checking
				self.port.SCPIWrite('C0R1X')
				self.port.Wait487CommandDone()
			else:
				raise Exception(f'{error}. Picoammeter status failed after all zero checks.')
		else:
			status, error = self.errorhelper.CheckPicoammeterStatus()
			if not status:
				raise Exception(f'{error}. Failed at verify setup status')

	def SetupPicoammeterPowerSupply(self):
		print('[Electrometer] Performing 487 Picoammeter Power Supply setup...')
		self.port.SetToPicoammter()

		# Set Voltage to 0 volts, range 50V, 25uA max current
		self.port.SCPIWrite('V0,0,0X')
		# Turn on source
		# self.port.SCPIWrite('O1X')

		self.port.Wait487CommandDone()

		status, error = self.errorhelper.CheckPowerSupplyStatus()
		if status:
			print('[Electrometer] Done with power supply setup!')
			return True
		else:
			raise Exception(f'Power supply status failed with error {error}.')

	def SetupMultimeter(self):
		print('[Electrometer] Performing 34401A multimeter setup...')
		self.port.SetTo34401A()

		print('[Electrometer] Clearing and reseting DMM.')
		# Set the GPIB controller to only talk for some commands.
		self.port.SCPIWrite('++auto 0')
		self.port.SCPIWrite('++clr')
		# Set DMM in a known state
		self.port.SCPIWrite('++rst')

		# No beeping PLEASE
		# Stills fails, but minimizes beeping ;-;
		self.port.SCPIWrite('SYST:BEEP:STAT OFF')
		# Integration time 1 PLC
		self.port.SCPIWrite('SENSE:VOLT:DC:NPLC 1')
		# Set the range
		self.port.SCPIWrite('SENSE:VOLT:DC:RANG 10')
		self.port.SCPIWrite('TRIG:SOUR EXT')
		# No trigger delay
		self.port.SCPIWrite('TRIG:DEL 0')
		# Input impedance auto
		# self.port.write(b'INP:IMP:AUTO ON\n')

		# Wait for the commands to write, and then wait until they are
		# executed.
		self.port.flush()

		# Turn on by default
		self.port.SCPIWrite('++auto 1')
		self.port.WaitCMDDone()
		status, error = self.errorhelper.CheckDMMStatus()
		if status:
			print('[Electrometer] Done with multimeter setup!')
		else:
			raise Exception(f'Multimeter status failed with error: {error}.')


	def SetupRedPitaya(self):
		print('[Electrometer] Performing red pitaya setup...')
		#self.rpport = scpi.scpi(rp_ip)

		self.rpport.cls()
		self.rpport.rst()

		# Pin 7_P is connected to the triggers.
		self.rpport.tx_txt('DIG:PIN:DIR OUT,DIO7_P')

		# We set it high as the trigger is executed at the falling time.
		self.rpport.tx_txt('DIG:PIN DIO7_P,1')

		print('[Electrometer] Done with red pitaya setup!')


	# def setup(self, zeroCheck=False):
	# 	rp_s = setupRedPitaya()
	# 	gpib_usb_controller = SCPI_port(portName, 19200, timeout=15)

	# 	measure_Manager = sipmMeasurements(gpib_usb_controller, rp_s)

	# 	if gpib_usb_controller.is_open:
	# 		setup_GPIB_controller(gpib_usb_controller)
	# 		setup_DMM(gpib_usb_controller)

	# 		if setup_Picoammeter(gpib_usb_controller, zeroCheck):

	# 			setup_Picoammeter_PS(gpib_usb_controller)

	# 			measure_Manager.prepMeasurements()
	# 			measure_Manager.triggerInstruments()
	# 			curr =	measure_Manager.retrievePicoMeasurement()
	# 			volt =	measure_Manager.retrieveVoltageMeasurement()

	# 			print(volt)
	# 			print(curr)


	# 		return gpib_usb_controller, rp_s

	# 	else:
	# 		raise Exception("Serial port failed to open.")

	# def close(self):
	# 	if port and rp_s:
	# 		# Lets make 100% sure the output voltage is off
	# 		port.SCPIWrite('O0X')
	# 		port.flush()
	# 		port.Wait487CommandDone()
	# 		port.close()
	# 		rp_s.close()


# if __name__ == '__main__':
#     setup()
    # close(gpib_usb_controller)