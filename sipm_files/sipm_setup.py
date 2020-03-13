import serial
import time
import dependencies.redpitaya_scpi as scpi

from sipm_files.sipm_measurements import sipmMeasurements
from sipm_files.sipm_err import checkPicoAmmeterStatus, checkPicoammeterPS_status
from sipm_files.sipm_basic import SCPI_port

#For Windows:
portName = "COM3"
gpib_usb_controller = ""
rp_ip = '192.168.128.1' # pitaya IP
rp_s = ""

def setup_GPIB_controller(port):
	print('Performing GPIB controller setup...')
	port.scpi_write('++rst')
	time.sleep(5) # Should not be doing this... but no opc command
	# port.write(b'++opc?\n')

	port.scpi_write('++mode 1') # Sets in CONTROLLER mode
	port.scpi_write('++auto 1') # Read-After-Write
	port.scpi_write('++eos 2')  # Append LF to instrument commands

	s = ""
	while s != "":
		port.scpi_write('++ver') 
		s = port.readline()
		s = s.decode('ASCII')
		print(s.decode('ASCII'))

	print('Done with GPIB controller setup!')

# How the Keithley 487 commands work:
# A command is like the next:
# 	YZYZYZYZYZX
# where YZ is a command
# X is the end of list of commands, so the previous command
# implies several commands being sent and executed.
ranges = {1: '2nA', 2: '20nA', 3: '200nA', 4: '2uA', 5: '20uA', 6: '200uA', 7: '2mA'}
def setup_Picoammeter(port, zeroCheck=False):
	print('Performing 487 Picoammeter setup...')
	port.scpi_write('++addr 22')
	port.scpi_write('M16X')
	port.flush()
	
	port.wait_cmd_done_487()
	## C2 = Enable zero check and perform zero correction (must be done for each range)
	## G1 = ASCII readings without prefix
	## L2 = return to saved default conditions (I will assume the calibration is done....)
	## O0 = Place voltage source in standby (never too sure)
	## R1 = Select 2nA Range
	## T7 = One shot on External Trigger
	## W0X = No trigger delay
	## N1 = Buffer holds 1 value
	print('Clearing device')
	port.scpi_write('++clr')
	port.wait_cmd_done_487()

	print('Sending starting command')
	port.wait_cmd_done_487()

	port.scpi_write('K0W0G1O0R1T7X')
	port.flush()
	# Some time to wait for the last, then ask for status
	port.wait_cmd_done_487()

	# port.write(b'W0X\n')
	# U1 = Send machine error status word
	if zeroCheck:
		for i in range(1, 8):
			if checkPicoAmmeterStatus(port):
				range_str = 'R%dX' % i
				print("Zero checking for range ", ranges[i])
				port.scpi_write(range_str)
				port.scpi_write('C2X')
				# timeout is raised to 30 secs here as the zero correction can take a long time
				# depending on the range
				port.wait_cmd_done_487(timeout=60)
			else:
				raise Exception('Zero check failed at range %s' % ranges[i])

		if(checkPicoAmmeterStatus(port)):
			print("Picoammeter setup!")
			# Return to 2nA after all the zero checking
			port.scpi_write('R1X')
			port.wait_cmd_done_487()
			return True
		else:
			raise Exception('Picoammeter status failed after zero check.')
	else:
		if checkPicoAmmeterStatus(port):
			return True
		else:
			raise Exception('Picoammeter failed to verify.')

def setup_Picoammeter_PS(port):
	print('Performing 487 Picoammeter Power Supply setup...')
	port.set_to_pico()

	# Set Voltage to 0 volts, range 50V, 25uA max current
	port.scpi_write('V0,0,0X')
	# Turn on source
	# port.scpi_write('O1X')

	port.wait_cmd_done_487()

	if checkPicoammeterPS_status(port):
		print('Done with power supply setup!')
		return True
	else:
		raise Exception("Power supply status failed.")

def setup_DMM(port):
	print('Performing 34401A multimeter setup...')
	port.set_to_DMM()

	port.scpi_write('*CLR')
	# Set DMM in a known state
	port.scpi_write('*RST')

	port.wait_cmd_done()

	port.scpi_write('*IDN?')
	txt = port.readline()

	print(txt)

	# No beeping PLEASE
	# Stills fails, but minimizes beeping ;-;
	port.scpi_write('SYSTem:BEEPer:STATe OFF')
	# Integration time 1 PLC
	port.scpi_write('SENSE:VOLT:DC:NPLC 1')
	# Set the range
	port.scpi_write('SENSE:VOLT:DC:RANG 10')
	port.scpi_write('TRIG:SOUR EXT')
	# No trigger delay
	port.scpi_write('TRIG:DEL 0')
	# Input impedance auto
	port.flush()
	port.wait_cmd_done()
	# port.write(b'INP:IMP:AUTO ON\n')
	print('Done with multimeter setup!')


def setupRedPitaya():
	print('Performing red pitaya setup...')
	rp_s = scpi.scpi(rp_ip)

	rp_s.rst()

	# Pin 7_P is connected to the triggers.
	rp_s.tx_txt('DIG:PIN:DIR OUT,DIO7_P')

	# We set it high as the trigger is executed at the falling time.
	rp_s.tx_txt('DIG:PIN DIO7_P,1')

	print('Done with red pitaya setup!')
	return rp_s


def setup(zeroCheck=False):
	rp_s = setupRedPitaya()
	gpib_usb_controller = SCPI_port(portName, 19200, timeout=15)

	measure_Manager = sipmMeasurements(gpib_usb_controller, rp_s)

	if gpib_usb_controller.is_open:
		setup_GPIB_controller(gpib_usb_controller)
		setup_DMM(gpib_usb_controller)

		if setup_Picoammeter(gpib_usb_controller, zeroCheck):

			setup_Picoammeter_PS(gpib_usb_controller)

			measure_Manager.prepMeasurements()
			measure_Manager.triggerInstruments()
			curr =	measure_Manager.retrievePicoMeasurement()
			volt =	measure_Manager.retrieveVoltageMeasurement()

			print(volt)
			print(curr)


		return gpib_usb_controller, rp_s

	else:
		raise Exception("Serial port failed to open.")

def close(port, rp_s):
	if port and rp_s:
		# Lets make 100% sure the output voltage is off
		port.scpi_write('O0X')
		port.flush()
		port.wait_cmd_done_487()
		port.close()
		rp_s.close()


if __name__ == '__main__':
    setup()
    # close(gpib_usb_controller)