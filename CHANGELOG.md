# Changelog

All notable changes to LabPilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.0] - 2026-10-28

### Added

- **File Discovery System**: Updated the file discovery system with improved auto-data loading mechanisms
- **Scripting Support**: Added `ScriptingLoopHandler` class to simplify scripting files
- **Aggregate Tool**: Integrated aggregate tool with multiple options for data aggregation
- **Reader Control**: Added manual start/stop functionality for readers via status clicks in measurement mode
- **Recording Folder Suggestion**: System now suggests the last opened recording folder when selecting a new one
- **Enum Export**: Added support for JSON export of Enum types
- **Folder Naming**: Introduced automatic folder name update for MeasurementProcedures
- **Experiment Parameters Import** Using Ctrl+P / CMD+P in measurement mode, opens an explorer window to ask for a recording folder to load the parameters from an experiment

### Changed

- **PlotBackend**: Fixed issue where plot objects from all plots were incorrectly saved in the same class array (now using instance variables)
- **RecordingManager**: Added flag to deactivate reader data saving while recording MeasurementProcedures
- **Combobox Default Selection**: Fixed issue where combobox couldn't select default value if current value didn't exist
- **Combobox Enhancements**: Extended Combobox capabilities to accommodate Enum types
- **Logger Configuration**: Updated logging to use correct level from config file
- **SCPIInstrument**: Fixed SCPIInstrument class implementation
- **Global State**: Removed Global State recoding information for cleaner architecture
- **Record Button**: Hide the 'Record' button for MeasurementProcedures

### Fixed

- **Analysis Management**: Fixed analysis management in MeasurementProcedure - `self` is now always present in `self.analysis`
- **Reader Management**: Fixed various reader management bugs
- **Thread Saving**: Fixed race condition when saving threads, where the last saved files might not be saved in case of a folder rename
- **Refresh Delay**: Corrected bug that was cancelling the refresh_delay effect

### Improved

- **Simulation mode**: Fix simulation mode to be compatible with the new file saving system
- **Safety Warnings**: Added safety warning for measurement procedures when reading data from a reader not running
- **Unit Tests**: Improve unit tests compatibility for Windows
- **Documentation**: Added more documentation throughout the codebase
- **Typing Hints**: Improved typing hints for DataAnalysis' `@reader` decorator and other locations

### Internal

- Improvements, bug fixes and optimizations

### Removed


---

## [v0.1.0] - 2026-10-19

### Added

- Initial release of LabPilot
- Command line interface for current version and auto-update
- Configurable logging system


---
