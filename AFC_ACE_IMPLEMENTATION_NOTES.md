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

1. **lane1_offset** (configured value: 1.5mm) ✅
   - Distance from HOME to Lane 1 LOAD position
   - **MEASURED AND CONFIGURED** - Lane 1 LOAD is at 1.5mm from home endstop
   - This is the base position for all calculations

2. **steps_per_position** (configured value: 5.0mm) ✅
   - Distance between positions within a lane (LOAD → FREE → UNLOAD)
   - **MEASURED AND CONFIGURED**:
     - LOAD to FREE: 5mm
     - FREE to UNLOAD: 5mm
     - Total range: 10mm (1.5mm to 11.5mm for Lane 1)

3. **steps_per_lane** (placeholder value: 100mm) ⚠️ NEEDS CALIBRATION
   - Distance selector travels between adjacent lanes
   - Method: Manually find Lane 2 LOAD position, calculate: `Lane2_LOAD - lane1_offset`
   - Repeat for lanes 3 and 4 to verify consistent spacing

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

# Test Lane 1 positions (should match measured values):
ACE_SET_POSITION UNIT=ACE_1 LANE=1 POSITION=1  # Lane 1 LOAD (1.5mm)
ACE_SET_POSITION UNIT=ACE_1 LANE=1 POSITION=0  # Lane 1 FREE (6.5mm)
ACE_SET_POSITION UNIT=ACE_1 LANE=1 POSITION=2  # Lane 1 UNLOAD (11.5mm)

# Find and test other lanes (adjust steps_per_lane after finding):
ACE_SET_POSITION UNIT=ACE_1 LANE=2 POSITION=1  # Lane 2 LOAD
ACE_SET_POSITION UNIT=ACE_1 LANE=3 POSITION=1  # Lane 3 LOAD
ACE_SET_POSITION UNIT=ACE_1 LANE=4 POSITION=1  # Lane 4 LOAD

# Check all sensors
QUERY_ENDSTOPS

# Standard AFC calibration
CALIBRATE_AFC LANE=lane1        # Calibrate dist_hub for lane 1
CALIBRATE_AFC BOWDEN=lane1      # Calibrate bowden length
```

### Position Calculation Formula

```python
total_position = lane1_offset + (lane_index - 1) * steps_per_lane + position_offset

where:
  lane1_offset = 1.5mm  (distance from HOME to Lane 1 LOAD)
  steps_per_lane = ???mm (needs calibration - distance between lanes)
  position_offset:
    LOAD (1) = 0mm
    FREE (0) = 5mm
    UNLOAD (2) = 10mm

Examples for Lane 1 (with lane1_offset=1.5, steps_per_lane=N/A):
  LOAD:   1.5 + 0*N + 0  = 1.5mm
  FREE:   1.5 + 0*N + 5  = 6.5mm
  UNLOAD: 1.5 + 0*N + 10 = 11.5mm
```

---

## Tension Assist System

### Overview
AFC_ACE implements a custom tension assist system (`AFC_ACE_tension.py`) designed specifically for the ACE hardware. Unlike TurtleNeck buffer which adjusts rotation_distance, ACE tension assist actively feeds filament when tension is detected.

### Two Assist Modes

1. **Active Mode** (for long tube systems):
   - Selector stays in LOAD position during printing
   - When tension sensor triggers → Drive motor feeds `tension_feed_length` mm
   - Ideal for systems where tubes create significant drag
   - Maintains constant engagement with drive gear

2. **Passive Mode** (for short tube systems):
   - Selector moves to FREE position during printing
   - Filament moves freely without active feeding
   - No tension sensor monitoring
   - Minimal resistance, filament pulled by extruder only

### Hub Sensor & Buffer Zone Concept

**Proposed Loading Logic** (not yet implemented):
1. Load filament to hub sensor (junction of 4 lanes)
2. Retract `hub_retract_distance` (20mm default) into lane-specific buffer zone
3. Eliminates need to measure tube lengths manually
4. Buffer zone provides slack for tension variations

**Benefits:**
- Auto-calibration: hub sensor provides known reference point
- Consistent buffer: each lane has same 20mm slack
- Simpler setup: no manual tube length measurement needed

### Tension Assist Configuration

```ini
[AFC_ACE_tension ACE_tension1]
tension_pin: ^!ACE:TENSION1          # Hall sensor pin
assist_mode: passive                 # 'active' or 'passive'
tension_feed_length: 10.0            # mm to feed when tension detected (active mode)
tension_feed_speed: 50.0             # Feed speed in mm/s
tension_feed_accel: 400.0            # Feed acceleration in mm/s^2
hub_retract_distance: 20.0           # Buffer zone size (mm)
debug: False                         # Debug logging
enable_sensors_in_gui: True          # Show in Mainsail/Fluidd
```

### How It Works

**Integration with Lane:**
- Tension assist objects register in `afc.buffers` dict (same as TurtleNeck)
- Lane references tension assist via `buffer: ACE_tension1` parameter
- Lane calls `enable_buffer()` when loaded → tension assist activates
- Lane calls `disable_buffer()` when unloaded → tension assist deactivates

**Active Mode Operation:**
1. Lane loaded into toolhead
2. `enable_buffer()` → Selector moves to LOAD position
3. During printing: tension sensor triggers → callback activated
4. Drive motor feeds `tension_feed_length` mm
5. Minimum interval between assists: 0.5 seconds (configurable)

**Passive Mode Operation:**
1. Lane loaded into toolhead
2. `enable_buffer()` → Selector moves to FREE position
3. Tension sensor ignored
4. Filament moves freely

### Available Commands

```gcode
# Enable/disable tension assist
ENABLE_TENSION_ASSIST TENSION=ACE_tension1
DISABLE_TENSION_ASSIST TENSION=ACE_tension1

# Switch modes
SET_TENSION_MODE TENSION=ACE_tension1 MODE=active
SET_TENSION_MODE TENSION=ACE_tension1 MODE=passive

# Query status
QUERY_TENSION TENSION=ACE_tension1
```

### File Created
**File:** `extras/AFC_ACE_tension.py`

**Class:** `AFC_ACE_TensionAssist`

**Key Methods:**
- `tension_callback()`: Responds to tension sensor triggers
- `do_tension_assist()`: Executes assist move via Drive motor
- `enable_buffer()`: Activates assist, sets selector position
- `disable_buffer()`: Deactivates assist
- `buffer_status()`: Reports status (for compatibility)

---

## Known Issues / TODO

### Not Yet Implemented
- Hub sensor loading logic (hub sensor pin needs definition)
- Hub sensor retract-to-buffer integration
- Toolhead sensors (pin_tool_start, pin_tool_end) - user needs to configure
- UNLOAD position spool motor control (if using retraction)

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
1. `extras/AFC_ACE.py` - 357 lines, main implementation with selector positioning
2. `extras/AFC_ACE_tension.py` - 280 lines, tension assist system
3. `config/mcu/AcePro.cfg` - 38 lines, pinout definitions
4. `templates/AFC_ACE_1.cfg` - 221 lines, complete configuration with tension assist
5. `templates/AFC_Hardware-ACE.cfg` - 95 lines, extruder/buffer template

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
