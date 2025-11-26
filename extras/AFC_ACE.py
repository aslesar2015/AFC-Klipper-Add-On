# Armored Turtle Automated Filament Changer
#
# Copyright (C) 2024 Armored Turtle
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import traceback

from configparser import Error as error

try: from extras.AFC_utils import ERROR_STR
except: raise error("Error when trying to import AFC_utils.ERROR_STR\n{trace}".format(trace=traceback.format_exc()))

try: from extras.AFC_lane import AFCLaneState
except: raise error(ERROR_STR.format(import_lib="AFC_lane", trace=traceback.format_exc()))

try: from extras.AFC_BoxTurtle import afcBoxTurtle
except: raise error(ERROR_STR.format(import_lib="AFC_BoxTurtle", trace=traceback.format_exc()))

try: from extras.AFC_utils import add_filament_switch
except: raise error(ERROR_STR.format(import_lib="AFC_utils", trace=traceback.format_exc()))

class AFC_ACE(afcBoxTurtle):
    """
    AFC_ACE system implementation

    Features:
    - 2 stepper motors: selector motor and single drive motor
    - 3 positions per lane: LOAD (feed to printer), FREE (neutral), UNLOAD (retract to spool)
    - Single shared drive motor with 4 gears, selector engages filament with gear
    - 4 independent status LEDs (non-Neopixel)
    - Dual sensors per lane: presence sensor (before drive) and tension sensor (after drive)
    - 5 Hall effect tension sensors: 4 per lane + 1 common for maximum tension detection
    """

    # Selector position constants
    POSITION_FREE = 0      # Neutral position - filament can move freely
    POSITION_LOAD = 1      # Load position - filament engaged with drive gear for feeding
    POSITION_UNLOAD = 2    # Unload position - filament engaged for retraction to spool

    def __init__(self, config):
        super().__init__(config)
        self.type                   = config.get('type', 'ACE')
        self.drive_stepper          = config.get("drive_stepper")                                                   # Name of AFC_stepper for shared drive motor
        self.selector_stepper       = config.get("selector_stepper")                                                # Name of AFC_stepper for selector motor
        self.drive_stepper_obj      = None
        self.selector_stepper_obj   = None
        self.current_selected_lane  = None
        self.current_position       = None  # Current selector position (FREE, LOAD, or UNLOAD)
        self.home_state             = False

        # Selector configuration
        self.steps_per_lane         = config.getint("steps_per_lane", 100)                                         # Steps to move between lanes
        self.steps_per_position     = config.getint("steps_per_position", 50)                                      # Steps to move between positions (FREE/LOAD/UNLOAD)
        self.home_pin               = config.get("home_pin")                                                        # Pin for homing sensor
        self.selector_speed         = config.getfloat("selector_speed", 50)                                         # Selector movement speed in mm/s
        self.selector_accel         = config.getfloat("selector_accel", 50)                                         # Selector acceleration in mm/s^2

        # LED configuration (individual LEDs, not Neopixel)
        self.led_pins               = {}                                                                            # Dictionary to store LED pins for each lane

        # Tension sensor configuration (5 Hall sensors: 4 per lane + 1 common)
        self.tension_sensors        = {}                                                                            # Dictionary to store tension sensor pins
        self.tension_common_pin     = config.get("tension_common_pin", None)                                        # Common tension sensor pin
        self.tension_common_state   = False

        self.enable_sensors_in_gui  = config.getboolean("enable_sensors_in_gui", self.afc.enable_sensors_in_gui)    # Set to True to show sensors in GUI
        self.prep_homed             = False
        self.failed_to_home         = False

        # Register home pin button
        buttons = self.printer.load_object(config, "buttons")
        buttons.register_buttons([self.home_pin], self.home_callback)

        if self.home_pin is not None:
            self.home_sensor = add_filament_switch(f"{self.name}_home_pin", self.home_pin, self.printer, self.enable_sensors_in_gui)

        # Register common tension sensor if defined
        if self.tension_common_pin is not None:
            buttons.register_buttons([self.tension_common_pin], self.tension_common_callback)
            self.tension_common_sensor = add_filament_switch(f"{self.name}_tension_common", self.tension_common_pin, self.printer, self.enable_sensors_in_gui)

    def handle_connect(self):
        """
        Handle the connection event.
        This function is called when the printer connects. It looks up AFC info
        and assigns objects for drive and selector steppers.
        """

        try:
            self.drive_stepper_obj = self.printer.lookup_object('AFC_stepper {}'.format(self.drive_stepper))
        except:
            error_string = 'Error: No config found for drive_stepper: {drive_stepper} in [AFC_ACE {stepper}]. Please make sure [AFC_stepper {drive_stepper}] section exists in your config'.format(
                drive_stepper=self.drive_stepper, stepper=self.name)
            raise error(error_string)

        try:
            self.selector_stepper_obj = self.printer.lookup_object('AFC_stepper {}'.format(self.selector_stepper))
        except:
            error_string = 'Error: No config found for selector_stepper: {selector_stepper} in [AFC_ACE {stepper}]. Please make sure [AFC_stepper {selector_stepper}] section exists in your config'.format(
                selector_stepper=self.selector_stepper, stepper=self.name)
            raise error(error_string)

        # Register custom commands
        self.gcode.register_mux_command('HOME_UNIT', "UNIT", self.name, self.cmd_HOME_UNIT)
        self.gcode.register_mux_command('ACE_SET_POSITION', "UNIT", self.name, self.cmd_ACE_SET_POSITION)

        super().handle_connect()

        self.logo = '<span class=success--text>ACE Ready\n</span>'
        self.logo_error = '<span class=error--text>ACE Not Ready</span>\n'

    def system_Test(self, cur_lane, delay, assignTcmd, enable_movement):
        """
        Test system readiness before operations
        """
        cur_lane.prep_state = cur_lane.load_state
        if not self.prep_homed:
            self.return_to_home(prep=True)
        status = super().system_Test(cur_lane, delay, assignTcmd, enable_movement)
        self.return_to_home()

        return self.prep_homed and status

    def home_callback(self, eventtime, state):
        """
        Callback when home switch is triggered/untriggered
        """
        self.home_state = state

    def tension_common_callback(self, eventtime, state):
        """
        Callback when common tension sensor is triggered/untriggered
        """
        self.tension_common_state = state

    def cmd_HOME_UNIT(self, gcmd):
        """
        Moves unit selector back to home position

        Usage
        -----
        `HOME_UNIT UNIT=<unit_name>`

        Example:
        -----
        ```
        HOME_UNIT UNIT=ACE_1
        ```
        """
        self.return_to_home()

    def cmd_ACE_SET_POSITION(self, gcmd):
        """
        Manually set selector position for debugging/testing

        Usage
        -----
        `ACE_SET_POSITION UNIT=<unit_name> LANE=<lane_number> POSITION=<position>`

        POSITION: 0=FREE, 1=LOAD, 2=UNLOAD

        Example:
        -----
        ```
        ACE_SET_POSITION UNIT=ACE_1 LANE=1 POSITION=1
        ```
        """
        lane_num = gcmd.get_int('LANE', minval=1, maxval=4)
        position = gcmd.get_int('POSITION', minval=0, maxval=2)

        # Find lane object
        lane = None
        for l in self.lanes.values():
            if l.index == lane_num:
                lane = l
                break

        if lane is None:
            gcmd.respond_info(f"Lane {lane_num} not found")
            return

        self.move_to_position(lane, position)
        gcmd.respond_info(f"Moved to lane {lane_num}, position {position}")

    def return_to_home(self, prep=False):
        """
        Moves selector to home position

        :param prep: Set to True if this function is being called within prep function
        :return boolean: Returns True if homing was successful
        """
        total_moved = 0

        # If we know current position, do a fast move back first
        if self.current_selected_lane is not None and not self.home_state and not prep:
            estimated_distance = self.calculate_selector_movement(self.current_selected_lane.index, self.POSITION_FREE)
            self.selector_stepper_obj.move(estimated_distance * -1, self.selector_speed, self.selector_accel, False)

        # Then do slow moves until home sensor triggers
        while not self.home_state and not self.failed_to_home:
            self.selector_stepper_obj.move(-1, 20, 20, False)
            total_moved += 1
            if total_moved > (self.steps_per_lane * 4 + self.steps_per_position * 2):
                self.failed_to_home = True
                self.afc.error.AFC_error("Failed to home {}".format(self.name), False)
                return False

        self.prep_homed = True
        self.selector_stepper_obj.do_enable(False)
        self.current_selected_lane = None
        self.current_position = None
        return True

    def calculate_selector_movement(self, lane_index, position):
        """
        Calculates movement in mm to reach specified lane and position

        :param lane_index: Lane index (1-4)
        :param position: Target position (FREE=0, LOAD=1, UNLOAD=2)
        :return float: Return movement in mm to move selector
        """
        # Calculate lane offset (each lane is steps_per_lane apart)
        lane_offset = (lane_index - 1) * self.steps_per_lane

        # Calculate position offset within lane
        # FREE = 0, LOAD = +steps_per_position, UNLOAD = -steps_per_position
        if position == self.POSITION_FREE:
            position_offset = 0
        elif position == self.POSITION_LOAD:
            position_offset = self.steps_per_position
        elif position == self.POSITION_UNLOAD:
            position_offset = -self.steps_per_position
        else:
            position_offset = 0

        total_movement = lane_offset + position_offset
        self.logger.debug(f"ACE: Selector movement to lane {lane_index} position {position}: {total_movement} steps")
        return total_movement

    def move_to_position(self, lane, position):
        """
        Moves selector to specified lane and position

        :param lane: Lane object to move selector to
        :param position: Target position (FREE=0, LOAD=1, UNLOAD=2)
        :return boolean: Returns True if movement succeeded
        """
        self.failed_to_home = False

        # Always home first if we're not sure of position
        if self.current_selected_lane != lane or self.current_position is None:
            self.logger.debug(f"ACE: {self.name} Homing to endstop.")
            if not self.return_to_home():
                return False

        # Calculate and execute movement
        movement = self.calculate_selector_movement(lane.index, position)
        self.selector_stepper_obj.move(movement, self.selector_speed, self.selector_accel, False)
        self.logger.debug(f"ACE: {lane} position {position} selected")

        self.current_selected_lane = lane
        self.current_position = position
        return True

    def select_lane(self, lane):
        """
        Moves selector to specified lane in LOAD position

        :param lane: Lane object to move selector to
        :return boolean: Returns True if movement of selector succeeded
        """
        return self.move_to_position(lane, self.POSITION_LOAD)

    def check_runout(self, cur_lane):
        """
        Function to check if runout logic should be triggered

        :return boolean: Returns true if current lane is loaded and printer is printing
        """
        return cur_lane.name == self.afc.function.get_current_lane() and self.afc.function.is_printing() and cur_lane.status != AFCLaneState.EJECTING and cur_lane.status != AFCLaneState.CALIBRATING

    def lane_loaded(self, lane):
        """
        Set lane LED when filament is loaded (uses individual LED control)

        :param lane: Lane object to set LED
        """
        # Individual LED control - turn on LED for loaded lane
        self.set_individual_led(lane.index, True)

    def lane_unloaded(self, lane):
        """
        Set lane LED when filament is unloaded (uses individual LED control)

        :param lane: Lane object to set LED
        """
        # Individual LED control - turn off LED for unloaded lane
        self.set_individual_led(lane.index, False)

    def lane_loading(self, lane):
        """
        Set lane LED when filament is loading (blink or dim)

        :param lane: Lane object to set LED
        """
        # Set LED to dim state during loading
        self.set_individual_led(lane.index, True, brightness=0.3)

    def set_individual_led(self, lane_index, state, brightness=1.0):
        """
        Set individual LED state (on/off) for a specific lane

        :param lane_index: Lane number (1-4)
        :param state: True for on, False for off
        :param brightness: LED brightness level (0.0-1.0)
        """
        # Use Klipper's LED control for individual white LEDs
        try:
            led_name = f'led LED_lane{lane_index}'
            led_obj = self.printer.lookup_object(led_name)
            if state:
                # Turn on LED with specified brightness
                led_obj.set_color(self.printer.lookup_object('toolhead').get_last_move_time(),
                                 red=0.0, green=0.0, blue=0.0, white=brightness)
            else:
                # Turn off LED
                led_obj.set_color(self.printer.lookup_object('toolhead').get_last_move_time(),
                                 red=0.0, green=0.0, blue=0.0, white=0.0)
        except Exception as e:
            self.logger.debug(f"Could not control LED for lane {lane_index}: {e}")

def load_config_prefix(config):
    return AFC_ACE(config)
