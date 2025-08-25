# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based multi-instrument control system for laboratory equipment, supporting Keithley 2461 SourceMeter and Rigol DP711 Power Supply with unified tabbed GUI interface. The system provides both GUI and programmatic interfaces for controlling these instruments via SCPI commands, with advanced features like automatic device detection, multi-device management, and real-time data visualization.

**Key Features:**
- Multi-instrument tabbed GUI with automatic system theme detection
- Real-time data plotting and logging with CSV/JSON export
- Automatic COM port scanning and device identification
- Support for multiple Rigol DP711 devices simultaneously
- Thread-safe measurement workers for continuous data acquisition

## Essential Commands

### Setup and Dependencies
```bash
# Install dependencies
pip install -r requirements.txt

# Main multi-instrument GUI (recommended entry point)
python main.py

# Single Keithley GUI (legacy)
python gui_main.py

# Run tests
python test_keithley.py

# Quick system test (import verification)
python -c "from gui_multi_instrument import main; print('✅ System ready')"
```

### Development Commands
The system uses PyQt6 for GUI and requires PyVISA for Keithley and PySerial for Rigol. The main application automatically checks for missing dependencies and provides helpful error messages.

**Key Dependencies:**
- PyQt6 6.5.2: GUI framework
- PyVISA 1.13.0: Keithley instrument communication
- PySerial 3.5: Rigol serial communication
- pyqtgraph 0.13.3: Real-time plotting
- numpy, pandas, scipy: Data processing

## Architecture Overview

### Core Design Pattern
The codebase follows an object-oriented design with abstract base classes for instrument control:

- **InstrumentBase**: Abstract base class defining common instrument interface
- **PowerSupplyBase**: Extends InstrumentBase for power supply specific functionality  
- **SourceMeterBase**: Extends PowerSupplyBase for source meter capabilities
- **InstrumentManager**: Manages multiple instruments in a unified interface

### Multi-Device Architecture
The system supports multiple devices of the same type simultaneously:

- **PortManager**: Automatic COM port detection and device identification via SCPI *IDN? queries
- **MultiDeviceManager**: Manages multiple Rigol DP711 devices with active device switching
- **Device Widgets**: Modular widget system supporting both single and multi-device modes
- **Thread-Safe Operation**: All device operations are thread-safe with proper resource management

### Key Components

**Entry Points:**
- `main.py`: Primary GUI application entry point, launches multi-instrument interface
- `gui_main.py`: Legacy single Keithley GUI (still functional)
- `gui_multi_instrument.py`: Multi-instrument tabbed interface for Keithley 2461 and Rigol DP711

**Instrument Control (`src/`):**
- `instrument_base.py`: Abstract base classes defining instrument interfaces
- `keithley_2461.py`: Keithley 2461 SourceMeter implementation (TCP/IP via SCPI)
- `rigol_dp711.py`: Rigol DP711 Power Supply implementation (RS232 via SCPI)  
- `port_manager.py`: Automatic COM port scanning and device identification
- `multi_device_manager.py`: Multi-device management with active device switching
- `data_logger.py`: Data recording and CSV/JSON export functionality
- `theme_manager.py`: System theme detection and Qt stylesheet management

**GUI System (`widgets/`):**
- `keithley_widget.py`: Complete Keithley 2461 control widget with measurement threading
- `rigol_widget.py`: Multi-device Rigol DP711 widget with automatic port detection and device switching
- Multi-threaded design with `MeasurementWorker` for background data acquisition
- Real-time plotting using pyqtgraph
- Automatic system theme detection (dark/light mode)
- Comprehensive logging system with colored output and file rotation

### Instrument Communication
- **Keithley 2461**: TCP/IP connection on port 5025, supports both PyVISA and raw socket
  - Default connection method: PyVISA (recommended)
  - Fallback to raw socket if PyVISA unavailable
  - Standard SCPI command set with instrument-specific extensions
- **Rigol DP711**: RS232 serial connection (COM ports), supports multiple simultaneous devices
  - Automatic port detection and device identification via SCPI *IDN? command
  - Smart port filtering to avoid conflicts with already connected devices
  - Default baudrate: 9600, configurable in widget
  - Requires female-female cable despite male connector on device
