#pragma once

// PID defines
#define PID_TEMP
//#define PID_CURR
#define MIN_VOLT 0
#define MAX_VOLT 3800
#define MAX_CURR 4000

// Arduino voltage source. Not really necessary
#define REF_VOLTAGE 5110

// MAX31865 Temp sensor
// The value of the Rref resistor. Use 430.0 for PT100 and 4300.0 for PT1000
#define RREF      430.0
// The 'nominal' 0-degrees-C resistance of the sensor
// 100.0 for PT100, 1000.0 for PT1000
#define RNOMINAL  100.0

// PID temperature refresh rate (Hz)
#define REFRESH_RATE 20
#define PERIOD_RATE 1000/REFRESH_RATE //ms 

// PID current refresh time
#define CURRENT_PID_REFRESH_RATE 2 //ms

// DHT
#define DHTPIN 2 
#define DHTTYPE DHT22 

// Relay/Peltier Relay
#define RELAY_PIN 7
