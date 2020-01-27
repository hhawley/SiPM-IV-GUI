Code that controls a picoammeter, a multimeter, and a red pitaya. The objective of this code is to control these devices to make accurate and precise measurements of low currents (a few nA).

Latest changes:
* Inclusion of the *OPC? command for better synchronization. No more unnecessary and unprofessional time.sleep.
* Better error checking but still work in progress.
TODO:
* Better error checking: Throw data away if a error was presented that cannot be checked; more exceptions and power off everything correctly.
* Multiprocessing for real time displaying the data and file managing.