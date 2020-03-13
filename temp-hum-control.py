from sipm_files import sipm_setup, sipm_arduino, sipm_measurements, sipm_voltage, sipm_dataTaking
from grapher import grapher_process_main
from secretary import file_process_main
from arduinoer import arduino_process_main

from multiprocessing import Process, Queue
from queue import Empty

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
import numpy as np
import time
from itertools import count

def main():
	try:

		file_ard_Queue = Queue()
		file_gra_Queue = Queue()

		# Arduino code that measures the humidity/temperature measurements
		humtemp_process = Process(target=arduino_process_main, args=(file_ard_Queue, ))

		# Secretary (file Manager)
		file_process = Process(target=file_process_main, args=(file_ard_Queue, file_gra_Queue))

		# Code that plots every data avaliable
		gra_process = Process(target=grapher_process_main, args=(file_gra_Queue,), kwargs={'humidity_only' : True})
		
		humtemp_process.start()
		file_process.start()
		gra_process.start()

		humtemp_process.join()
		file_process.join()
		gra_process.join()

	finally:
		pass

if __name__ == '__main__':
    main()
