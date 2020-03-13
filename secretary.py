from sipm_files import sipm_dataTaking

from multiprocessing import Process, Queue
from queue import Empty

import time
import configparser

def read_config():
	config = configparser.ConfigParser()

	with open('file.cfg') as f:
		config.read_file(f)

	return config['FILE']

### Initial while-loop to start the program ###
def wait_for_main(queue, timeout=15*60):
	timeoutCounter = 0
	startTime = time.time()
	
	onGoing = False
	while not onGoing:
		time.sleep(1)
		timeoutCounter = (time.time() - startTime) 

		if timeoutCounter > timeout:
			raise Exception('Timeout from main process. (FileManager)')

		try:
			items = toIv.get_nowait()
			# item[0] -> start
			# item[1] -> num of elements
			onGoing	= items[0]
			file.create_dataset(items[1], nameofMeasurements)
		except Empty as err:
			pass

def loop(ard_queue, gra_queue, file, iv_queue=None):
	### Saving data to file while-loop ###
	print('[File] Starting listening.')
	onGoing = True
	while onGoing:
		time.sleep(0.1)
		try:
			items = iv_queue.get_nowait()
			# item[0] -> value to save
			# item[1] -> index
			# item[2] -> should stop
			if items[0] is not None:
				file.add_IV(items[0], items[1])
				gra_queue.put([items[0][0], None, items[0][1], items[0][2], None, None, True])

			onGoing = items[2]
		except Empty as err:
			pass
		except AttributeError:
			# Error that gets executed if iv_queue is None
			pass
		except Exception as err:
			print(err)

		try:
			items = ard_queue.get_nowait()
			# item[0] -> value to save
			# item[1] -> index
			file.add_HT(items[0], items[1])
			gra_queue.put([None, items[0][0], None, None, items[0][1], items[0][2], True])
		except Empty as err:
			pass
		except Exception as err:
			print(err)

def file_process_main(ard_queue, gra_queue, iv_queue=None):
	file = None

	# Only three config for now. Database name, file name and comment
	# Maybe expand to include number of data points, time, etc
	configs = read_config()
	db_name = configs['DBName']
	name_of_measurements = configs['FileName']
	comment = configs['Comment']

	try:
		print('[File] Setting up database.')
		file = sipm_dataTaking.sipmFileManager(db_name)
		file.create_dataset(name_of_measurements)
		file.add_attribute('Comment', comment)

		# This part might be deprecated soon keeping it for now
		# if toIV is not None:
		# 	print('[File] This should not happen')
		# 	wait_for_main(toIv)
		# else:
		# 	print('[File] No I-V process detected. Going to loop.')
		print('[File] No I-V process detected. Going to loop.')
		loop(ard_queue, gra_queue, file, iv_queue=iv_queue)
		
	except Exception as err:
		print('[File] Error with the file manager. Deleting previous data base.')
		print('[File] error: %s' % err)
		file.delete_dataset()
	finally:
		if file is not None:
			file.close()