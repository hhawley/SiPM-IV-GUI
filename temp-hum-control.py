from grapher import grapher_process_main
from secretary import file_process_main
from arduinoer import arduino_process_main

from multiprocessing import (Process, Queue)
from queue import Empty
from threading import Thread

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
import numpy as np
import time
import configparser
from itertools import count

# The boss of the Processes is this script reading the stdin
# Command expected as:
# [TO] [CMD] [Value]
# Where CMD is the command 
def loop(queue):
	while True:
		cmd = input('[Command] ')
		# fstrings are interesting
		print(f'[Boss] Sending command "{cmd}" to the control software.')

		cmd_split = cmd.split(' ')

		queue.put(cmd_split)

		if cmd_split[0] == 'close':
			print('[Boss] Closing everything.')
			break

def read_config():
	config = configparser.ConfigParser()

	with open('file.cfg') as f:
		config.read_file(f)

	return config['MAIN']

def main():
	try:

		config = read_config()

		ardInQueue = Queue()
		ardOutQueue = Queue()
		graQueue = Queue()
		consoleQueue = Queue()
		# iv_Queue = Queue() 

		# Arduino code that measures the humidity/temperature measurements
		humtemp_process = Process(target=arduino_process_main, \
			kwargs={'inQueue' : ardInQueue, 'outQueue' : ardOutQueue})

		# Secretary (file Manager)
		file_process = Process(target=file_process_main, \
			kwargs={'bossQueue' : consoleQueue, 'graQueue' : graQueue, \
			'ardOutQueue' : ardOutQueue, 'ardInQueue' : ardInQueue, \
			'ivOutQueue' : None, 'ivInQueue' : None })

		# Code that plots every data avaliable
		gra_process = Process(target=grapher_process_main, args=(graQueue,), kwargs={'humidity_only' : True})

		# Reads stdin
		# https://stackoverflow.com/questions/8976962/is-there-any-way-to-pass-stdin-as-an-argument-to-another-process-in-python
		boss_thread = Thread(target=loop, args=(consoleQueue,))

		# if config.getboolean('IVMeasurements'):

		
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