- All instruments use SCPI command protocol with consistent error handling and timeout management

### Data Management
- Sessions-based data logging with automatic timestamping
- Export formats: CSV and JSON
- Real-time data visualization with configurable point limits (default 1000 points)
- Automatic log file rotation (10MB files, 5 backups retained)

### Theme System
The GUI automatically detects and applies system themes:
- **Detection**: Works across macOS, Windows, and Linux
- **Application**: Single detection at startup (no runtime switching to avoid UI issues)
- **Fallback**: Uses Qt palette detection if OS-specific methods fail

## Important Implementation Details

### GUI Threading Model
- Main UI thread handles interface updates
- `MeasurementWorker` thread runs continuous measurements at 1000ms intervals (1Hz)
- `PortManager` scans for device changes every 2000ms
- Qt signals/slots used for thread-safe communication
- Proper cleanup on application exit to prevent resource leaks
- Background threads automatically terminate when main window closes

### Error Handling Strategy
- Comprehensive exception handling at instrument communication level
- GUI displays user-friendly error messages while logging technical details
- Automatic resource cleanup using context managers where possible
- Graceful degradation when instruments are disconnected

### SCPI Command Implementation
Both instrument classes follow consistent patterns:
- Connection validation before command execution
- Command/query methods with timeout handling
- Automatic device initialization on connection
- Standard SCPI compliance with instrument-specific extensions

## File Structure Context

### Documentation Directories
- `2461/`: Contains Keithley 2461 official manuals and datasheets
- `711/`: Contains Rigol DP711 SCPI command reference and documentation
- `logs/`: Runtime log files with daily rotation
- `data/`: Default location for exported measurement data

### Configuration Files
- `requirements.txt`: Pinned dependencies for reproducible environments (~5,200 lines of code)
- System theme detection works without additional configuration files
- No external config files required - all settings managed in code
- Log rotation configured automatically (10MB files, 5 backups)

## Critical Implementation Notes

### Code Architecture Decisions
- **Single Responsibility**: Each module has a clear, single purpose
- **Dependency Injection**: Instruments passed to widgets, not created within them
- **Observer Pattern**: Extensive use of Qt signals for loose coupling
- **Resource Management**: Context managers and proper cleanup in all connection classes

## Development Notes

### Multi-Device Management
The new multi-device system (primarily for Rigol DP711) provides:
- Automatic COM port scanning every 2 seconds
- Device identification via SCPI commands
- Active device switching without reconnection
- Graceful handling of device disconnection
- Thread-safe device state management

### Widget Architecture
The widget system supports both single and multi-device modes:
- Single device widgets (legacy): Direct instrument control
- Multi-device widgets: Use device manager for coordination
- All widgets support theme switching and provide backward compatibility methods

### Multi-Instrument Support
The architecture supports multiple instruments simultaneously:
- `InstrumentManager` for different instrument types (Keithley + Rigol)
- `MultiDeviceManager` for multiple devices of same type (multiple DP711s)
- Tabbed interface allows easy switching between instrument types

### GUI Customization
The theme system provides comprehensive styling for both light and dark modes. Custom styles should be added to `ThemeStyleSheet` class methods rather than inline CSS.

### Data Export
The `DataLogger` supports both real-time data streaming and batch export. Session management allows for organized data collection with metadata preservation.

### Port Management
The `PortManager` class provides:
- Real-time port monitoring with change detection
- Device identification using SCPI *IDN? queries
- Smart filtering of available vs. connected ports
- Cross-platform COM port enumeration
- Automatic cleanup of disconnected devices
- Thread-safe port access with locking mechanisms

### Testing Approach
The system includes functional tests in `test_keithley.py` that verify:
- Instrument connection and communication
- SCPI command execution and response parsing
- Data logging and export functionality
- Error handling and recovery mechanisms

**Testing Notes:**
- Tests require actual hardware or mock instruments
- Network tests assume Keithley 2461 available at default IP
- Serial tests require available COM ports for Rigol devices
- Use `python test_keithley.py` to run full test suite