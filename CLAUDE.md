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
- **Device Widgets**: Modular widget system supporting both single and multi-device modes with integrated device management
- **Thread-Safe Operation**: All device operations are thread-safe with proper resource management
- **UnifiedWorkerBase**: Standardized threading system with state management and resource cleanup

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
- `data_logger.py`: Data recording and CSV/JSON export functionality
- `enhanced_data_system.py`: Advanced data analytics and export system
- `theme_manager.py`: System theme detection and Qt stylesheet management
- `unified_logger.py`: Centralized logging system with file rotation

**GUI System (`widgets/`):**
- `keithley_widget_professional.py`: Professional Keithley 2461 control with IV curve and sweep measurement capabilities
- `rigol_widget.py`: Multi-device Rigol DP711 widget with automatic port detection and device switching
- `unit_input_widget.py`: Engineering unit input/display widgets with automatic scaling
- `connection_status_widget.py`: Real-time connection status monitoring
- `floating_settings_panel.py`: Modular settings overlay system
- Multi-threaded design using unified worker system for background operations
- Real-time plotting using pyqtgraph with professional styling
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
- Unified worker system with `UnifiedWorkerBase` for standardized threading
- `MeasurementWorker` with strategy pattern supporting continuous and sweep measurements
- `ConnectionWorker` for non-blocking instrument connections
- `PortManager` scans for device changes every 2000ms
- Qt signals/slots used for thread-safe communication
- Proper cleanup on application exit to prevent resource leaks
- Background threads automatically terminate when main window closes
- Worker state management with start/stop/pause capabilities

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
- `requirements.txt`: Pinned dependencies for reproducible environments
- `maintenance_config.py`: System maintenance and database optimization settings
- `src/config/`: Configuration management system with default settings and validation
- System theme detection works automatically across platforms
- Log rotation configured automatically (10MB files, 5 backups)
- Settings stored in local JSON files when needed (.claude/settings.local.json)

## Critical Implementation Notes

### Modern Architecture Features
The codebase has been extensively refactored with a unified architecture system:

**Worker System (`src/workers/`):**
- `UnifiedWorkerBase`: Solves metaclass conflicts, provides standardized threading interface
- `MeasurementWorker`: Strategy pattern supporting continuous measurements and voltage sweeps
- `ConnectionWorker`: Non-blocking connection management with timeout handling
- Worker state management (idle/running/stopping) with proper cleanup

**Data System (`src/data/`):**
- `UnifiedDataManager`: Centralized data handling with multiple storage backends
- `ExportManager`: Multi-format export (CSV, JSON, Excel, Parquet) with metadata
- `StorageBackends`: Pluggable storage system (CSV, JSON, SQLite)
- `BufferManager`: Circular buffer management for real-time data

**Configuration System (`src/config/`):**
- Centralized configuration management with validation
- Default settings with per-device customization
- Environment-specific configuration support

### Code Architecture Decisions
- **Single Responsibility**: Each module has a clear, single purpose
- **Strategy Pattern**: Used in workers for different measurement modes
- **Dependency Injection**: Instruments passed to widgets, not created within them
- **Observer Pattern**: Extensive use of Qt signals for loose coupling
- **Resource Management**: Context managers and proper cleanup in all connection classes
- **Mixin Architecture**: Shared functionality through composable mixins

## Development Notes

### Multi-Device Management
The multi-device system provides:
- Automatic COM port scanning every 2 seconds with smart filtering
- Device identification via SCPI commands (*IDN? queries)
- Active device switching without reconnection
- Graceful handling of device disconnection with automatic cleanup
- Thread-safe device state management using unified worker system
- Support for multiple Rigol DP711 devices simultaneously
- Connection state monitoring with visual feedback

### Widget Architecture
The widget system is built on a modular, professional-grade architecture:
- Professional widgets with advanced measurement capabilities (IV curves, sweeps)
- Multi-device widgets with integrated device management
- Mixin-based architecture for shared functionality (connection, data visualization)
- Unit input/display widgets with engineering notation and automatic scaling
- Floating settings panels for non-intrusive configuration
- All widgets support automatic theme detection and switching
- Connection status widgets with real-time monitoring
- Standardized widget interfaces for easy extension

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
The system includes functional testing capabilities integrated into the main modules. Key testing features:
- Instrument connection validation and communication testing
- SCPI command execution and response parsing verification
- Data logging and export functionality validation
- Real-time error handling and recovery testing

**Testing Notes:**
- Tests require actual hardware or mock instruments for full validation
- Network tests assume Keithley 2461 available at default IP (192.168.0.100)
- Serial tests require available COM ports for Rigol devices
- Use the system's built-in diagnostic features for component testing
- Each widget includes connection testing and validation routines