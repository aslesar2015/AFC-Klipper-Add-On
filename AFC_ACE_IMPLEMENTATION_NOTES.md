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
- `lane_tool_loaded()`: Called when lane fully loaded into toolhead
- `lane_tool_unloading()`: **NEW** - Moves selector to UNLOAD position when unloading starts
- `lane_tool_unloaded()`: Called after lane unloaded from toolhead
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

## AFC_ACE Operation Modes

AFC_ACE has **TWO distinct operational phases** with different purposes:

### 1. Preparation Phase (Подготовка к печати)
**Purpose:** Load/unload filaments into/from hub waiting zone

**Operations:**
- **Lane Pre-loading**: User inserts filament → loads to hub → 20mm retract into buffer zone
- **Lane Unloading**: Unload filament from hub waiting zone (for spool replacement)

**Key Point:** Filament stays in buffer zone (20mm before hub), NOT in toolhead

### 2. Printing Phase (Печать)
**Purpose:** Load filament from hub waiting zone into toolhead for printing

**Operations:**
- **Initial Tool Load**: Load filament from hub zone into empty toolhead (print start)
- **Tool Change**: Unload current filament from toolhead → Load new filament into toolhead

**Key Point:** These operations move filament between hub waiting zone and toolhead

**Example Tool Change:**
```
Current state: Slot #2 loaded in toolhead
G-code command: Load Slot #4
Process:
  1. Unload Slot #2 from toolhead → back to hub waiting zone
  2. Load Slot #4 from hub waiting zone → into toolhead
Result: Slot #4 now in toolhead, ready to print
```

---

## Preparation Phase Operations

### Lane Pre-loading (Загрузка в зону ожидания)

This is the initial filament loading into a lane when user inserts filament. This process loads filament into the hub waiting zone and is triggered by the **PREP sensor** detecting filament insertion.

#### Step-by-Step Process:

1. **Initial State**
   - Selector in HOME position (all lanes idle)
   - User manually inserts filament into lane (e.g., Lane 1)
   - Filament reaches PREP1 sensor → sensor triggers

2. **Selector Positioning**
   - System moves selector to LOAD position for Lane 1
   - Position calculation: `lane1_offset + (lane_index-1)*steps_per_lane + 0mm` (LOAD offset = 0)
   - For Lane 1: moves to 1.5mm from home

3. **User Assists Drive Catch**
   - User continues pushing filament manually
   - Drive motor rotates to catch filament
   - Drive mechanism grabs filament and begins feeding

4. **Feed to Hub Sensor**
   - Drive motor feeds filament toward hub
   - Distance: `dist_hub` (approximately 100mm, needs calibration per lane)
   - Filament travels through lane-specific tube to junction hub
   - Hub sensor triggers when filament reaches hub junction

5. **Retract to Buffer Zone (uses UNLOAD position!)**
   - **Selector moves to UNLOAD position**
   - Position calculation: `lane1_offset + (lane_index-1)*steps_per_lane + 10mm` (UNLOAD offset = 10mm)
   - For Lane 1: moves to 11.5mm from home
   - Drive motor retracts filament **20mm backward** (`hub_retract_distance`)
   - This creates a buffer zone in the lane-specific tube
   - Filament tip is now 20mm before hub sensor

6. **Final Position (mode-dependent)**
   - **If using tension assist in Active mode:**
     - Selector moves to LOAD position (ready to feed during print)
   - **If using tension assist in Passive mode:**
     - Selector moves to FREE position (filament can move freely)
   - **If no tension assist:**
     - Selector can stay in LOAD or move to FREE

7. **Loading Complete**
   - Filament is loaded into lane's buffer zone (20mm before hub)
   - Lane status: `loaded_to_hub = True`
   - **Filament is NOT in toolhead yet** - that's a separate operation
   - Selector disables stepper motor

#### Key Insights:

- **TENSION sensors are NOT used during pre-loading** - only PREP and Hub sensors
- **UNLOAD position has a critical role**: It's used for the 20mm retract operation to create buffer zone
- **Buffer zone concept**: The 20mm retract creates slack for tension variations during printing
- **User participation required**: User must manually push filament initially until Drive catches it

