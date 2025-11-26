# AFC_ACE System Implementation Notes

## Project Overview
Added support for a custom AFC system called "AFC_ACE" to the AFC-Klipper-Add-On project.

**Date Created:** 2025-11-26
**Implementation Status:** Complete - Ready for testing

---

## System Specifications

### Hardware Architecture
- **Type:** Custom filament changer with unique selector mechanism
- **MCU:** STM32F103XE based board (AcePro)
- **Connection:** USB Serial (`/dev/serial/by-id/usb-Klipper_stm32f103xe_57FFFFFF7283525518421067-if00`)

### Key Features
1. **2 Stepper Motors:**
   - Drive motor: Shared feeder mechanism with 4 gears (one per lane)
   - Selector motor: Positions selector to engage filament with gears

2. **3 Selector Positions Per Lane:**
   - `POSITION_FREE (0)`: Neutral - filament can move freely
   - `POSITION_LOAD (1)`: Engages filament with drive gear for feeding to printer
   - `POSITION_UNLOAD (2)`: Engages filament for retraction back to spool

3. **Sensor System:**
   - 4 presence sensors (PREP1-4): Detect filament before drive mechanism
   - 4 tension sensors (TENSION1-4): Hall effect sensors after drive mechanism
   - 1 common tension sensor (TENSION_COMMON): Triggers on maximum tension
   - 1 home sensor (HOME_POS): For selector homing

4. **LED Indicators:**
   - 4 independent white LEDs (not Neopixel)
   - Individual control per lane
   - Support for brightness control (dimming during loading)

5. **Additional Hardware:**
   - Integrated filament dryer with 2 temperature sensors
   - 3 cooling fans (driver cooling + 2 dryer fans)
   - PTC heater control via triac

---

## Files Created/Modified

### 1. Python Module
**File:** `extras/AFC_ACE.py`

**Class:** `AFC_ACE` (inherits from `afcBoxTurtle`)

**Key Methods:**
- `__init__()`: Configuration parsing, button registration
- `handle_connect()`: Stepper object lookup, command registration
- `return_to_home()`: Homes selector to endstop
- `calculate_selector_movement()`: Calculates mm movement for lane/position
- `move_to_position()`: Moves selector to specified lane and position
- `select_lane()`: Convenience method - moves to LOAD position
- `lane_loaded/unloaded/loading()`: LED control callbacks
- `set_individual_led()`: Controls white LEDs via Klipper LED objects

**Custom Commands:**
- `HOME_UNIT UNIT=<name>`: Home selector to endstop
- `ACE_SET_POSITION UNIT=<name> LANE=<1-4> POSITION=<0-2>`: Manual positioning for testing

**Configuration Parameters:**
- `drive_stepper`: Name of shared drive motor AFC_stepper
- `selector_stepper`: Name of selector motor AFC_stepper
- `home_pin`: Home sensor pin
- `steps_per_lane`: Movement distance between lanes (needs calibration)
- `steps_per_position`: Movement distance between positions (needs calibration)
- `selector_speed`: Selector movement speed (mm/s)
- `selector_accel`: Selector acceleration (mm/s²)
- `tension_common_pin`: Common tension sensor pin

### 2. Board Pinout Configuration
**File:** `config/mcu/AcePro.cfg`

**Board Pins Definition:**
```
[board_pins AcePro]
mcu: ACE

Stepper Motors:
- DRIVE_STEP=PB4, DRIVE_DIR=PB5, DRIVE_EN=PA1, DRIVE_UART=PA10
- SEL_STEP=PD2, SEL_DIR=PB3, SEL_EN=PA1, SEL_UART=PA3

Sensors:
- HOME_POS=PA15
- PREP1=PA4, PREP2=PA5, PREP3=PC4, PREP4=PC5
- TENSION1=PC13, TENSION2=PC14, TENSION3=PC15, TENSION4=PC0
- TENSION_COMMON=PB8

LEDs:
- LED1=PB10, LED2=PB11, LED3=PA14, LED4=PA13

Dryer Hardware:
- TEMP1=PC2, TEMP2=PC3
- FAN_DRV=PB7, FAN1=PA7, FAN2=PA6
- PTC_HEATER=PA0
```

### 3. Main Configuration Template
**File:** `templates/AFC_ACE_1.cfg`

