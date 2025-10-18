# Auto Slicer Plugin for Cura

**Version:** 1.8.1  
**Author:** HellAholic  
**Compatible with:** Cura 5.10.0+

## Overview

The Auto Slicer Plugin is a powerful Cura extension that automates the batch processing of 3D model files. It allows you to slice multiple STL and 3MF files with different quality profiles, automatically saving the output files with timestamps and comprehensive logging.

## Key Features

- 🚀 **Batch Processing**: Process multiple files with different quality profiles in one operation
- 📁 **Multiple Format Support**: STL and 3MF files supported
- 🎯 **Individual Profile Assignment**: Assign different quality profiles to each file
- ⚡ **Smart Timeout Management**: Configurable timeout (30-3600 seconds) with automatic skip on timeout
- 🔍 **Real-Time Validation**: Material-variant compatibility checking with visual indicators
- 📊 **Progress Tracking**: Real-time progress updates and detailed logging
- 💾 **Automatic File Management**: Organized output with timestamp naming convention
- 📝 **CSV Logging**: Complete processing history with detailed error reporting

## Quick Start

1. **Configure Folders**: Set your source folder (containing STL/3MF files) and destination folder
2. **Select Files**: Click "Select Files to Process..." to choose specific files and assign quality profiles
3. **Check Printer Status**: Verify your printer configuration shows green (valid) status
4. **Start Processing**: Click "Start Auto Slicing" and monitor progress in real-time

## User Interface Guide

### 📁 Configuration Section

#### Source Folder
- **Purpose**: Select the folder containing your 3D model files
- **Supported Formats**: 
  - **STL files (.stl)**: Standard triangle mesh format
  - **3MF files (.3mf)**: Microsoft 3D Manufacturing Format with embedded settings
- **Important Notes**:
  - Files must be directly in the selected folder (not in subfolders)
  - Large files (>100MB) may take longer to process
  - Ensure files are not corrupted or locked by other applications

#### Destination Folder
- **Purpose**: Where sliced output files will be saved
- **Output Formats**: 
  - **UFP files**: Ultimaker Format Package (for Ultimaker printers)
  - **G-code files**: Uncompressed G-code format (for most other printers)
- **File Naming**: `[OriginalName]_[YYYYMMDD_HH_MM].[extension]`
- **Example**: "dragon.stl" becomes "dragon_20250801_14_30.ufp"

#### Max Files to Process
- **Settings**: 0 (no limit) to 1000 files
- **Recommendations**:
  - **First-time users**: Start with 2-3 files
  - **Large batches**: Consider system resources and available time
  - **Testing profiles**: Use 1-2 files when trying new settings

#### Slice Timeout (30-3600 seconds)
- **Default**: 300 seconds (5 minutes)
- **Behavior**: Files taking longer than this time are automatically skipped
- **Recommended Settings**:
  - **Small/simple models**: 60-180 seconds
  - **Medium complexity**: 300-600 seconds
  - **Large/complex models**: 900-1800 seconds
  - **Very complex models**: 1800-3600 seconds (maximum)

### 📋 File Selection Section

#### Advanced File Selection Dialog
- **File Table**: Individual file selection with checkboxes
- **Quality Profile Assignment**: Assign specific profiles to each file
- **Quick Actions**:
  - **Select All/None**: Bulk selection controls
  - **Update Profiles**: Refresh quality profiles from current Cura settings

#### Quality Profile Features
- **Profile Organization**: Grouped by Intent Category (Visual, Engineering, Quick)
- **Profile Types**:
  - **Machine Profiles**: Built-in Cura profiles
  - **User-Defined Profiles (*)**: Custom profiles marked with asterisk
- **Smart Features**:
  - Automatic suggestion of currently active profile
  - Remembers previous selections
  - Compatibility filtering based on current nozzle and material

### 🖨️ Printer Information Section

#### Real-Time Status Monitoring
- **Printer Name**: Currently selected printer model
- **Extruder Information**: Position, nozzle size, material, and status for each extruder
- **Status Indicators**:
  - 🟢 **Green**: Valid configuration
  - 🟡 **Yellow**: Warning - compatibility issues
  - 🟠 **Orange**: Disabled or inactive
  - 🔴 **Red**: Error condition requiring attention

#### Material-Variant Compatibility Validation
- **Real-Time Monitoring**: Updates automatically when changing materials/variants
- **Cura Integration**: Uses Cura's built-in validation system
- **Visual Indicators**:
  - ⚠️ **Warning Icon**: Compatibility warnings
  - ❌ **Error Icon**: Critical configuration errors
- **Detailed Tooltips**: Hover for specific compatibility issues

### 🎮 Control Section

#### Start Auto Slicing
**Processing Pipeline (per file)**:
1. Quality Profile Switch
2. Build Plate Clear
3. Model Loading
4. Positioning (auto-arrange or UCP for 3MF)
5. Slicing with current profile settings
6. Output Save with timestamp
7. File Management (move original to "sliced" subfolder)
8. CSV Logging