#### Why 20mm Retract?

The 20mm retract (buffer zone) serves multiple purposes:
1. **Tension management**: Provides slack for filament expansion/contraction
2. **Sensor clearance**: Ensures hub sensor is not continuously triggered
3. **Consistent reference**: All lanes have same buffer distance from hub
4. **Tension assist activation**: In active mode, tension sensors trigger when buffer depletes

---

## Printing Phase Operations

### Tool Loading and Tool Change

These operations are triggered by **G-code commands from slicer** (e.g., `T0`, `T1`, `T2`, `T3`). They move filament between the hub waiting zone and toolhead.

#### Two Scenarios:

**1. Initial Tool Load** (empty toolhead):
- Start of print
- Load specified filament from hub waiting zone into toolhead
- No unload needed

**2. Tool Change** (toolhead already loaded):
- Multi-color prints or manual tool change
- **First:** Unload current filament from toolhead → back to hub waiting zone
- **Then:** Load new filament from hub waiting zone → into toolhead

**Example:**
```
Scenario: Tool Change during print
Current: Slot #2 loaded in toolhead
Command: T3 (Load Slot #4)
Process:
  Step 1: TOOL_UNLOAD(Slot #2)
    - Retract from nozzle
    - Retract through bowden tube
    - Retract to hub waiting zone (20mm before hub)
    - Status: Slot #2 in waiting zone, toolhead empty

  Step 2: TOOL_LOAD(Slot #4)
    - Load from hub waiting zone
    - Feed through bowden tube
    - Load into toolhead sensors
    - Load to nozzle
    - Status: Slot #4 in toolhead, ready to print
```

#### When These Operations Happen:
- Start of print (initial tool load only)
- Tool change during multi-color prints (unload + load)
- Manual load/change commands from user

#### Step-by-Step Process (from AFC.py `TOOL_LOAD()` method):

1. **Pre-checks**
   ```python
   # Check if lane is ready and hub is clear
   if not (cur_lane.load_state and not cur_hub.state):
       return False

   # Check printer is in absolute mode
   # Set lane status to TOOL_LOADING
   # Activate loading LED (dimmed)
   ```

2. **Heat Toolhead (if needed)**
   - Check current extruder temperature
   - If below minimum for material type, heat and wait
   - Required before filament can enter hot end

3. **Verify Filament at Hub** (if not already there)
   ```python
   if not cur_lane.loaded_to_hub:
       # Load filament to hub first (uses dist_hub distance)
       cur_lane.move_advanced(cur_lane.dist_hub, SpeedMode.HUB)
       cur_lane.loaded_to_hub = True
   ```

4. **Move Past Hub Sensor**
   - Push filament `cur_hub.move_dis` (typically 60mm) past hub sensor
   - Ensures filament fully enters common bowden tube
   - Verify hub sensor triggers (error if not reached after 20 attempts)

5. **Feed Through Bowden Tube**
   ```python
   # Long move through bowden tube from hub to toolhead
   cur_lane.move_advanced(cur_hub.afc_bowden_length, SpeedMode.LONG, assist_active=YES)
   # Distance: afc_bowden_length (e.g., 1750mm)
   # Speed: long_moves_speed (e.g., 150mm/s)
   # Assist: Buffer/tension assist active during this move
   ```

6. **Reach Toolhead Pre-Sensor (pin_tool_start)**
   ```python
   # Keep moving in short increments until tool_start triggers
   while not cur_extruder.tool_start_state:
       cur_lane.move(cur_lane.short_move_dis, cur_extruder.tool_load_speed, accel)
       # Error after excessive attempts (failed to reach sensor)

   # Sensor triggered: filament reached entrance to extruder gears
   ```

7. **Synchronize with Extruder**
   ```python
   cur_lane.sync_to_extruder()
   # AFC lane stepper now synced with toolhead extruder
   # Both motors will move together
   ```

