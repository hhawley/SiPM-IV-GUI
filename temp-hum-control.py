from sipm_files import sipm_setup, ArduinoManager, sipm_measurements, sipm_voltage, FileManager
from grapher import grapher_process_main
from secretary import file_process_main
from arduinoer import arduino_process_main

from multiprocessing import Process, Queue
from queue import Empty
from threading import Thread

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
import numpy as np
import time
from itertools import count

# The boss of the Processes is this script reading the stdin
# Command expected as:
# [TO] [CMD] [Value]
# Where CMD is the command 
def loop(queue):
	while True:
		cmd = input('[Command] ')
		print('[Boss] Sending command \'%s\' to the control software.' % cmd)

		cmd_split = cmd.split(' ')

		queue.put(cmd_split)

		if cmd_split[0] == 'close':
			print('[Boss] Closing everything.')
			break

def main():
	try:

		file_ard_Queue = Queue()
		file_gra_Queue = Queue()
		console_Queue = Queue()

		# Arduino code that measures the humidity/temperature measurements
		humtemp_process = Process(target=arduino_process_main, args=(file_ard_Queue, ))

		# Secretary (file Manager)
		file_process = Process(target=file_process_main, args=(file_ard_Queue, file_gra_Queue, console_Queue))

		# Code that plots every data avaliable
		gra_process = Process(target=grapher_process_main, args=(file_gra_Queue,), kwargs={'humidity_only' : True})

		# Reads stdin
		# https://stackoverflow.com/questions/8976962/is-there-any-way-to-pass-stdin-as-an-argument-to-another-process-in-python
		boss_thread = Thread(target=loop, args=(console_Queue,))
		
		boss_thread.start()
		humtemp_process.start()
		file_process.start()
		gra_process.start()

		boss_thread.join()
		humtemp_process.join()
		file_process.join()
		gra_process.join()

		

	finally:
		pass

if __name__ == '__main__':
    main()
