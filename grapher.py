import matplotlib.pyplot as plt
import numpy as np
import time

from queue import Empty
from matplotlib.animation import FuncAnimation
from multiprocessing import Process, Queue

def animate_all(i, file_queue, vals):
	try:
		items = file_queue.get_nowait()
		# item[0] -> time1
		# item[1] -> time2
		# item[2] -> voltage
		# item[3] -> current
		# item[4] -> humidity
		# item[5] -> temperature

		if len(items) == 6:
			for j in range(0, 6):
				if items[j] is not None:
					vals[j].append(items[j])

			onGoing = items[5]

			plt.clf()

			if vals[1]:

				ht_ax = plt.subplot(2, 2, 3, label='H-T')
				ht_ax.plot(vals[1], vals[4], color='tab:blue', label='Humidity')
				ht_ax.set_xlabel('time (s)')
				ht_ax.set_ylabel('Humidity (%)')

				ax_2 = ht_ax.twinx()
				bb = ax_2.plot(vals[1], vals[5], color='tab:red', label='Temperature')
				ax_2.set_ylabel('Temperature (C)')

				ht_ax.legend()
				ax_2.legend(loc=0)

			if vals[0]:
				iv_ax = plt.subplot(2, 2, 1, label='I-V')
				iv_ax.plot(vals[2], vals[3], 'ro')
				iv_ax.set_ylabel('Current (A)')
				iv_ax.set_xlabel('Voltage (V)')

				v_ax = plt.subplot(2, 2, 2, label='V')
				v_ax.plot(vals[0], vals[3])
				v_ax.set_xlabel('time (s)')
				v_ax.set_ylabel('Current (A)')

				i_ax = plt.subplot(2, 2, 4, label='I')
				i_ax.plot(vals[0], vals[2])
				i_ax.set_xlabel('time (s)')
				i_ax.set_ylabel('Voltage (V)')

			plt.tight_layout()

	except Empty as err:
		pass
	except Exception as err:
		print('[Grapher] Error in the grapher: %s.' % err)

def animate_humidity(i, file_queue, vals):
	try:
		items = file_queue.get_nowait()
		# item[0] -> time1
		# item[1] -> time2
		# item[2] -> voltage
		# item[3] -> current
		# item[4] -> humidity
		# item[5] -> temperature

		if len(items) == 6:
			for j in range(0, 6):
				if items[j] is not None:
					vals[j].append(items[j])

			onGoing = items[5]

			plt.clf()

			if vals[1]:

				ht_ax = plt.subplot(1, 1, 1, label='H-T')
				ht_ax.plot(vals[1], vals[4], color='tab:blue', label='Humidity')
				ht_ax.set_xlabel('time (s)')
				ht_ax.set_ylabel('Humidity (%)')

				ax_2 = ht_ax.twinx()
				bb = ax_2.plot(vals[1], vals[5], color='tab:red', label='Temperature')
				ax_2.set_ylabel('Temperature (C)')

				ht_ax.legend()
				ax_2.legend(loc=0)

			
			plt.tight_layout()

	except Empty as err:
		pass
	except Exception as err:
		print('[Grapher] Error in the grapher: %s.' % err)

# file_queue -> Queue
def grapher_process_main(file_queue, humidity_only=False):

	time_vals 		= []
	time2_vals		= []
	voltage_vals 	= []
	current_vals 	= []
	humidity_vals 	= []
	temperature_vals= []

	plt.style.use('ggplot')

	if not humidity_only:
		anim = FuncAnimation(plt.gcf(), animate_all, \
			fargs=(file_queue, [time_vals, time2_vals, voltage_vals, current_vals, humidity_vals, temperature_vals]), \
			interval=300)
	else:
		anim = FuncAnimation(plt.gcf(), animate_humidity, \
			fargs=(file_queue, [time_vals, time2_vals, voltage_vals, current_vals, humidity_vals, temperature_vals]), \
			interval=300)

	plt.show()


# For testing purposes only:
def test_process(queue):
	for i in range(0, 100):
		time.sleep(2)
		queue.put([i, 1, i*i, 1/(i+1), 3*i, True])

def main():
	q = Queue()

	grap_p = Process(target=grapher_process_main, args=(q,))
	test_p = Process(target=test_process, args=(q,))

	test_p.start()
	grap_p.start()

	grap_p.join()
	test_p.join()

if __name__ == '__main__':
	main()