#### Skip Current File
- Skip the currently processing file and continue with next
- Useful for files taking unusually long or having issues
- File marked as "skipped" in log, remains in source folder

#### Stop Processing
- Immediately halt entire batch operation
- Completes current file if possible
- Restores original Cura settings
- Provides final processing summary

### 📊 Progress & Logging

#### Progress Tracking
- **Progress Bar**: Visual completion percentage
- **Status Messages**: Real-time processing updates
- **Common Statuses**: "Ready", "Discovering files...", "Processing [filename]", etc.

#### Processing Log
- **Real-Time Information**: Start/stop notifications, file status, success/error messages
- **Features**: Auto-scroll, color coding (errors in red), clear logs button
- **Error Types**: File loading failures, slicing errors, disk space issues, timeouts

## Output Files

### Generated Files
- **Sliced Files**: `[name]_[timestamp].[format]` - Ready for printing
- **CSV Log**: `auto_slicer_progress.csv` - Complete processing record

### CSV Log Contents
- **filename**: Original file name
- **source_path**: Full path to original file
- **ufp_path**: Full path to output file
- **status**: "completed", "failed", or "skipped"
- **timestamp**: When processing occurred
- **error_message**: Details for failed files

### File Organization After Processing

**Source Folder Structure:**
```
Source Folder/
├── remaining_unprocessed_files.stl
└── sliced/ (automatically created)
    ├── successfully_processed_file1.stl
    └── successfully_processed_file2.3mf
```

**Destination Folder Structure:**
```
Destination Folder/
├── file1_20250801_14_30.ufp
├── file2_20250801_14_35.gcode
└── auto_slicer_progress.csv
```

## Best Practices & Tips

### Getting Started
- ✅ **Start Small**: Test with 2-3 files before large batches
- ✅ **Test Profiles**: Verify quality settings work with sample files
- ✅ **Check Validation**: Ensure green (valid) status before starting
- ✅ **Resolve Warnings**: Address yellow indicators for optimal results
- ✅ **Check Disk Space**: Ensure adequate storage before large batches
- ✅ **Backup Originals**: Keep copies of important files elsewhere

### Validation Best Practices
- 👀 **Monitor Status**: Watch for validation icons (⚠️ ❌)
- 🔴 **Fix Errors First**: Resolve red indicators before batch processing
- 🟡 **Investigate Warnings**: May work but could affect print quality
- 💡 **Use Tooltips**: Hover over validation icons for details
- 🔄 **Real-Time Updates**: Status updates when changing materials

### Optimization Tips
- 🖥️ **Close Unnecessary Apps**: Free up system resources
- 📁 **Use Consistent File Types**: Avoid mixing formats
- 👁️ **Monitor First Few Files**: Catch issues early
- 📊 **Organize by Complexity**: Group similar models for better timeout estimates

### Performance Considerations
- 💾 **Memory Usage**: Large models require more RAM
- 🔥 **CPU Load**: Slicing is CPU-intensive
- 💿 **Disk I/O**: Use fast storage for source and destination
- ⚖️ **Batch Size**: Balance efficiency with system stability

## Troubleshooting

### Common Issues & Solutions

#### File Processing Errors
- **"Failed to load model file"**: Check file corruption, format support, access permissions
- **"Failed to slice model"**: Verify geometry validity, memory availability, settings compatibility
- **"Failed to save output file"**: Check disk space, permissions, destination folder access
- **"Slicing timeout"**: Increase timeout value for complex models

#### Validation Issues
- **"Material not supported"**: Switch to compatible material or different variant
- **"Variant not supported"**: Use different nozzle variant or update material
- **"Material incompatible"**: Check Cura's material-variant compatibility matrix
- **Persistent errors**: Restart Cura to refresh validation state

#### General Troubleshooting
- 📋 **Check Error Logs**: Review detailed error information
- 📊 **Review CSV File**: Complete processing history with timestamps
- ✅ **Verify File Integrity**: Ensure source files aren't corrupted
- 🧪 **Test Individual Files**: Process problematic files manually first
- 🔄 **Refresh Profiles**: Use "Update Profiles" button after changing settings
- 🔍 **Validation Issues**: Check printer information section for warnings

## System Requirements

- **Cura Version**: 5.10.0 or later
- **Supported SDK**: 8.9.0
- **Operating System**: Windows, macOS, Linux (wherever Cura runs)
- **Disk Space**: At least 100MB free in destination folder
- **Memory**: Adequate RAM for large model processing

## Support

For issues, feature requests, or contributions:
- **GitHub**: [AutoSlicerPlugin Repository](https://github.com/HellAholic/AutoSlicerPlugin)
- **Issues**: Please report bugs with detailed logs and system information

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

**Key points about AGPL-3.0:**
- ✅ **Free to use**: Use the plugin for any purpose
- ✅ **Modify and distribute**: Make changes and share them
- ✅ **Open source requirement**: Any modifications must also be open source
- ⚠️ **Network copyleft**: If you use modified versions on a server, you must provide source code to users

For the complete license text, see the [LICENSE](LICENSE) file in this repository or visit <https://www.gnu.org/licenses/agpl-3.0.html>.