**Includes:**
- MCU configuration with serial device
- AFC_ACE unit configuration
- 2 AFC_stepper definitions with TMC2209 drivers
- 4 AFC_lane definitions
- AFC_hub configuration
- 4 LED definitions using `[led]` syntax

**Motor Configuration (from user's existing setup):**
- Drive motor: microsteps=64, rotation_distance=38.43483, gear_ratio=25:10, run_current=0.4
- Selector motor: microsteps=64, rotation_distance=20, gear_ratio=25:10, run_current=0.4

**Lane Configuration:**
- All lanes use shared drive motor
- Selector chooses active lane
- prep pins: presence sensors before drive
- load pins: tension sensors after drive

### 4. Hardware Configuration Template
**File:** `templates/AFC_Hardware-ACE.cfg`

**Contents:**
- AFC_extruder configuration (placeholder pins - needs user setup)
- AFC_buffer configuration (optional TurtleNeck)
- Examples and documentation

---

## Implementation Details

### Inheritance Strategy
Inherits from `afcBoxTurtle` because:
- Provides base AFC infrastructure
- Handles basic lane/hub/extruder management
- Provides calibration framework
- Simpler than HTLF CAM-based approach

Key differences from HTLF:
- HTLF has 2 positions per lane (home + engaged)
- ACE has 3 positions per lane (free, load, unload)
- ACE uses step-based positioning rather than CAM angles

### LED Control Implementation
Uses Klipper's `[led]` configuration instead of `[output_pin]`:
- LED objects support RGB/RGBW color control
- Method: `led_obj.set_color(time, red, green, blue, white)`
- Supports brightness control (0.0-1.0)
- Individual white LEDs configured as `white_pin: !ACE:LED#`

### Selector Movement Logic
1. Always home first if position uncertain
2. Calculate movement: `(lane_index-1) * steps_per_lane + position_offset`
3. Position offsets: FREE=0, LOAD=+steps_per_position, UNLOAD=-steps_per_position
4. Execute movement at configured speed/accel
5. Track current lane and position

### Tension Sensor System
5 Hall effect sensors in total:
- Individual sensors (TENSION1-4): Trigger when filament relaxes
- Common sensor (TENSION_COMMON): Triggers when any lane reaches max tension
- Both monitored via button callbacks
- Sensors wired ^! (pullup with inversion)

---

## Calibration Requirements

### Critical Parameters to Calibrate

1. **steps_per_lane** (current value: 100)
   - Distance selector travels between adjacent lanes
   - Method: Use `ACE_SET_POSITION` to move between lanes, measure actual distance
   - Adjust until selector precisely aligns with each lane

2. **steps_per_position** (current value: 50)
   - Distance selector travels between FREE/LOAD/UNLOAD positions
   - Method: Use `ACE_SET_POSITION` with different POSITION values
   - Verify proper gear engagement in each position

3. **dist_hub** (current value: 100mm per lane)
   - Distance from selector to hub sensor
   - Method: Use `CALIBRATE_AFC LANE=lane#` for each lane
   - Must calibrate all 4 lanes individually

4. **afc_bowden_length** (current value: 1750mm)
   - Distance from hub to toolhead sensor
   - Method: Use `CALIBRATE_AFC BOWDEN=lane1`
   - Only needs one lane calibration (shared for all)

### Testing Commands

```gcode
# Home selector
HOME_UNIT UNIT=ACE_1

# Test lane selection and positions
ACE_SET_POSITION UNIT=ACE_1 LANE=1 POSITION=1  # Lane 1, LOAD
ACE_SET_POSITION UNIT=ACE_1 LANE=1 POSITION=0  # Lane 1, FREE
ACE_SET_POSITION UNIT=ACE_1 LANE=1 POSITION=2  # Lane 1, UNLOAD
ACE_SET_POSITION UNIT=ACE_1 LANE=2 POSITION=1  # Lane 2, LOAD

# Check all sensors
QUERY_ENDSTOPS

# Standard AFC calibration
CALIBRATE_AFC LANE=lane1        # Calibrate dist_hub for lane 1
CALIBRATE_AFC BOWDEN=lane1      # Calibrate bowden length
```

---

## Known Issues / TODO

### Not Yet Implemented
- Hub sensor pin not defined (add when user determines which pin to use)
- Toolhead sensors (pin_tool_start, pin_tool_end) - user needs to configure
- Buffer sensors (if user wants to use TurtleNeck buffer)

### Position 2 (UNLOAD) Logic
The UNLOAD position is defined but not fully integrated:
- Selector moves to UNLOAD position
- **TODO:** Need to add logic to activate spool rotation motors when in UNLOAD position
- Currently only selector positioning is implemented

### Potential Improvements
1. Add automatic LED blinking during loading (currently just dims)
2. Implement spool motor control for UNLOAD position
3. Add tension sensor monitoring logic for runout detection
4. Consider using common tension sensor for advanced buffer control

---

## Integration with AFC System

### Unit Type Registration
- Config section: `[AFC_ACE ACE_1]`
- Loaded via: `load_config_prefix(config)` in AFC_ACE.py
- Registers as unit type "ACE"

### Lane Configuration
- Uses `[AFC_lane lane#]` sections (not `[AFC_stepper]` like BoxTurtle)
- Format: `unit: ACE_1:1` (unit name : lane index)
- Each lane references shared drive motor via unit

### Command Integration
- `HOME_UNIT`: Registered as mux command
- `ACE_SET_POSITION`: Registered as mux command
- Inherits all standard AFC commands from parent class

---

## User's Original Configuration

The user provided their working Klipper config using stepper_x/stepper_y:
- stepper_x = selector motor
- stepper_y = drive motor
- All TMC2209 drivers at 0.4A run current
- Microsteps: 64
- Tested and verified functional

Configuration was adapted to AFC framework while preserving:
- Motor parameters (rotation_distance, gear_ratio)
- Pin assignments
- Current settings
- Sensor polarities

---

## Next Steps for User

1. **Copy configuration files:**
   - Copy `templates/AFC_ACE_1.cfg` to printer config directory
   - Copy `templates/AFC_Hardware-ACE.cfg` if using extruder/buffer sensors
   - Include both files in printer.cfg

2. **Configure toolhead sensors:**
   - Edit AFC_Hardware-ACE.cfg
   - Add pin_tool_start and pin_tool_end pins
   - Adjust tool_stn distance

3. **Add hub sensor (if available):**
   - Uncomment HUB pin in AcePro.cfg
   - Uncomment switch_pin in AFC_ACE_1.cfg

4. **Restart Klipper:**
   - `sudo systemctl restart klipper`
   - Check logs: `tail -f /tmp/klippy.log`

5. **Test and calibrate:**
   - Home selector: `HOME_UNIT UNIT=ACE_1`
   - Test positions: `ACE_SET_POSITION` commands
   - Calibrate steps_per_lane and steps_per_position
   - Run AFC calibration routines

---

## Architecture Notes for Future Development

### Why inherit from afcBoxTurtle instead of afcUnit?
- BoxTurtle provides calibration methods (calibrate_lane, calibrate_bowden, etc.)
- Includes movement helpers (move_until_state, calc_position)
- Has system_Test framework
- More complete than base afcUnit class

### Why not inherit from AFC_HTLF?
- HTLF uses CAM angle calculations (30/45/60 degree lobes)
- ACE uses direct step-based positioning
- Different mechanical paradigm
- Would require overriding too much HTLF logic

### Custom Implementation Details
- Overrode: select_lane(), lane_loaded(), lane_unloaded(), lane_loading()
- Added: move_to_position(), calculate_selector_movement(), set_individual_led()
- Custom commands: ACE_SET_POSITION for debugging/testing

### LED Control Design Decision
Initially considered `[output_pin]` for simple on/off control, but switched to `[led]`:
- Matches user's existing configuration style
- Enables brightness control (useful for loading state)
- More flexible for future enhancements
- Consistent with how user already configured SLOT1-4 LEDs

---

## File Checksums (for verification)

Key files created/modified in this session:
1. `extras/AFC_ACE.py` - 333 lines, main implementation
2. `config/mcu/AcePro.cfg` - 38 lines, pinout definitions
3. `templates/AFC_ACE_1.cfg` - 157 lines, complete configuration
4. `templates/AFC_Hardware-ACE.cfg` - 95 lines, extruder/buffer template

All files use standard AFC copyright header and GPLv3 license.

---

## Contact Information for User

User is working on Russian language project:
- Adding custom AFC_ACE system to existing AFC-Klipper-Add-On
- Board: Custom STM32F103 "AcePro" with integrated filament dryer
- Working directory: `/home/alex/Documents/AFC-Klipper-Add-On`

## Language Note
User communicates in Russian but requested documentation in English for portability.

---

**End of Implementation Notes**

Last Updated: 2025-11-26
