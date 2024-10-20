import sys
import numpy as np
import pyvisa
import matplotlib
from typing import Tuple
matplotlib.use('Qt5Agg')  # Use the Qt5Agg backend for PyQt5
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout,
    QLabel, QLineEdit, QMessageBox, QHBoxLayout, QComboBox, QDoubleSpinBox
)
from PyQt5.QtWidgets import QColorDialog


class Oscilloscope:
    """
    A class to represent and interface with an oscilloscope using pyvisa.
    """

    def __init__(self, resource_name: str):
        """
        Initialize the oscilloscope with the given resource name.

        :param resource_name: The VISA resource name of the oscilloscope.
        """
        self.resource_name: str = resource_name
        self.rm: pyvisa.ResourceManager = pyvisa.ResourceManager()
        self.inst: pyvisa.resources.MessageBasedResource = None

    def connect(self) -> None:
        """
        Connect to the oscilloscope.
        """
        self.inst = self.rm.open_resource(self.resource_name)
        idn = self.inst.query('*IDN?')
        print(f"Connected to {idn}")

    def disconnect(self) -> None:
        """
        Disconnect from the oscilloscope.
        """
        if self.inst is not None:
            self.inst.close()
            self.inst = None
            print("Disconnected from oscilloscope.")

    def set_channel(self, channel: int) -> None:
        """
        Set the active channel.

        :param channel: The oscilloscope channel to set.
        """
        self.inst.write(f":WAV:SOUR CHAN{channel}")

    def set_timebase(self, time_per_div: float) -> None:
        """
        Set the timebase (seconds per division).

        :param time_per_div: Time per division in seconds.
        """
        self.inst.write(f":TIM:SCAL {time_per_div}")

    def set_voltage_scale(self, channel: int, volts_per_div: float) -> None:
        """
        Set the voltage scale (volts per division) for a channel.

        :param channel: The channel to set.
        :param volts_per_div: Volts per division.
        """
        self.inst.write(f":CHAN{channel}:SCAL {volts_per_div}")

    def set_trigger(self, mode: str, source: int, slope: str, level: float) -> None:
        """
        Set the trigger settings.

        :param mode: Trigger mode (e.g., 'EDGE').
        :param source: Trigger source channel.
        :param slope: Trigger slope ('POS' or 'NEG').
        :param level: Trigger level in volts.
        """
        self.inst.write(f":TRIG:MODE {mode}")
        self.inst.write(f":TRIG:EDGE:SOUR CHAN{source}")
        self.inst.write(f":TRIG:EDGE:SLOP {slope}")
        self.inst.write(f":TRIG:LEV CHAN{source},{level}")  
    
    def get_waveform(self, channel: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retrieve waveform data from the oscilloscope.

        :param channel: The channel to retrieve data from.
        :return: Tuple of numpy arrays (time, voltage).
        """
        if self.inst is None:
            raise Exception("Oscilloscope not connected.")

        # Set the waveform source to the specified channel
        self.inst.write(f":WAV:SOUR CHAN{channel}")

        # Correct command to set data format
        self.inst.write(":WAV:FORM BYTE")  # Use 'FORM', not 'FORMAT'
        self.inst.write(":WAV:MODE NORMAL")

        # Verify data format
        actual_format = self.inst.query(":WAV:FORM?")
        print(f"Data format set to: {actual_format.strip()}")

        # Read preamble block
        preamble = self.inst.query(":WAV:PRE?")
        preamble_fields = preamble.strip().split(',')

        print("Preamble Fields:", preamble_fields)

        (
            format_code, type_code, points, count, x_increment, x_origin, x_reference,
            y_increment, y_origin, y_reference
        ) = preamble_fields[:10]

        # Convert string values to appropriate data types
        x_increment = float(x_increment)
        x_origin = float(x_origin)
        x_reference = int(float(x_reference))
        y_increment = float(y_increment)
        y_origin = float(y_origin)
        y_reference = int(float(y_reference))

        print(f"x_increment: {x_increment}, x_origin: {x_origin}, x_reference: {x_reference}")
        print(f"y_increment: {y_increment}, y_origin: {y_origin}, y_reference: {y_reference}")

        # Read waveform data using unsigned bytes
        data = self.inst.query_binary_values(':WAV:DATA?', datatype='B', container=np.array)

        print("Raw data sample:", data[:10])  # Print first 10 data points

        # Get vertical scale and offset from the oscilloscope
        vertical_scale = float(self.inst.query(f":CHAN{channel}:SCAL?"))
        probe_attenuation = float(self.inst.query(f":CHAN{channel}:PROB?"))
        print(f"Vertical scale: {vertical_scale}, Probe attenuation: {probe_attenuation}")

        # Adjust vertical scale for probe attenuation
        adjusted_vertical_scale = vertical_scale / probe_attenuation

        # Convert data to voltage values using the correct formula
        voltage = ((data - 130.0) / 25.0) * adjusted_vertical_scale

        print("Voltage sample:", voltage[:10])  # Print first 10 voltage points

        # Generate time array
        time = (np.arange(len(data)) - x_reference) * x_increment + x_origin

        print("Waveform data retrieved and processed.")
        return time, voltage



class MplCanvas(FigureCanvas):
    """
    Matplotlib Canvas to embed in PyQt5 application.
    """

    def __init__(self):

        # Set figure background color
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor='#fafafa')
        self.axes = self.fig.add_subplot(111)

        # Set axes background color
        self.axes.set_facecolor('#000000')

        # Add grid lines
        self.axes.grid(True, which='major', linestyle='-', linewidth=0.75, color='gray')

        # Display minor ticks on the Axes.
        self.axes.minorticks_on()

        # Configure the grid lines.
        self.axes.grid(True, which='minor', linestyle=':', linewidth=0.45, color='lightgray')

        # Set a title for the Axes.
        self.axes.set_title("Oscilloscope Waveform", fontsize=14, fontweight='normal')

        # Set the label for the x-axis.
        self.axes.set_xlabel("Time (s)", fontsize=12)

        # Set the label for the y-axis.
        self.axes.set_ylabel("Voltage (V)", fontsize=12)
        
        # Adjust tick parameters
        self.axes.tick_params(axis='both', which='major', labelsize=10)

        super().__init__(self.fig)
        


class MainWindow(QMainWindow):
    """
    The main window of the application.
    """

    def __init__(self):
        super().__init__()
        
        self.oscilloscope: Oscilloscope = None
        self.time: np.ndarray = None
        self.voltage: np.ndarray = None
        self.waveform_color = 'yellow'  # Default color

        self._setup_ui()    

    def _setup_ui(self) -> None:
        """
        Set up the user interface components.
        """
        # Resource name input
        self.resource_label = QLabel("Resource Name:")
        self.resource_input = QLineEdit("USB0::0x1AB1::0x0517::DS1ZE242906834::INSTR")
        self.resource_input.setFixedWidth(350)

        # Channel selection
        self.channel_label = QLabel("Channel:")
        self.channel_select = QComboBox()
        self.channel_select.setFixedWidth(100)
        self.channel_select.addItems(["1", "2", "3", "4"])

        # Timebase setting
        self.timebase_label = QLabel("Timebase (s/div):")
        self.timebase_input = QDoubleSpinBox()
        self.timebase_input.setFixedWidth(100)
        self.timebase_input.setRange(1e-9, 10)
        self.timebase_input.setDecimals(9)
        self.timebase_input.setSingleStep(1e-6)
        self.timebase_input.setValue(200e-6)

        # Voltage scale setting
        self.voltage_label = QLabel("Voltage Scale (V/div):")
        self.voltage_input = QDoubleSpinBox()
        self.voltage_input.setFixedWidth(100)
        self.voltage_input.setRange(1e-3, 100)
        self.voltage_input.setDecimals(3)
        self.voltage_input.setSingleStep(0.1)
        self.voltage_input.setValue(1.0)

        # Trigger mode
        self.trigger_mode_label = QLabel("Trigger Mode:")
        self.trigger_mode_select = QComboBox()
        self.trigger_mode_select.setFixedWidth(100)
        self.trigger_mode_select.addItems(["EDGE", "PULSE", "VIDEO"])

        # Trigger source
        self.trigger_source_label = QLabel("Trigger Source:")
        self.trigger_source_select = QComboBox()
        self.trigger_source_select.setFixedWidth(100)
        self.trigger_source_select.addItems(["1", "2", "3", "4"])

        # Trigger slope
        self.trigger_slope_label = QLabel("Trigger Slope:")
        self.trigger_slope_select = QComboBox()
        self.trigger_slope_select.setFixedWidth(100)
        self.trigger_slope_select.addItems(["Positive", "Negative"])

        # Trigger level
        self.trigger_level_label = QLabel("Trigger Level (V):")
        self.trigger_level_input = QDoubleSpinBox()
        self.trigger_level_input.setFixedWidth(100)
        self.trigger_level_input.setRange(-100, 100)
        self.trigger_level_input.setDecimals(3)
        self.trigger_level_input.setSingleStep(0.1)
        self.trigger_level_input.setValue(1.5)

        # oscilloscope settings layout
        osc_setting_layout = QVBoxLayout()
        osc_setting_layout.addWidget(self.channel_label)
        osc_setting_layout.addWidget(self.channel_select)
        osc_setting_layout.addWidget(self.timebase_label)
        osc_setting_layout.addWidget(self.timebase_input)
        osc_setting_layout.addWidget(self.voltage_label)
        osc_setting_layout.addWidget(self.voltage_input)
        osc_setting_layout.addWidget(self.trigger_mode_label)
        osc_setting_layout.addWidget(self.trigger_mode_select)
        osc_setting_layout.addWidget(self.trigger_source_label)
        osc_setting_layout.addWidget(self.trigger_source_select)
        osc_setting_layout.addWidget(self.trigger_slope_label)
        osc_setting_layout.addWidget(self.trigger_slope_select)
        osc_setting_layout.addWidget(self.trigger_level_label)
        osc_setting_layout.addWidget(self.trigger_level_input)
        osc_setting_layout.addStretch(1)

        # Buttons
        self.connect_button = QPushButton("Connect")
        self.connect_button.setFixedWidth(100)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setFixedWidth(100)
        self.disconnect_button.setDisabled(True)

        self.apply_settings_button = QPushButton("Apply Settings")
        self.apply_settings_button.setFixedWidth(100)
        self.apply_settings_button.setDisabled(True)

        self.get_data_button = QPushButton("Get Waveform")
        self.get_data_button.setFixedWidth(100)
        self.get_data_button.setDisabled(True)

        self.color_button = QPushButton("Select Color")
        self.color_button.clicked.connect(self.select_waveform_color) 
        self.color_button.setDisabled(True)       

        # buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.addSpacing(20)
        buttons_layout.addWidget(self.connect_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.disconnect_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.apply_settings_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.get_data_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.color_button)
        buttons_layout.addSpacing(20)

        self.status_label = QLabel("Status: Disconnected")

        # Matplotlib Figure Canvas
        self.canvas = MplCanvas()

        canvas_layout = QHBoxLayout()
        canvas_layout.addLayout(osc_setting_layout)
        canvas_layout.addWidget(self.canvas)

        # Layout for control widgets
        control_layout = QVBoxLayout()
        control_layout.addWidget(self.resource_label)
        control_layout.addWidget(self.resource_input)
        control_layout.addLayout(canvas_layout)
        control_layout.addLayout(buttons_layout)
        control_layout.addWidget(self.status_label)
        
        # Set up the windows settings
        container = QWidget()
        container.setLayout(control_layout)
        self.setCentralWidget(container)
        self.setMinimumSize(900, 500)
        self.setWindowTitle("Oscilloscope Interface")

        # Signal Connections
        self.connect_button.clicked.connect(self.connect_oscilloscope)
        self.disconnect_button.clicked.connect(self.disconnect_oscilloscope)
        self.apply_settings_button.clicked.connect(self.apply_settings)
        self.get_data_button.clicked.connect(self.get_waveform)

        self.timebase_input.valueChanged.connect(self.apply_settings)
        self.voltage_input.valueChanged.connect(self.apply_settings)
        self.trigger_level_input.valueChanged.connect(self.apply_settings)

    def connect_oscilloscope(self) -> None:
        """
        Connect to the oscilloscope using the resource name from the input field.
        """
        resource_name = self.resource_input.text()
        
        try:
            self.oscilloscope = Oscilloscope(resource_name)
            self.oscilloscope.connect()
            self.status_label.setText(f"Status: Connected to {resource_name}")

            self.disconnect_button.setEnabled(True)
            self.apply_settings_button.setEnabled(True)
            self.get_data_button.setEnabled(True)
            self.color_button.setEnabled(True)  

            self.apply_settings()

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def disconnect_oscilloscope(self) -> None:
        """
        Disconnect from the oscilloscope.
        """
        if self.oscilloscope:
            self.oscilloscope.disconnect()
            self.oscilloscope = None
            self.status_label.setText("Status: Disconnected")

    def apply_settings(self) -> None:
        """
        Apply the oscilloscope settings from the GUI inputs.
        """
        if not self.oscilloscope:
            QMessageBox.warning(self, "Warning", "Oscilloscope not connected.")
            return

        try:
            channel = int(self.channel_select.currentText())
            timebase = self.timebase_input.value()
            voltage_scale = self.voltage_input.value()
            trigger_mode = self.trigger_mode_select.currentText()
            trigger_source = int(self.trigger_source_select.currentText())
            trigger_slope = self.trigger_slope_select.currentText().upper()
            if trigger_slope == "POSITIVE":
                trigger_slope = "POS"
            else:
                trigger_slope = "NEG"
            trigger_level = self.trigger_level_input.value()

            # Apply settings
            self.oscilloscope.set_channel(channel)
            self.oscilloscope.set_timebase(timebase)
            self.oscilloscope.set_voltage_scale(channel, voltage_scale)
            self.oscilloscope.set_trigger(trigger_mode, trigger_source, 
                                          trigger_slope, trigger_level)

            # QMessageBox.information(self, "Settings Applied", 
            #                         "Oscilloscope settings have been applied.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def get_waveform(self) -> None:
        """
        Get the waveform data from the oscilloscope and plot it.
        """
        if not self.oscilloscope:
            QMessageBox.warning(self, "Warning", "Oscilloscope not connected.")
            return

        try:
            channel = int(self.channel_select.currentText())
            self.time, self.voltage = self.oscilloscope.get_waveform(channel)
            self.plot_waveform(self.time, self.voltage)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def plot_waveform(self, time: np.ndarray, voltage: np.ndarray) -> None:
        """
        Plot the waveform data on the matplotlib canvas.

        :param time: The time data as a numpy array.
        :param voltage: The voltage data as a numpy array.
        """
        # Clear the Axes.
        self.canvas.axes.clear()
        
        # Plot the waveform with a custom color and line width
        self.canvas.axes.plot(time, voltage, color=self.waveform_color, linewidth=1.0)

        # Set a title for the Axes.
        self.canvas.axes.set_title("Oscilloscope Waveform", fontsize=14, fontweight='normal')

        # Set the label for the x-axis.
        self.canvas.axes.set_xlabel("Time (s)", fontsize=12)

        self.canvas.axes.minorticks_on()
        # 
        self.canvas.axes.set_ylabel("Voltage (V)", fontsize=12)
        
        # Configure and add the major grid lines.
        self.canvas.axes.grid(True, which='major', linestyle='-', linewidth=0.75, color='gray')
        
        # Display minor ticks on the Axes.
        # Displaying minor ticks may reduce performance; you may turn them off using minorticks_off() 
        # if drawing speed is a problem.
        self.canvas.axes.minorticks_on()

        # Configure and add the minor grid lines.
        self.canvas.axes.grid(True, which='minor', linestyle=':', linewidth=0.45, color='lightgray')

        # Adjust tick parameters. Change the appearance of ticks, tick labels, and gridlines.
        self.canvas.axes.tick_params(axis='both', which='major', labelsize=10)

        # Set tight layout to fit labels
        self.canvas.fig.tight_layout()

        # Render the .Figure.
        self.canvas.draw()
        print("Waveform plotted.")

    def select_waveform_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.waveform_color = color.name()
            print(f"Selected waveform color: {self.waveform_color}")
            # Plot the waveform with a custom color 
            self.plot_waveform(self.time, self.voltage)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
