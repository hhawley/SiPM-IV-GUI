import serial

#https://stackoverflow.com/questions/39644638/how-to-take-the-nth-digit-of-a-number-in-python
def get_digit(number, n):
    return number // 10**n % 10

def translatePicoammeterStatus(err):
	if(isinstance(err, str)):
		raise Exception("Error is a string: " + err + " if empty check if the system is behaving as normal.")

	err_i = int(err)

	if(err_i == 0):
		print("No error in the picoammeter!")
		return True

	idcc_err = 			get_digit(err_i, 12) == 1
	idcco_err = 		get_digit(err_i, 11) == 1
	no_rem_err = 		get_digit(err_i, 10) == 1
	self_test_err = 	get_digit(err_i, 9)  == 1
	trigg_overrun_err = get_digit(err_i, 8)  == 1
	conflict_err = 		get_digit(err_i, 7)  == 1
	call_lock_err = 	get_digit(err_i, 6)  == 1
	zero_check_err = 	get_digit(err_i, 5)  == 1
	cal_err = 			get_digit(err_i, 4)  == 1
	eprom_def_err = 	get_digit(err_i, 3)  == 1
	eprom_const_err = 	get_digit(err_i, 2)  == 1
	v_source_conf_err = get_digit(err_i, 1)  == 1
	vsource_err = 		get_digit(err_i, 0)  == 1

	list_errs = []
	print("Errors found: (the next error warnings are taken from the manual)")
	if(idcco_err):
		print('Set when an illegal device-dependent command (IDIYJ, such as ElX is received (\'E\'is illegal).')
		list_errs.append(13)

	if(idcco_err):
		print('Set when an illegal device-dependent cormnan d option @DDCO) such as TlOX is received (“IO” is iuegal).')
		list_errs.append(12)

	if(no_rem_err):
		print('Set when a progr amming command is received when instrument is in the Lo-cal state')
		list_errs.append(11)

	if(self_test_err):
		print("Set when a self-test failme (RAM and/or ROM) occurs")
		list_errs.append(10)

	if(trigg_overrun_err):
		print('Set when the instnunent receives a trigger while it is still processing a reading from a previous tripper.')
		list_errs.append(9)

	if(conflict_err):
		print('Set when trying to send a calibration value with the instrument on a measurement range that is too small to accommodate the value')
		list_errs.append(8)

	if(call_lock_err):
		print('Set when calibrating the instrument with the calibration switch in the locked(disabled) position.')
		list_errs.append(7)

	if(zero_check_err):
		print('Set when trying to calibrate the instrument with zero check enabled.')
		list_errs.append(6)

	if(cal_err):
		print('Set when calibration results in a cal constant value that is not within allowable limits. Repeated failure may indicate that the Model 486/487 is defective.')
		list_errs.append(5)

	if(eprom_def_err):
		print('Set when power-up checksum test on defaults fail.')
		list_errs.append(4)

	if(eprom_const_err):
		print('Set when power-up checksum test on cal constants fail.')
		list_errs.append(3)

	if(v_source_conf_err):
		print('Set when trying to send a voltage source value to the Model 487 that exceeds the maximum limit of the currently selected voltage sauce range.')
		list_errs.append(2)

	if(vsource_err):
		print('On the Model 487, this bit is set when trying to place the voltage source in operate while the enabled interlock is open.')
		list_errs.append(1)

	if len(list_errs) == 0:
		raise Exception('An error was raised but no actual error was translated. This probably means weird picoammeter behavior.')

	return list_errs

def translatePicoammeterPS_status(err):
	if(isinstance(err, str)):
		raise Exception("Error is a string: " + err + " if empty check if the system is behaving as normal.")

	err_i = int(err)

	if(err_i == 0):
		print("No error in the power supply!")
		return True

	curr_lim_err = 	get_digit(err_i, 1) == 1
	interlock_err = get_digit(err_i, 0) == 1

	list_errs = []
	print("Errors found: (the next error warnings are taken from the manual)")

	if curr_lim_err:
		print('The voltage source is now (or was previously) in current limit (Up.4 or 2.5n-A)')
		list_errs.append(2)

	if interlock_err:
		print('The enabled interlock circuit is now (or was previously) open (ie. lid of test fixture open).')
		list_errs.append(1)

	if len(list_errs) == 0:
		raise UnknownTranslationError


	return list_errs

def translate_ESR(esr):
	pass

def checkPicoAmmeterStatus(port):
	# U1 = Send machine error status word
	port.scpi_write('U1X')
	port.flush()
	port.wait_cmd_done()

	err_word = port.readline()
	err_word = err_word.decode("ASCII")
	err_val = float(err_word) - 4870000000000000
	# If the word is equal to 0 implies no error

	r = translatePicoammeterStatus(err_val)

	if isinstance(r, list):
		print('Several errors happened on the picoammeter.')
		return r
	elif isinstance(r, bool):
		if r:
			print("Picoammeter checked succesfully!")
			return True
	else:
		raise Exception('Something weird happened...')

def checkPicoammeterPS_status(port):
	# U9 = Power supply error status word
	port.scpi_write('U9X')
	port.flush()
	port.wait_cmd_done()

	err_word = port.readline()
	err_word = err_word.decode("ASCII")
	err_val = float(err_word) - 48700

	r = translatePicoammeterPS_status(err_val)

	if isinstance(r, list):
		print('Several errors happened on the picoammeter power supply.')
		return r
	elif isinstance(r, bool):
		if r:
			print("Picoammeter checked succesfully!")
			return True
	else:
		raise Exception('Something weird happened...')


def check_device_status(port):
	port.read_esr()