8. **Load Through Extruder Gears (pin_tool_end, if configured)**
   ```python
   if cur_extruder.tool_end:  # Post-extruder sensor exists
       while not cur_extruder.tool_end_state:
           # Move both lane motor AND extruder together
           self.move_e_pos(cur_lane.short_move_dis, cur_extruder.tool_load_speed)
           # Continue until post-extruder sensor triggers

       # Filament successfully passed through extruder gears
   ```

9. **Load to Nozzle Tip**
   ```python
   # Final push: sensor to nozzle tip distance
   self.move_e_pos(cur_extruder.tool_stn, cur_extruder.tool_load_speed)
   # Distance: tool_stn (e.g., 45mm from tool_end sensor to nozzle)
   # Filament now at nozzle tip, ready to print
   ```

10. **Buffer Reset (if using buffer system)**
    ```python
    if cur_extruder.tool_start == "buffer":
        # Retract to reset buffer to neutral position
        while buffer_advance_triggered:
            cur_lane.move(short_move_dis * -1, SpeedMode.SHORT)
        # Buffer now in neutral state
    ```

11. **Final Status Update**
    ```python
    cur_lane.set_loaded()              # Mark lane as loaded
    cur_lane.enable_buffer()           # Enable tension assist/buffer
    cur_lane.unit_obj.lane_tool_loaded(cur_lane)  # Update LED

    # If poop/purge configured, run purge sequence
    ```

#### Key Insights:

- **Toolhead loading is completely separate from lane pre-loading**
- **Two toolhead sensors** (if configured):
  - `pin_tool_start`: Before extruder gears (detects filament arrival)
  - `pin_tool_end`: After extruder gears (confirms successful loading)
- **Synchronization**: Lane motor syncs with extruder during final loading phase
- **Buffer/Tension assist**: Activated after successful toolhead loading
- **Error handling**: Multiple checkpoints with retry logic and user guidance

#### Configuration Parameters:

```ini
[AFC_extruder extruder]
pin_tool_start: ^!<sensor_pin>           # Pre-extruder sensor
pin_tool_end: ^!<sensor_pin>             # Post-extruder sensor (optional)
tool_stn: 45                             # Distance from sensor to nozzle (mm)
tool_load_speed: 10                      # Loading speed (mm/s)
tool_unload_speed: 10                    # Unloading speed (mm/s)

[AFC_hub ACE_HUB_1]
afc_bowden_length: 1750                  # Hub to toolhead distance (mm)
move_dis: 60                             # Movement past hub sensor (mm)
```

---

### Toolhead Unloading Process (Tool Change)

The reverse process when changing tools during print - **selector MOVES to UNLOAD position**:

1. **Disable buffer/tension assist** → stop monitoring tension sensors
2. **Form tip** (if configured) → run tip shaping macro
3. **Retract from nozzle** → retract `tool_stn` distance
   - **Both motors synchronized:** Extruder motor + Lane (Drive) motor
   - Both pull together - no gap for filament to get stuck
4. **Retract through extruder** → use `tool_unload_speed` until sensors clear
   - **Still synchronized** - both motors work together
5. **Additional retraction** (if configured) → `tool_sensor_after_extruder` distance
6. **Unsync from extruder** → lane motor independent again
7. **Move selector to UNLOAD position** → ✅ **CRITICAL for ACE**
   - Selector moves to position 2 (UNLOAD) - e.g., 11.5mm for Lane 1
   - Engages filament with drive gear for active retraction
   - **Prevents filament from hanging loose and tangling**
   - **Actively winds filament onto spool during retraction**
8. **Retract through bowden** → pull back `afc_unload_bowden_length`
   - Lane (Drive) motor retracts through UNLOAD position
   - Filament actively wound onto spool
9. **Retract past hub sensor** → clear hub completely
10. **Retract to buffer zone** → stop 20mm before hub sensor
    - **Filament stays in buffer zone** - ready for quick reload
11. **Selector returns to HOME** → `return_to_home()` called
12. **Update status** → lane unloaded, LED off

