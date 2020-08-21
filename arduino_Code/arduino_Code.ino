// Arduino libs
#include <Wire.h>

// PC comm libs
#include <inttypes.h>
#include <VariablesTransfer.h>

// PID libs
#include <AutoPID.h>

// Sensors libs
#include <DFRobot_MCP4725.h> // DAC source
#include <DFRobot_INA219.h>  // Wattmeter
#include <Adafruit_MAX31865.h> // RTD meter
#include <DHT.h> // Humidity/temp sensor

// My libs
#include "config.h"

// Program states
enum STATES{STANDBY, RUNNING} state;

// DAC controls the current
bool dac_err = false;
DFRobot_MCP4725 DAC;

// INA219 measured the current
DFRobot_INA219_IIC ina219(&Wire, INA219_I2C_ADDRESS4);

// MAX31865 Temp sensor
Adafruit_MAX31865 thermo(10, 11, 12, 13);

// DHT22 humidity/temp sensor
bool dht_err = false;
DHT dht(DHTPIN, DHTTYPE);

// Calibration vals
float ina219Reading_mA = 1000;
float extMeterReading_mA = 1004;

double desired_curr = MAX_CURR;
double desired_temp = 10;
double latest_curr = 0;
double latest_volt = 0;
double latest_humi = 0.0;
double latest_temp = 20.0;

//double Kp=1.1, Ki=44, Kd=0.02;

// High, 300ma and up, current PID values
double Kp=0, Ki=1, Kd=0.02;

double T_Kp = -700, T_Ki = -10, T_Kd=-20;

// Replace desired_curr with desired_temp
// and latest_curr with latest_temp
// for temp PID
AutoPID current_PID(&latest_curr, &desired_curr, &latest_volt, 
  MIN_VOLT, MAX_VOLT,
  Kp, Ki, Kd);

AutoPID temp_PID(&latest_temp, &desired_temp, &latest_volt, 
  MIN_VOLT, MAX_VOLT,
  T_Kp, T_Ki, T_Kd);

bool vt_err = 0;
// PC comm pointers
// from most significant bit to lower:
// XXXX XXXX XXX SET_DES_TEMP[1] RESET_ERROR[1] TOGGLE_STATE[1] SEND_HT[1] READ_HUMIDIY[1]
// READ_HUMIDIY[1] -> Starts a hum measurement
// SEND_HT[1] -> Send a temperature (RTD) and humidity measurement
// TOGGLE_STATE[1] -> Toggles between STANDBY and RUNNING
// RESET_ERROR[1] -> Resets error part of the status flag
#define READ_HUMIDIY_BIT 0
#define SEND_HT_BIT 1
#define TOGGLE_STATE_BIT 2
#define RESET_ERROR_BIT 3
#define SET_DES_BIT 4
uint16_t* COMMAND_REGISTER;
// Saves the current temperature
uint16_t* CURR_TEMP_REGISTER;
// Saves the desired temperature
uint16_t* DESI_TEMP_REGISTER;
// from most significant bit to lower:
// XXXX STATUS[1] DAC_ERR[1] DHT_ERR[1] VT_ERR[1] RTD_ERR[8]  
// No error checking for the ina219 (wattmeter) available
#define STATUS_BIT 11
#define DAC_ERR_BIT 10
#define DHT_ERR_BIT 9
#define VT_ERR_BIT 8
#define RTD_ERR 0
uint16_t* STATUS_FLAG;

// temp = (35+10) / (2^16-1) (x) - 10
double uint_to_temp(uint16_t val) {
  return (45.0/UINT16_MAX)*val - 10;
}

#define TEMP_TO_UINT(x) (uint16_t)(x+10)*(UINT16_MAX/45)


bool errorCheck() {

  // RTD error checking
  // Fault is a 8 bits error
  uint8_t fault = thermo.readFault();
  *STATUS_FLAG &= 0xFF00; // Reset RTD error bits
  *STATUS_FLAG |= ( fault & 0x00FF);

  if(fault) {
    thermo.clearFault(); 
  }

  dac_err = DAC.check_mcp4725(); // Trust nobody...

  *STATUS_FLAG |= (dac_err << 8);
  *STATUS_FLAG |= (dht_err << 9);
  *STATUS_FLAG |= (vt_err << 10);

  // Checks if any of the error bits are higher than 0
  return (*STATUS_FLAG & 0x03FF) > 0;
}

