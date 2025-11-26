# Armored Turtle Automated Filament Changer
#
# Copyright (C) 2024 Armored Turtle
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import traceback
from configparser import Error as error

try: from extras.AFC_utils import add_filament_switch
except: raise error("Error when trying to import AFC_utils.add_filament_switch\n{trace}".format(trace=traceback.format_exc()))

class AFC_ACE_TensionAssist:
    """
    Tension assist system for AFC_ACE. Monitors tension sensors and provides
    filament feeding assistance when tension is detected.

    Two modes of operation:
    - Active: Selector stays in LOAD position, feeds filament when tension detected
    - Passive: Selector in FREE position, filament moves freely without assist
    """

    def __init__(self, config):
        self.printer    = config.get_printer()
        self.afc        = self.printer.lookup_object('AFC')
        self.reactor    = self.afc.reactor
        self.gcode      = self.afc.gcode
        self.logger     = self.afc.logger

        self.name       = config.get_name().split(' ')[-1]
        self.lanes      = {}
        self.enable     = False
        self.current_lane = None

        # Tension assist configuration
        self.assist_mode            = config.get("assist_mode", "passive")  # 'active' or 'passive'
        self.tension_feed_length    = config.getfloat("tension_feed_length", 10.0)  # mm to feed when tension detected
        self.tension_feed_speed     = config.getfloat("tension_feed_speed", 50.0)   # mm/s feed speed
        self.tension_feed_accel     = config.getfloat("tension_feed_accel", 400.0)  # mm/s^2 feed acceleration
        self.hub_retract_distance   = config.getfloat("hub_retract_distance", 20.0) # mm to retract from hub sensor into buffer zone
        self.debug                  = config.getboolean("debug", False)

        # Sensor pin configuration
        self.tension_pin            = config.get('tension_pin')  # Tension sensor pin for this lane

        # Enable sensors in GUI
        self.enable_sensors_in_gui  = config.getboolean("enable_sensors_in_gui", self.afc.enable_sensors_in_gui)

        # Button handler for tension sensor
        self.buttons = self.printer.load_object(config, "buttons")

        # Tension sensor state
        self.tension_state = False
        self.last_assist_time = 0
        self.min_assist_interval = 0.5  # Minimum seconds between assist moves

        # Register tension sensor
        self.tension_filament_switch_name = "{}_tension".format(self.name)
        self.tension_switch = add_filament_switch(
            self.tension_filament_switch_name,
            self.tension_pin,
            self.printer,
            show_sensor=self.enable_sensors_in_gui
        )

        # Register button callback
        self.buttons.register_buttons([self.tension_pin], self.tension_callback)

        # Register G-code commands
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.function = self.printer.load_object(config, 'AFC_functions')

        self.gcode.register_mux_command("ENABLE_TENSION_ASSIST",  "TENSION", self.name, self.cmd_ENABLE_TENSION_ASSIST)
        self.gcode.register_mux_command("DISABLE_TENSION_ASSIST", "TENSION", self.name, self.cmd_DISABLE_TENSION_ASSIST)
        self.gcode.register_mux_command("SET_TENSION_MODE",       "TENSION", self.name, self.cmd_SET_TENSION_MODE)
        self.gcode.register_mux_command("QUERY_TENSION",          "TENSION", self.name, self.cmd_QUERY_TENSION)

        # Register this tension assist in AFC
        # Note: Using afc.buffers dict for compatibility with existing lane.buffer_obj pattern
        self.afc.buffers[self.name] = self

        self.logger.info("AFC_ACE_TensionAssist '{}' initialized in {} mode".format(self.name, self.assist_mode))

    def __str__(self):
        return self.name

    def _handle_ready(self):
        """Handle klippy ready event"""
        self.min_event_systime = self.reactor.monotonic() + 2.

    def tension_callback(self, eventime, state):
        """
        Callback when tension sensor is triggered/untriggered.

        In active mode: triggers filament feeding when tension is detected
        In passive mode: does nothing
        """
        self.tension_state = state

        # Only respond in active mode when printer is ready and printing
        if (self.assist_mode == "active" and
            self.enable and
            self.printer.state_message == 'Printer is ready' and
            self.afc.function.is_printing() and
            not self.afc.function.is_paused() and
            not self.afc.in_toolchange):

            # Check minimum interval between assists
            current_time = self.reactor.monotonic()
            if state and (current_time - self.last_assist_time) >= self.min_assist_interval:
                self.do_tension_assist()
                self.last_assist_time = current_time

                if self.debug:
                    self.logger.debug("{} tension assist triggered at {}".format(self.name, eventime))

    def do_tension_assist(self):
        """
        Perform tension assist move by feeding filament through Drive motor.
        This method should be called when tension is detected in active mode.
        """
        if self.current_lane is None:
            return

        try:
            # Get the ACE unit object to access Drive motor
            unit_obj = self.current_lane.unit_obj

            # Move Drive motor forward to feed filament
            if hasattr(unit_obj, 'drive_stepper_obj') and unit_obj.drive_stepper_obj is not None:
                unit_obj.drive_stepper_obj.move(
                    self.tension_feed_length,
                    self.tension_feed_speed,
                    self.tension_feed_accel,
                    True  # Wait for move to complete
                )

                if self.debug:
                    self.logger.debug("{} fed {}mm due to tension".format(
                        self.name, self.tension_feed_length))
            else:
                self.logger.error("{} cannot perform tension assist: drive_stepper_obj not found".format(self.name))

        except Exception as e:
            self.logger.error("{} error during tension assist: {}".format(self.name, str(e)))

    def enable_buffer(self):
        """
        Enable tension assist. Called when lane is loaded into toolhead.
        Sets selector position based on assist mode.
        """
        self.enable = True

        if self.current_lane is None:
            self.logger.warning("{} enable_buffer called but current_lane is None".format(self.name))
            return

        # Set selector position based on mode
        unit_obj = self.current_lane.unit_obj

        if self.assist_mode == "active":
            # Active mode: keep selector in LOAD position
            if hasattr(unit_obj, 'set_selector_position'):
                unit_obj.set_selector_position(self.current_lane, unit_obj.POSITION_LOAD)
            self.logger.debug("{} enabled in ACTIVE mode (selector in LOAD)".format(self.name))

        else:  # passive mode
            # Passive mode: move selector to FREE position
            if hasattr(unit_obj, 'set_selector_position'):
                unit_obj.set_selector_position(self.current_lane, unit_obj.POSITION_FREE)
            self.logger.debug("{} enabled in PASSIVE mode (selector in FREE)".format(self.name))

    def disable_buffer(self):
        """
        Disable tension assist. Called when lane is unloaded from toolhead.
        """
        self.enable = False
        self.logger.debug("{} tension assist disabled".format(self.name))

    def set_current_lane(self, lane):
        """
        Set the current active lane for this tension assist.
        Should be called when a lane using this tension assist is loaded.
        """
        self.current_lane = lane
        if lane is not None:
            self.lanes[lane.name] = lane

    def buffer_status(self):
        """
        Return current status of tension assist for compatibility with buffer interface.
        """
        if self.enable:
            return "{} mode enabled".format(self.assist_mode.capitalize())
        else:
            return "Disabled"

    # G-code command implementations

    def cmd_ENABLE_TENSION_ASSIST(self, gcmd):
        """
        Enable tension assist for this lane.

        Usage:
        ENABLE_TENSION_ASSIST TENSION=<tension_name>
        """
        self.enable_buffer()
        self.logger.info("{} tension assist enabled".format(self.name))

    def cmd_DISABLE_TENSION_ASSIST(self, gcmd):
        """
        Disable tension assist for this lane.

        Usage:
        DISABLE_TENSION_ASSIST TENSION=<tension_name>
        """
        self.disable_buffer()
        self.logger.info("{} tension assist disabled".format(self.name))

    def cmd_SET_TENSION_MODE(self, gcmd):
        """
        Set tension assist mode (active or passive).

        Usage:
        SET_TENSION_MODE TENSION=<tension_name> MODE=<active|passive>

        Example:
        SET_TENSION_MODE TENSION=ACE_tension1 MODE=active
        """
        mode = gcmd.get('MODE', self.assist_mode).lower()

        if mode not in ['active', 'passive']:
            self.logger.error("Invalid mode '{}'. Must be 'active' or 'passive'".format(mode))
            return

        old_mode = self.assist_mode
        self.assist_mode = mode

        self.logger.info("{} tension assist mode changed from {} to {}".format(
            self.name, old_mode, mode))

        # If currently enabled, update selector position
        if self.enable and self.current_lane is not None:
            unit_obj = self.current_lane.unit_obj
            if self.assist_mode == "active":
                if hasattr(unit_obj, 'set_selector_position'):
                    unit_obj.set_selector_position(self.current_lane, unit_obj.POSITION_LOAD)
            else:
                if hasattr(unit_obj, 'set_selector_position'):
                    unit_obj.set_selector_position(self.current_lane, unit_obj.POSITION_FREE)

    def cmd_QUERY_TENSION(self, gcmd):
        """
        Query current tension assist status.

        Usage:
        QUERY_TENSION TENSION=<tension_name>
        """
        status = "Tension Assist Status for {}:\n".format(self.name)
        status += "  Enabled: {}\n".format(self.enable)
        status += "  Mode: {}\n".format(self.assist_mode)
        status += "  Tension Sensor State: {}\n".format("TRIGGERED" if self.tension_state else "Clear")
        status += "  Feed Length: {}mm\n".format(self.tension_feed_length)
        status += "  Feed Speed: {}mm/s\n".format(self.tension_feed_speed)
        status += "  Current Lane: {}\n".format(self.current_lane.name if self.current_lane else "None")

        self.logger.info(status)

    def get_status(self, eventtime=None):
        """
        Get status for Klipper status reporting.
        """
        return {
            'enabled': self.enable,
            'mode': self.assist_mode,
            'tension_state': self.tension_state,
            'lanes': [lane.name for lane in self.lanes.values()],
        }


def load_config_prefix(config):
    return AFC_ACE_TensionAssist(config)