**Key Point:**
UNLOAD position is REQUIRED during TOOL_UNLOAD to prevent filament tangling. Without it, retracted filament would hang loose instead of winding onto the spool.

---

### Complete Operation Workflow

**Full workflow from empty spool to multi-color printing:**

```
═══════════════════════════════════════════════════════════════
PREPARATION PHASE (Подготовка к печати)
═══════════════════════════════════════════════════════════════

Lane Pre-loading - Load all spools into hub waiting zone:

Lane 1 Pre-loading:
   ├─ User inserts filament → PREP1 sensor triggers
   ├─ Selector → Lane 1 LOAD position (1.5mm)
   ├─ User pushes, Drive catches filament
   ├─ Feed to hub sensor (dist_hub ~100mm)
   ├─ Selector → UNLOAD position (11.5mm)
   ├─ Retract 20mm (create buffer zone)
   ├─ Selector → final position (LOAD/FREE based on mode)
   └─ Status: Slot #1 in waiting zone (loaded_to_hub = True)

Lane 2 Pre-loading:
   └─ Same process for Slot #2 → waiting zone

Lane 3 Pre-loading:
   └─ Same process for Slot #3 → waiting zone

Lane 4 Pre-loading:
   └─ Same process for Slot #4 → waiting zone

Result: All 4 slots loaded in hub waiting zones, ready for printing

═══════════════════════════════════════════════════════════════
PRINTING PHASE (Печать)
═══════════════════════════════════════════════════════════════

Print Start - Initial Tool Load (T0):
   ├─ Heat toolhead (if needed)
   ├─ Verify Slot #1 at hub waiting zone
   ├─ Push past hub sensor (move_dis)
   ├─ Feed through bowden (afc_bowden_length)
   ├─ Reach tool_start sensor
   ├─ Sync with extruder
   ├─ Load through gears → tool_end sensor
   ├─ Push to nozzle (tool_stn)
   ├─ Enable buffer/tension assist
   └─ Status: Slot #1 in toolhead, printing

During Print - Printing with Slot #1:
   ├─ Tension assist active (if configured)
   ├─ Active mode: feeds on slack detection
   └─ Passive mode: free movement

Tool Change - Switch from Slot #1 to Slot #3 (T2):

  Step 1 - TOOL_UNLOAD(Slot #1):
   ├─ Disable buffer/tension assist
   ├─ Form tip (if configured)
   ├─ Retract from nozzle (Extruder + Lane motors SYNCED)
   ├─ Retract through extruder (STILL SYNCED - both motors work together)
   ├─ Unsync from extruder
   ├─ **Selector → UNLOAD position (11.5mm for Lane 1)** ✅
   ├─ Retract through bowden tube (Lane motor winds onto spool via UNLOAD)
   ├─ Retract past hub sensor
   ├─ Retract to hub waiting zone (20mm before hub)
   ├─ Selector → HOME position
   └─ Status: Slot #1 back in waiting zone, toolhead empty

  Step 2 - TOOL_LOAD(Slot #3):
   ├─ Load from hub waiting zone
   ├─ Push past hub sensor
   ├─ Feed through bowden tube
   ├─ Load into toolhead sensors
   ├─ Sync with extruder
   ├─ Load to nozzle
   ├─ Enable buffer/tension assist
   └─ Status: Slot #3 in toolhead, printing

During Print - Printing with Slot #3:
   └─ Continue printing with new color...

Print End - Unload from toolhead:
   ├─ Unload current slot from toolhead
   ├─ Retract to hub waiting zone
   └─ Status: All slots in waiting zones, toolhead empty

═══════════════════════════════════════════════════════════════
POST-PRINT (Optional) - Full Lane Ejection
═══════════════════════════════════════════════════════════════

Lane Unloading - Remove filaments for spool change:

Command: LANE_UNLOAD LANE=lane1

  Full Lane Ejection Process:
   ├─ **Selector → UNLOAD position (11.5mm for Lane 1)** ✅
   ├─ Retract from buffer zone (20mm before hub)
   ├─ Retract past hub sensor
   ├─ Retract through lane-specific tube
   ├─ Retract until PREP sensor clears (filament fully out)
   ├─ **Drive motor actively pulls filament via UNLOAD position**
   ├─ Selector → HOME position
   └─ Status: Lane empty, ready for new spool

**Key Difference from TOOL_UNLOAD:**
- LANE_UNLOAD = Full ejection from system (uses UNLOAD position)
- TOOL_UNLOAD = Retract to buffer zone only (ALSO uses UNLOAD position)
- **Both use UNLOAD position to wind filament onto spool**
- **Only difference: retraction distance (buffer zone vs full ejection)**
```

