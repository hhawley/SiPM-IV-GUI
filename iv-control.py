from grapher import grapher_process_main
from secretary import file_process_main
from arduinoer import arduino_process_main
from electrometer import electrometer_process_main
from Managers.LoggerManager import Logger

from multiprocessing import (Process, Queue)
from queue import Empty
from threading import Thread

import time
import configparser
import sys


# The boss of the Processes is this script reading the stdin
# Command expected as:
# [TO] [CMD] [Value]
# Where CMD is the command 
def loop(queue):
	while True:
		cmd = input('[Command] \n')
		# fstrings are interesting
		print(f'[Boss] Sending command "{cmd}" to the control software.')

		cmd_split = cmd.split(' ')

		queue.put(cmd_split)

		if cmd_split[0] == 'close':
			print('[Boss] Closing everything.')
			break

		time.sleep(1.0/1000)

def read_config():
	config = configparser.ConfigParser()

	with open('file.cfg') as f:
		config.read_file(f)

	return config['MAIN']

def main():
	try:

		# Makes sure all output gets written to a log and console.
		sys.stdout = Logger()

		config = read_config()

		ivInQueue = Queue()
		ivOutQueue = Queue()
		graQueue = Queue()
		consoleQueue = Queue()
		ardOutQueue = Queue()
		ardInQueue = Queue()

		# Arduino code that measures the humidity/temperature measurements
		# and controls the peltier.
		humtemp_process = Process(target = arduino_process_main, \
			kwargs={'inQueue' : ardOutQueue, 'outQueue' : ardInQueue })

		# Secretary (file/comm Manager)
		file_process = Process(target = file_process_main, \
			kwargs={'bossQueue' : consoleQueue, 'graQueue' : graQueue, \
			'ardOutQueue' : ardOutQueue, 'ardInQueue' : ardInQueue, \
			'ivOutQueue' : ivOutQueue, 'ivInQueue' : ivInQueue })

		# Code that plots every data avaliable.
		gra_process = Process(target = grapher_process_main, \
			args=(graQueue,), kwargs={'humidity_only' : False})

		# Reads commands and parses them.
		boss_thread = Thread(target = loop, args = (consoleQueue,))

		# Electrometer manager.
		iv_thread = Thread(target = electrometer_process_main, \
			kwargs={'inQueue' : ivOutQueue, 'outQueue' : ivInQueue })
		
		boss_thread.start()
		humtemp_process.start()
		file_process.start()
		gra_process.start()
		iv_thread.start()

		boss_thread.join()
		humtemp_process.join()
		file_process.join()
		gra_process.join()
		iv_thread.join()

		

	finally:
		pass

if __name__ == '__main__':
    main()