void setup() {
  
  // Setup serial
  Serial.begin(115200);

  // Links serial variables
  VarTransfer::linkVariable(0, COMMAND_REGISTER);
  VarTransfer::linkVariable(1, CURR_TEMP_REGISTER);
  VarTransfer::linkVariable(2, DESI_TEMP_REGISTER);
  VarTransfer::linkVariable(3, STATUS_FLAG);
  
  // Initialize serial variables to default values
  *COMMAND_REGISTER = 0x0000;
  *CURR_TEMP_REGISTER = 0x0000;
  *DESI_TEMP_REGISTER = TEMP_TO_UINT(desired_temp);
  *STATUS_FLAG = 0x0000;

  // Sensors initialization
  dht.begin();

  ina219.begin();
  ina219.linearCalibrate(ina219Reading_mA, extMeterReading_mA);

  thermo.begin(MAX31865_3WIRE);

  DAC.init(MCP4725A0_IIC_Address0, REF_VOLTAGE);
  DAC.outputVoltage(0);

  // Initialize PID
  current_PID.setTimeStep(CURRENT_PID_REFRESH_RATE);
  temp_PID.setTimeStep(PERIOD_RATE);
  
  delay(10);

  state = STANDBY;
  *STATUS_FLAG |= ((state & 0xFFFE) << 11);
}


// Listens to the PC
// and runs code based on what was changed.
void listen() {
  // PC comm checking
  int err = VarTransfer::processVariables(Serial);

  if(err == VT_SUCESS) {
    // Code to be executed if a correct transfer was made
    desired_temp = uint_to_temp(*DESI_TEMP_REGISTER);
  } else if(err != VT_NO_DATA){
    vt_err = true;
  }

  if(bitRead(*COMMAND_REGISTER, READ_HUMIDIY_BIT)) {
     latest_humi = dht.readHumidity();
     dht_err = (latest_humi == NAN) & 0xFFFE;

     bitWrite(*COMMAND_REGISTER, READ_HUMIDIY_BIT, false);
  }

  if(bitRead(*COMMAND_REGISTER, SEND_HT_BIT)) {
    Serial.print(latest_humi);
    Serial.print(",");
    Serial.println(latest_temp);
    bitWrite(*COMMAND_REGISTER, SEND_HT_BIT, false);
  }

}



void standby() {
  listen();

  latest_temp = thermo.temperature(RNOMINAL, RREF);
  *CURR_TEMP_REGISTER = TEMP_TO_UINT(latest_temp);

  // Only way to reset the STATUS_flag
  // is by being on standby and
  // asking to read it.
  if(bitRead(*COMMAND_REGISTER, RESET_ERROR_BIT)) {
    STATUS_FLAG = 0x0000;
    bitWrite(*STATUS_FLAG, STATUS_BIT, state);
    bitWrite(*COMMAND_REGISTER, RESET_ERROR_BIT, false);
  }

  if(bitRead(*COMMAND_REGISTER, TOGGLE_STATE_BIT)) {

    if(STATUS_FLAG > 0) {
      state = RUNNING;
      bitWrite(*STATUS_FLAG, STATUS_BIT, state);
    }

    bitWrite(*COMMAND_REGISTER, TOGGLE_STATE_BIT, false);
  }

  // In standy, the peltier should not be
  // working!
  DAC.outputVoltage(0);
}

void run() {
  listen();

  latest_temp = thermo.temperature(RNOMINAL, RREF);
  *CURR_TEMP_REGISTER = TEMP_TO_UINT(latest_temp);
  latest_curr = ina219.getCurrent();

  // Run PID to control temperature/current
  double temp_diff = abs(desired_temp - latest_temp);
  // When temperature difference is high
  // we run on a constant current mode
  if(temp_diff > 5.0) {
    current_PID.run();
  } else if(temp_diff < 5.0) {
    temp_PID.run();
  }

  DAC.outputVoltage(latest_volt);
  
  if(errorCheck()) {
    state = STANDBY;
    bitWrite(*STATUS_FLAG, STATUS_BIT, state);

  }

  if(bitRead(*COMMAND_REGISTER, TOGGLE_STATE_BIT)) {
    state = STANDBY;
    bitWrite(*STATUS_FLAG, STATUS_BIT, state);
    bitWrite(*COMMAND_REGISTER, TOGGLE_STATE_BIT, false);
  }
}

void loop() {

  // Get latest values
  switch(state) {
    
    case RUNNING:
      run();
    case STANDBY:
    default:
      standby();

  }

}