---

## Known Issues / TODO

### Not Yet Implemented
- Hub sensor loading logic (hub sensor pin needs definition in config)
- Toolhead sensors (pin_tool_start, pin_tool_end) - user needs to configure in AFC_Hardware-ACE.cfg
- Complete integration of hub sensor with buffer zone retract
- Spool motor control (if using active spool rotation)

### Position 2 (UNLOAD) Active Use ✅
The UNLOAD position is **actively used** in TWO scenarios:

**1. Lane Pre-loading (Buffer Zone Creation):**
- Used during the 20mm retract operation to create buffer zone
- Selector physically moves to UNLOAD position (11.5mm for Lane 1)
- Drive motor retracts filament while selector is in UNLOAD position

**2. Lane Ejection (Full Unload for Spool Change):** ✅ **IMPLEMENTED**
- When `LANE_UNLOAD` is called, selector moves to UNLOAD position
- Drive motor actively retracts filament from buffer zone back through lane tube
- UNLOAD position engages filament with drive gear for active retraction
- This provides better retraction control and reduces motor load
- After unload completes, selector returns to HOME position

**IMPORTANT:** UNLOAD position is used during BOTH operations:
- `TOOL_UNLOAD` (tool change): Uses UNLOAD to wind filament onto spool during retract to buffer zone
- `LANE_UNLOAD` (spool ejection): Uses UNLOAD to wind filament onto spool during full ejection
- **Difference:** Only the retraction distance changes (buffer zone vs full ejection)
- **Critical:** Without UNLOAD position, filament would hang loose and tangle during retraction

### Potential Improvements
1. Add automatic LED blinking during loading (currently just dims)
2. Implement spool motor control for active retraction in UNLOAD position
3. Add tension sensor monitoring logic for predictive runout detection
4. Consider using common tension sensor (TENSION_COMMON) for advanced buffer control
5. Add visual feedback for different loading stages (lane pre-loading vs toolhead loading)

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
1. `extras/AFC_ACE.py` - 396 lines, main implementation with selector positioning **[UPDATED: Added lane_tool_unloading()]**
2. `extras/AFC.py` - 1911 lines, modified to call lane_tool_unloading() during BOTH TOOL_UNLOAD and LANE_UNLOAD **[UPDATED: Added UNLOAD support]**
3. `extras/AFC_ACE_tension.py` - 280 lines, tension assist system
4. `config/mcu/AcePro.cfg` - 38 lines, pinout definitions
5. `templates/AFC_ACE_1.cfg` - 221 lines, complete configuration with tension assist
6. `templates/AFC_Hardware-ACE.cfg` - 95 lines, extruder/buffer template

All files use standard AFC copyright header and GPLv3 license.

### Latest Changes (2025-11-26)
**Feature: Active UNLOAD Position Support for Lane Ejection**
- Added `lane_tool_unloading()` method to AFC_ACE class
- Selector moves to UNLOAD position during `LANE_UNLOAD` (full ejection for spool change)
- Provides active retraction assistance when removing filament from system
- Improved motor efficiency and retraction reliability

**Important Clarification:**
- `TOOL_UNLOAD` (tool change): DOES use UNLOAD position - prevents filament tangling
- `LANE_UNLOAD` (spool ejection): DOES use UNLOAD position - full ejection
- Both operations wind filament onto spool via UNLOAD position
- Difference is only retraction distance (buffer zone vs complete ejection)

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
