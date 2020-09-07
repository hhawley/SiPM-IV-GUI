import serial

# Manages the error reading, checking and translating of
# all the devices.
# NOTE: redpitaya has no way to error check. God help us
# all

class ErrorHelper:
	def __init__(self, port, rpport):
			self.port = port
			self.rpport	= rpport

	# Translates 487 error string
	def TranslatePicoammeterStatus(self, err_in):
		# In theory this should not happen but just adding normal checks
		if(err_in == "4870000000000000"):
			print('[IV Equipment] No error in the picoammeter!')
			return ''

		if len(err_in) != 16:
			err_out = f'{err_out}. Error is not the correct size. Connection or timing \
				issues suspected' 
			return err_out

		if err_in[15:13] != '487':
			err_out = f'{err_out}. Error is the correct length but header is incorrect. \
				Error possibly just happens to be the correct length: \
				check for connection of timing issues'
			return err_out

		idcc_err = 			err_in[12]
		idcco_err = 		err_in[11]
		no_rem_err = 		err_in[10]
		self_test_err = 	err_in[9]
		trigg_overrun_err = err_in[8]
		conflict_err = 		err_in[7]
		call_lock_err = 	err_in[6]
		zero_check_err = 	err_in[5]
		cal_err = 			err_in[4]
		eprom_def_err = 	err_in[3]
		eprom_const_err = 	err_in[2]
		v_source_conf_err = err_in[1]
		vsource_err = 		err_in[0]

		err_out = 'Errors found in the picoammter: \
			(the next error warnings are taken from the manual)'
		if idcco_err == "1":
			err_out = f'{err_out}. Set when an illegal device-dependent command \
				(such as ElX is received (\'E\'is illegal)'

		if idcco_err == "1":
			err_out = f'{err_out}. Set when an illegal device-dependent command \
				option such as TIOX is received (“IO” is illegal)'

		if no_rem_err == "1":
			err_out = f'{err_out}. Set when a programming command is received \
				when instrument is in the local state'

		if self_test_err == "1":
			err_out = f'{err_out}. Set when a self-test fails (RAM and/or ROM) occurs'

		if trigg_overrun_err == "1":
			err_out = f'{err_out}. Set when the instnunent receives a trigger while \
				it is still processing a reading from a previous tripper'

		if conflict_err == "1":
			err_out = f'{err_out}. Set when trying to send a calibration value with \
				the instrument on a measurement range that is too small to \
				accommodate the value'

		if call_lock_err == "1":
			err_out = f'{err_out}. Set when calibrating the instrument with the \
				calibration switch in the locked (disabled) position'

		if zero_check_err == "1":
			err_out = f'{err_out}. Set when trying to calibrate the instrument \
				with zero check enabled'

		if cal_err == "1":
			err_out = f'{err_out}. Set when calibration results in a cal constant \
				value that is not within allowable limits. Repeated failure may \
				indicate that the Model 486/487 is defective'

		if eprom_def_err == "1":
			err_out = f'{err_out}. Set when power-up checksum test on defaults fail'

		if eprom_const_err == "1":
			err_out = f'{err_out}. Set when power-up checksum test on cal constants fail.'

		if v_source_conf_err == "1":
			err_out = f'{err_out}. Set when trying to send a voltage source value \
				to the Model 487 that exceeds the maximum limit of the currently \
				selected voltage sauce range'

		if vsource_err == "1":
			err_out = f'{err_out}. On the Model 487, this bit is set when trying \
				to place the voltage source in operate while the enabled interlock \
				is open.'

		return err_out

	def TranslatePicoammeterPSStatus(self, err_in):
		# In theory this should not happen but just adding normal checks
		if(err_in == '48700'):
			print('[IV Equipment] No error in the picoammeter!')
			return ''

		if len(err_in) != 5:
			err_out = f'{err_out}. Error is not the correct size. Connection or timing \
				issues suspected' 
			return err_out

		if err_in[4:2] != '487':
			err_out = f'{err_out}. Error is the correct length but header is incorrect. \
				Error possibly just happens to be the correct length: \
				check for connection of timing issues'
			return err_out

		curr_lim_err = 	err_in[1]
		interlock_err = err_in[0]

		err_out = 'Errors found in the picoammter power supply: \
			(the next error warnings are taken from the manual)'
		if curr_lim_err:
			err_out = f'{err_out}. The voltage source is now (or was previously) \
				in current limit'

		if interlock_err:
			err_out = f'{err_out}. The enabled interlock circuit is now (or was \
				previously) open (ie. lid of test fixture open)'

		return err_out

	def translate_ESR(esr):
		pass

	# Returns (status, error)
	def CheckPicoammeterStatus(self):

		# U1 = Send machine error status word
		self.port.SetToPicoammter()
		self.port.SCPIWrite('U1X')
		487_error = self.port.readline()
		487_error = 487_error.decode("ASCII")

		# If the word is equal this string, it implies no error.
		if 487_error == "4870000000000000":
			return (True, '')

		# if there is an error:
		error = TranslatePicoammeterStatus(487_error)

		return (False, error)

	# Returns (status, error)
	def CheckPowerSupplyStatus(self):
		# U9 = Power supply error status word
		self.port.SetToPicoammter()
		self.port.SCPIWrite('U9X')
		487_error = self.port.readline()
		487_error = 487_error.decode("ASCII")

		if 487_error =='48700':
			return (True, '')

		error = TranslatePicoammeterPSStatus(487_error)

		return (False, error)


	def CheckDMMStatus(self):
		self.port.SetTo34401A()
		self.port.SCPIWrite('*ESR?')
		response = self.port.readline().decode("ASCII")

		# ESR responses always start with +
		if response[-1] != '+':
			return (False, 'Device did not respond correctly.')

		if response != '+0':
			# Grab all the errors.
			error = f'The multimeter presented the next errors (ESR = {response}): '
			while True:
				self.port.SCPIWrite('SYST:ERR?')
				errorResponse = self.port.readline().decode("ASCII")

				# No need to translate error as the DMM already gives a small
				# description of the error.

				# If errors starts with the '+' it implies no error
				if errorResponse[-1] == '+':
					break
				elif errorResponse[-1] == '-':
					error = f'{error}{errorResponse}, '

			return (False, error)
		else:
			return (True, '')



