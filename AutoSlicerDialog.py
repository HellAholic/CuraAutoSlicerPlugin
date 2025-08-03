# Auto Slicer Plugin for Cura
# Copyright (C) 2025 HellAholic
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QTextEdit, QProgressBar,
                             QFileDialog, QSpinBox, QGroupBox, QGridLayout,
                             QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
                             QSizePolicy, QWidget)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont

from UM.Logger import Logger
from .PluginConstants import PluginConstants
from .AutoSlicerController import AutoSlicerController


class ProfileComboBox(QComboBox):
    """Custom combo box that shows profile name with category when closed, but clean names in dropdown."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_texts = {}  # Store original item texts
        
        # Connect to selection change to update display text
        self.currentIndexChanged.connect(self._onSelectionChanged)
        
    def showPopup(self):
        """When opening dropdown, restore original item texts."""
        # Restore original texts for dropdown display
        for index, original_text in self._original_texts.items():
            if index < self.count():
                super().setItemText(index, original_text)
        super().showPopup()
        
    def hidePopup(self):
        """When closing dropdown, update selected item text to include category."""
        super().hidePopup()
        self._updateSelectedItemDisplay()
        
    def _onSelectionChanged(self, index):
        """Handle selection change to update display text."""
        if index >= 0:
            self._updateSelectedItemDisplay()
        
    def setItemText(self, index, text):
        """Override to store original text."""
        self._original_texts[index] = text
        super().setItemText(index, text)
        
    def addItem(self, text, userData=None):
        """Override to store original text."""
        index = self.count()
        self._original_texts[index] = text
        super().addItem(text, userData)
        
    def _updateSelectedItemDisplay(self):
        """Update the selected item to show profile name with category."""
        try:
            current_index = self.currentIndex()
            if current_index >= 0:
                profile_data = self.itemData(current_index)
                if profile_data and isinstance(profile_data, dict):
                    quality_name = profile_data.get('quality_name', '')
                    intent_display = profile_data.get('intent_display', '')
                    is_user_defined = profile_data.get('is_user_defined', False)
                    
                    # Create the display text with category for the closed state
                    if is_user_defined:
                        display_with_category = f"* {quality_name} - {intent_display}"
                    else:
                        display_with_category = f"{quality_name} - {intent_display}"
                    
                    # Temporarily disconnect signal to avoid recursion
                    self.currentIndexChanged.disconnect(self._onSelectionChanged)
                    
                    # Update only the selected item display (what shows when closed)
                    super().setItemText(current_index, display_with_category)
                    
                    # Force the combo box to update its display
                    self.update()
                    self.repaint()
                    
                    # Reconnect signal
                    self.currentIndexChanged.connect(self._onSelectionChanged)
                    
        except Exception as e:
            Logger.log("w", f"Error updating combo box display: {e}")


class FileSelectionDialog(QDialog):
    """Child dialog for selecting files and their quality profiles."""
    
    def __init__(self, parent=None, source_folder="", max_files=10, quality_profiles=None, previous_selections=None, controller=None):
        super().__init__(parent)
        self.setWindowTitle("Select Files to Process")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)
        
        # Apply dialog background styling
        self.setStyleSheet(PluginConstants.DIALOG_BACKGROUND_STYLE)
        
        self._source_folder = source_folder
        self._max_files = max_files
        self._quality_profiles = quality_profiles or []
        self._selected_files = []
        self._previous_selections = previous_selections or []
        self._controller = controller
        
        # Connect to controller signals if available
        if self._controller:
            self._controller.qualityProfilesLoaded.connect(self._onQualityProfilesLoaded)
        
        self._setupUI()
        self._populateFileTable()
        
    def _setupUI(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Info label
        info_label = QLabel(f"Select files from: {self._source_folder}")
        info_label.setStyleSheet(PluginConstants.LABEL_STYLE)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # File List Section
        file_list_group = QGroupBox("Files Available for Processing")
        file_list_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        file_list_layout = QVBoxLayout()
        
        self._file_table = QTableWidget()
        self._file_table.setColumnCount(2)
        self._file_table.setHorizontalHeaderLabels(["File Name", "Quality Profile"])
        
        # Set uniform row height for better combo box alignment
        self._file_table.verticalHeader().setDefaultSectionSize(40)
        self._file_table.verticalHeader().setVisible(False)
        
        # Set 50-50 column width split
        header = self._file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # Apply table styling from constants
        self._file_table.setStyleSheet(PluginConstants.TABLE_WIDGET_STYLE)
        
        file_list_layout.addWidget(self._file_table)
        file_list_group.setLayout(file_list_layout)
        layout.addWidget(file_list_group)
        
        # Button section
        button_layout = QHBoxLayout()
        
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setStyleSheet(PluginConstants.BROWSE_BUTTON_STYLE)
        self._select_all_btn.clicked.connect(self._selectAllFiles)
        button_layout.addWidget(self._select_all_btn)
        
        self._select_none_btn = QPushButton("Select None")
        self._select_none_btn.setStyleSheet(PluginConstants.BROWSE_BUTTON_STYLE)
        self._select_none_btn.clicked.connect(self._selectNoFiles)
        button_layout.addWidget(self._select_none_btn)
        
        # Add Update Profiles button
        self._update_profiles_btn = QPushButton("Update Profiles")
        self._update_profiles_btn.setStyleSheet(PluginConstants.BROWSE_BUTTON_STYLE)
        self._update_profiles_btn.clicked.connect(self._updateQualityProfiles)
        self._update_profiles_btn.setToolTip("Refresh quality profiles from current Cura settings")
        button_layout.addWidget(self._update_profiles_btn)
        
        button_layout.addStretch()
        
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setStyleSheet(PluginConstants.START_BUTTON_STYLE)
        self._ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self._ok_btn)
        
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(PluginConstants.CLOSE_BUTTON_STYLE)
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _populateFileTable(self):
        """Populate the file table with files from the source folder."""
        self._file_table.setRowCount(0)

        if not os.path.isdir(self._source_folder):
            return

        # Get files from controller
        files = self._controller.getFilesFromFolder(self._source_folder, self._max_files) if self._controller else []

        self._file_table.setRowCount(len(files))

        # Get current machine info from controller
        machine_info = self._controller.getCurrentMachineInfo() if self._controller else {}
        current_quality_id = machine_info.get('current_quality_id')
        current_quality_changes_id = machine_info.get('current_quality_changes_id')
        current_intent_category = machine_info.get('current_intent_category')
        current_quality_name = machine_info.get('current_quality_name')
        current_quality_changes_name = machine_info.get('current_quality_changes_name')
        has_active_quality_changes = machine_info.get('has_active_quality_changes', False)

        for row, filename in enumerate(files):
            file_item = QTableWidgetItem(filename)
            file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            file_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._file_table.setItem(row, 0, file_item)

            combo_box = ProfileComboBox()
            combo_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo_box.setMinimumHeight(30)
            combo_box.setMaximumHeight(36)
            combo_box.setStyleSheet(PluginConstants.COMBOBOX_STYLE)
            
            # Check if this file has previous selections
            previous_selection = None
            file_was_previously_selected = False
            for prev_file in self._previous_selections:
                if prev_file.get("file") == filename:
                    previous_selection = prev_file
                    file_was_previously_selected = True
                    break
            
            current_profile_index = -1
            if not self._quality_profiles:
                combo_box.addItem("No profiles available")
                combo_box.setEnabled(False)
            else:
                intent_groups = {}
                for profile_entry in self._quality_profiles:
                    intent = profile_entry['intent']
                    intent_display = self._controller.normalizeIntentName(intent) if self._controller else intent.title()
                    if intent_display not in intent_groups:
                        intent_groups[intent_display] = []
                    intent_groups[intent_display].append(profile_entry)
                
                item_index = 0
                for intent_display in sorted(intent_groups.keys()):
                    profiles = intent_groups[intent_display]
                    
                    header_text = f"── {intent_display} ──"
                    combo_box.addItem(header_text)
                    model = combo_box.model()
                    header_item = model.item(item_index)
                    header_item.setEnabled(False)
                    header_item.setData("header", Qt.ItemDataRole.UserRole + 1)
                    item_index += 1
                    
                    for profile_entry in sorted(profiles, key=lambda p: p['quality_name']):
                        quality_name = profile_entry['quality_name']
                        container = profile_entry['container']
                        
                        if not container:
                            continue
                        
                        # Build display text with profile name only (category shown in headers)
                        quality_name = profile_entry['quality_name']
                        
                        # Create base display text without category (category is in section headers)
                        if profile_entry.get('is_user_defined', False):
                            display_text = f"  * {quality_name}"
                        else:
                            display_text = f"  {quality_name}"
                        
                        try:
                            container_id = container.getId()
                            profile_data = {
                                'container_id': container_id,
                                'intent_category': profile_entry['intent'],
                                'intent_container_id': profile_entry['intent_container'].getId() if profile_entry.get('intent_container') else None,
                                'quality_name': quality_name,
                                'intent_display': intent_display,
                                'quality_type': profile_entry.get('quality_type'),
                                'is_user_defined': profile_entry.get('is_user_defined', False)
                            }
                            combo_box.addItem(display_text, profile_data)
                            
                            # Priority 1: Check for previous selection match
                            if current_profile_index == -1 and previous_selection:
                                prev_profile_id = previous_selection.get('profile_id')
                                prev_intent_category = previous_selection.get('intent_category')
                                
                                # Match by profile ID and intent
                                if (prev_profile_id and container_id == prev_profile_id and 
                                    prev_intent_category and profile_entry['intent'] == prev_intent_category):
                                    current_profile_index = item_index
                            
                            # Priority 2: Enhanced matching logic for current active profile (only if no previous selection)
                            elif current_profile_index == -1 and not previous_selection:
                                profile_matches = False
                                
                                # Method 1: If we have an active quality_changes (user-defined profile), prioritize exact match
                                if has_active_quality_changes and profile_entry.get('is_user_defined', False):
                                    # For user-defined profiles, match by exact container ID and intent
                                    if (current_quality_changes_id and container_id == current_quality_changes_id):
                                        # Check intent compatibility if available
                                        if current_intent_category is not None:
                                            normalized_current_intent = self._controller.normalizeIntentName(current_intent_category) if self._controller else current_intent_category
                                            if intent_display == normalized_current_intent:
                                                profile_matches = True
                                        else:
                                            # No intent information available, just match on profile ID
                                            profile_matches = True
                                
                                # Method 2: If no quality_changes match found, or no active quality_changes, try base quality match
                                if not profile_matches and not profile_entry.get('is_user_defined', False):
                                    # For machine profiles, only match if no quality_changes is active, or if this profile matches the base quality
                                    if not has_active_quality_changes:
                                        # No quality_changes active, match base quality profile
                                        if current_quality_id and container_id == current_quality_id:
                                            if current_intent_category is not None:
                                                normalized_current_intent = self._controller.normalizeIntentName(current_intent_category) if self._controller else current_intent_category
                                                if intent_display == normalized_current_intent:
                                                    profile_matches = True
                                            else:
                                                profile_matches = True
                                
                                # Method 3: Fallback name match (only if no ID matches found)
                                if not profile_matches and current_quality_name and current_intent_category:
                                    normalized_current_intent = self._controller.normalizeIntentName(current_intent_category) if self._controller else current_intent_category
                                    
                                    # For user-defined profiles, try to match the quality_changes name
                                    if has_active_quality_changes and profile_entry.get('is_user_defined', False):
                                        if (current_quality_changes_name and 
                                            quality_name.lower() == current_quality_changes_name.lower() and 
                                            intent_display == normalized_current_intent):
                                            profile_matches = True
                                    
                                    # For machine profiles, try to match the base quality name (only if no quality_changes active)
                                    elif not has_active_quality_changes and not profile_entry.get('is_user_defined', False):
                                        if (quality_name.lower() == current_quality_name.lower() and 
                                            intent_display == normalized_current_intent):
                                            profile_matches = True
                                
                                if profile_matches:
                                    current_profile_index = item_index
                                
                        except:
                            combo_box.addItem(display_text, None)
                        
                        item_index += 1
                
                if current_profile_index == -1:
                    # Fallback: Find first enabled item
                    for i in range(combo_box.count()):
                        model = combo_box.model()
                        item = model.item(i)
                        if item and item.isEnabled():
                            current_profile_index = i
                            break
                
                if current_profile_index >= 0:
                    combo_box.setCurrentIndex(current_profile_index)
                    # Trigger initial display update for the custom combo box
                    combo_box._updateSelectedItemDisplay()
                else:
                    Logger.log("i", f"No matching profile found for {filename}, using fallback")

            # Set checkbox state based on previous selection
            # If no previous selection exists, default to checked for new files
            if self._previous_selections:  # If we have previous selections
                if file_was_previously_selected:
                    file_item.setCheckState(Qt.CheckState.Checked)  # File was selected before
                else:
                    file_item.setCheckState(Qt.CheckState.Unchecked)  # File was not selected before
            else:
                file_item.setCheckState(Qt.CheckState.Checked)  # Default for first time
            
            # Set the combo box directly in the table cell (no container widget needed)
            self._file_table.setCellWidget(row, 1, combo_box)
    
    def _selectAllFiles(self):
        """Select all files in the table."""
        for row in range(self._file_table.rowCount()):
            item = self._file_table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
    
    def _selectNoFiles(self):
        """Deselect all files in the table."""
        for row in range(self._file_table.rowCount()):
            item = self._file_table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
    
    def _updateQualityProfiles(self):
        """Update quality profiles from current Cura settings and refresh the table."""
        if not self._controller:
            Logger.log("w", "No controller available for updating quality profiles")
            return
        
        # Temporarily disable the button to prevent multiple clicks
        self._update_profiles_btn.setEnabled(False)
        self._update_profiles_btn.setText("Updating...")
        
        try:
            # Save current file selections before updating
            current_selections = self.getSelectedFiles()
            
            # Trigger quality profiles reload through controller
            Logger.log("i", "Updating quality profiles - this may take a moment...")
            self._controller._loadQualityProfilesAsync()
            
            # Give the async operation a moment to complete, then update
            QTimer.singleShot(500, lambda: self._finishProfileUpdate(current_selections))
            
        except Exception as e:
            Logger.logException("e", f"Error updating quality profiles: {str(e)}")
            # Re-enable the button on error
            self._update_profiles_btn.setEnabled(True)
            self._update_profiles_btn.setText("Update Profiles")
    
    def _finishProfileUpdate(self, previous_selections):
        """Complete the profile update process."""
        try:
            # Get updated profiles from controller
            self._quality_profiles = self._controller.getQualityProfiles()
            
            # Repopulate the table with updated profiles
            self._populateFileTable()
            
            # Restore previous selections if possible
            self._restoreFileSelections(previous_selections)
            
            Logger.log("i", f"Updated quality profiles - found {len(self._quality_profiles)} profiles")
            
        except Exception as e:
            Logger.logException("e", f"Error finishing profile update: {str(e)}")
        finally:
            # Re-enable the button
            self._update_profiles_btn.setEnabled(True)
            self._update_profiles_btn.setText("Update Profiles")
    
    def _restoreFileSelections(self, previous_selections):
        """Restore file selections after profile update."""
        if not previous_selections:
            return
        
        try:
            # Create a lookup map of previous selections
            selection_map = {sel["file"]: sel for sel in previous_selections}
            
            # Restore selections in the updated table
            for row in range(self._file_table.rowCount()):
                file_item = self._file_table.item(row, 0)
                if file_item:
                    filename = file_item.text()
                    if filename in selection_map:
                        # Restore checkbox state
                        file_item.setCheckState(Qt.CheckState.Checked)
                        
                        # Try to restore profile selection
                        combo_box = self._file_table.cellWidget(row, 1)
                        if combo_box and isinstance(combo_box, QComboBox):
                            previous_profile = selection_map[filename]
                            prev_profile_id = previous_profile.get('profile_id')
                            prev_intent_category = previous_profile.get('intent_category')
                            
                            # Find matching profile in updated list
                            for i in range(combo_box.count()):
                                profile_data = combo_box.itemData(i)
                                if profile_data and isinstance(profile_data, dict):
                                    if (profile_data.get('container_id') == prev_profile_id and 
                                        profile_data.get('intent_category') == prev_intent_category):
                                        combo_box.setCurrentIndex(i)
                                        # Update display for custom combo box
                                        if hasattr(combo_box, '_updateSelectedItemDisplay'):
                                            combo_box._updateSelectedItemDisplay()
                                        break
                    else:
                        # File wasn't previously selected, uncheck it
                        file_item.setCheckState(Qt.CheckState.Unchecked)
            
        except Exception as e:
            Logger.logException("e", f"Error restoring file selections: {str(e)}")
    
    def _onQualityProfilesLoaded(self, profiles):
        """Handle quality profiles loaded signal from controller."""
        self._quality_profiles = profiles
    
    def getSelectedFiles(self):
        """Get the list of selected files with their quality profiles."""
        selected_files = []
        for row in range(self._file_table.rowCount()):
            file_item = self._file_table.item(row, 0)
            if file_item and file_item.checkState() == Qt.CheckState.Checked:
                filename = file_item.text()
                combo_box = self._file_table.cellWidget(row, 1)
                profile_id = None
                intent_category = None
                intent_container_id = None
                
                if combo_box and isinstance(combo_box, QComboBox) and combo_box.isEnabled():
                    current_index = combo_box.currentIndex()
                    if current_index >= 0:
                        model = combo_box.model()
                        item = model.item(current_index)
                        if item and item.isEnabled():
                            profile_data = combo_box.currentData()
                            
                            if profile_data and isinstance(profile_data, dict):
                                profile_id = profile_data.get('container_id')
                                intent_category = profile_data.get('intent_category')
                                intent_container_id = profile_data.get('intent_container_id')
                                # Add quality type and user-defined flag for proper profile switching
                                quality_type = profile_data.get('quality_type')
                                is_user_defined = profile_data.get('is_user_defined', False)
                            else:
                                profile_id = profile_data
                                # Look up additional metadata from quality profiles
                                for profile_entry in self._quality_profiles:
                                    if profile_entry['container'] and profile_entry['container'].getId() == profile_id:
                                        intent_category = profile_entry['intent']
                                        quality_type = profile_entry.get('quality_type')
                                        is_user_defined = profile_entry.get('is_user_defined', False)
                                        if 'intent_container' in profile_entry and profile_entry['intent_container']:
                                            intent_container_id = profile_entry['intent_container'].getId()
                                        break
                
                selected_files.append({
                    "file": filename, 
                    "profile_id": profile_id,
                    "intent_category": intent_category,
                    "intent_container_id": intent_container_id,
                    "quality_type": quality_type if 'quality_type' in locals() else None,
                    "is_user_defined": is_user_defined if 'is_user_defined' in locals() else False
                })
        return selected_files


class HelpDialog(QDialog):
    """Help dialog with explanations for each section of the Auto Slicer plugin."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto Slicer Help")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        
        # Apply dialog background styling
        self.setStyleSheet(PluginConstants.DIALOG_BACKGROUND_STYLE)
        
        self._setupUI()
    
    def _setupUI(self):
        """Set up the help dialog UI."""
        layout = QVBoxLayout()
        
        # Help content
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setStyleSheet(PluginConstants.AUTO_SLICER_LOG_STYLE)
        
        help_content = """
        <h1 style="color: #2196F3; text-align: center; margin-bottom: 20px;">Auto Slicer Plugin - User Guide</h1>
        
        <h2 style="color: #4CAF50;">📁 Configuration Section</h2>
        
        <h3 style="color: #FFC107;">Source Folder</h3>
        <p><b>Purpose:</b> Select the folder containing your 3D model files that you want to batch process.</p>
        <p><b>Supported Formats:</b></p>
        <ul>
        <li><b>STL files (.stl):</b> Standard triangle mesh format, commonly used for 3D printing</li>
        <li><b>3MF files (.3mf):</b> Microsoft 3D Manufacturing Format with embedded print settings</li>
        </ul>
        <p><b>Important Notes:</b></p>
        <ul>
        <li>The plugin scans the folder and displays only compatible files</li>
        <li>Files must be directly in the selected folder (not in subfolders)</li>
        <li>Large files (>100MB) may take longer to load and process</li>
        <li>Ensure files are not corrupted or locked by other applications</li>
        </ul>

        <h3 style="color: #FFC107;">Destination Folder</h3>
        <p><b>Purpose:</b> Choose where the sliced output files will be saved after processing.</p>
        <p><b>Output Format:</b> The plugin automatically uses your machine's preferred format:</p>
        <ul>
        <li><b>.ufp files:</b> Ultimaker Format Package (for Ultimaker printers that support UFP file format)</li>
        <li><b>.gcode files:</b> Uncompressed G-code format (for most other printers). For consistency, the plugin prefers this format over the compressed G-code (.gcode.gz).</li>
        <li><b>Other formats:</b> Based on your printer's configuration</li>
        </ul>
        <p><b>File Naming Convention:</b> [OriginalName]_[YYYYMMDD_HH_MM].[extension]</p>
        <p><b>Example:</b> "dragon.stl" becomes "dragon_20250801_14_30.ufp"</p>
        <p><b>Requirements:</b></p>
        <ul>
        <li>Folder must have write permissions</li>
        <li>Sufficient disk space</li>
        <li>Path should not contain special characters that might cause issues</li>
        </ul>

        <h3 style="color: #FFC107;">Max Files to Process</h3>
        <p><b>Purpose:</b> Limit the number of files processed in a single batch operation.</p>
        <p><b>Settings:</b></p>
        <ul>
        <li><b>0:</b> No limit - process all selected files</li>
        <li><b>1-1000:</b> Process up to this many files from your selection</li>
        </ul>
        <p><b>Recommendations:</b></p>
        <ul>
        <li><b>First time users:</b> Start with 2-3 files to test the workflow</li>
        <li><b>Large batches:</b> Consider system resources and available time</li>
        <li><b>Testing profiles:</b> Use 1-2 files when trying new quality settings</li>
        </ul>

        <h3 style="color: #FFC107;">Slice Timeout (30-3600 seconds)</h3>
        <p><b>Purpose:</b> Maximum time to wait for each individual model to complete slicing.</p>
        <p><b>Default:</b> 300 seconds (5 minutes)</p>
        <p><b>Timeout Behavior:</b></p>
        <ul>
        <li>If a model takes longer than this time, it's automatically skipped</li>
        <li>Processing continues with the next file in the queue</li>
        <li>Skipped files are logged with timeout reason</li>
        </ul>
        <p><b>Recommended Settings:</b></p>
        <ul>
        <li><b>Small/simple models:</b> 60-180 seconds</li>
        <li><b>Medium complexity:</b> 300-600 seconds (default range)</li>
        <li><b>Large/complex models:</b> 900-1800 seconds</li>
        <li><b>Very complex models:</b> 1800-3600 seconds (maximum)</li>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">

        <h2 style="color: #4CAF50;">📋 File Selection Section</h2>
        
        <h3 style="color: #FFC107;">Selection Process</h3>
        <p>Click <b>"Select Files to Process..."</b> to open the advanced file selection dialog.</p>
        
        <h3 style="color: #FFC107;">File Selection Dialog Features</h3>
        <p><b>File Table:</b></p>
        <ul>
        <li><b>Checkboxes:</b> Select/deselect individual files for processing</li>
        <li><b>File Names:</b> Shows all compatible files found in source folder</li>
        <li><b>Quality Profile Dropdown:</b> Assign specific profiles to each file</li>
        </ul>
        
        <p><b>Quick Selection Buttons:</b></p>
        <ul>
        <li><b>"Select All":</b> Check all files in the list</li>
        <li><b>"Select None":</b> Uncheck all files</li>
        <li><b>"Update Profiles":</b> Refresh quality profiles from current Cura settings (useful when printer or material settings change or when adding new profiles)</li>
        </ul>

        <h3 style="color: #FFC107;">Quality Profile Assignment</h3>
        <p><b>Profile Organization:</b> Profiles are grouped by Intent Category (if applicable):</p>
        <ul>
        <li><b>── Visual ──</b> Profiles optimized for appearance and surface quality</li>
        <li><b>── Engineering ──</b> Profiles optimized for strength and dimensional accuracy</li>
        <li><b>── Quick ──</b> Fast printing profiles with acceptable quality</li>
        <li><b>── Other Categories ──</b> Additional intent-based groupings</li>
        </ul>
        
        <p><b>Profile Types:</b></p>
        <ul>
        <li><b>Machine Profiles:</b> Built-in profiles provided by Cura</li>
        <li><b>User-Defined Profiles (*):</b> Custom profiles you've created, marked with asterisk. Only profiles compatible with your current nozzle and material combination are shown.</li>
        </ul>
        
        <p><b>Smart Profile Matching:</b></p>
        <ul>
        <li>Plugin automatically suggests your currently active profile</li>
        <li>Remembers previous selections when reopening the dialog</li>
        <li>Matches by profile ID and intent category for accuracy</li>
        </ul>

        <h3 style="color: #FFC107;">Advanced Profile Features</h3>
        <p><b>Individual File Customization:</b></p>
        <ul>
        <li>Each file can use a different quality profile</li>
        <li>Mix different layer heights in the same batch</li>
        <li>Combine different infill densities and print speeds</li>
        <li>Use different intents (Visual for detailed parts, Engineering for functional parts)</li>
        </ul>
        
        <p><b>Smart Compatibility Filtering:</b></p>
        <ul>
        <li>Custom profiles are automatically filtered based on your current nozzle and material setup</li>
        <li>Only profiles that are compatible with your current configuration are shown</li>
        <li>Prevents confusion from seeing incompatible custom profiles in the list</li>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">

        <h2 style="color: #4CAF50;">🖨️ Printer Information Section</h2>
        
        <h3 style="color: #FFC107;">Real-Time Printer Status</h3>
        <p><b>Printer Name:</b> Displays your currently selected printer model from Cura</p>
        
        <h3 style="color: #FFC107;">Extruder Information</h3>
        <p><b>For each extruder, the plugin displays:</b></p>
        <ul>
        <li><b>Extruder Position:</b> Extruder 0, Extruder 1, etc.</li>
        <li><b>Nozzle Information:</b> Size and variant name</li>
        <li><b>Material:</b> Currently loaded material type</li>
        <li><b>Status Indicators:</b></li>
        <ul>
        <li><span style="color: #4CAF50; font-weight: bold;">Green:</span> Active and enabled extruder with valid configuration</li>
        <li><span style="color: #FFC107; font-weight: bold;">Yellow:</span> Warning - compatibility issues detected</li>
        <li><span style="color: #FFA500; font-weight: bold;">Orange:</span> Disabled or inactive extruder</li>
        <li><span style="color: #f44336; font-weight: bold;">Red:</span> Error condition or incompatible configuration</li>
        </ul>
        <li><b>Validation Icons:</b></li>
        <ul>
        <li><b>⚠️ Warning Icon:</b> Material-variant compatibility warnings</li>
        <li><b>❌ Error Icon:</b> Critical configuration errors that must be resolved</li>
        </ul>
        </ul>
        
        <h3 style="color: #FFC107;">Material-Variant Compatibility Validation</h3>
        <p><b>The plugin now integrates with Cura's built-in validation system to provide real-time compatibility checking:</b></p>
        <ul>
        <li><b>Real-Time Monitoring:</b> Validation status updates automatically when you change materials or variants</li>
        <li><b>Cura Integration:</b> Uses the same validation logic that Cura uses internally</li>
        <li><b>Detailed Tooltips:</b> Hover over validation icons to see specific compatibility issues</li>
        <li><b>Status Messages:</b> Detailed descriptions of validation problems in the status text</li>
        </ul>
        
        <h3 style="color: #FFC107;">Understanding Validation Status</h3>
        <p><b>Validation indicators help you identify issues before batch processing:</b></p>
        <ul>
        <li><b>"Valid" (Green):</b> Material and variant are fully compatible</li>
        <li><b>"Warning" (Yellow):</b> Configuration may work but has compatibility concerns</li>
        <li><b>"Error" (Red):</b> Incompatible configuration that should be fixed</li>
        </ul>
        
        <h3 style="color: #FFC107;">Common Validation Issues</h3>
        <ul>
        <li><b>"Material not supported":</b> Selected material isn't recommended for this printer/variant</li>
        <li><b>"Variant not supported":</b> Nozzle variant has compatibility issues</li>
        <li><b>"Material incompatible with current configuration":</b> Material-variant combination isn't supported</li>
        <li><b>"Configuration has validation errors":</b> General Cura validation issues detected</li>
        </ul>
        
        <h3 style="color: #FFC107;">Why This Matters</h3>
        <ul>
        <li><b>Material Compatibility:</b> Ensure selected profiles match loaded materials and prevent failed prints</li>
        <li><b>Multi-Extruder Setup:</b> Verify correct extruder configuration before batch processing</li>
        <li><b>Troubleshooting:</b> Identify configuration issues before starting long batch jobs</li>
        <li><b>Quality Assurance:</b> Catch "Not supported" configurations that Cura would flag</li>
        <li><b>Time Saving:</b> Avoid batch processing with incompatible settings that could fail</li>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">

        <h2 style="color: #4CAF50;">🎮 Control Section</h2>
        
        <h3 style="color: #FFC107;">Start Auto Slicing</h3>
        <p><b>What it does:</b> Begins the automated batch processing workflow</p>
        <p><b>Processing Pipeline (per file):</b></p>
        <ol>
        <li><b>Quality Profile Switch:</b> Changes to the assigned profile for this file</li>
        <li><b>Build Plate Clear:</b> Removes any existing models</li>
        <li><b>Model Loading:</b> Loads the 3D model file</li>
        <li><b>Positioning:</b> Uses Cura's auto-arrange or UCP positioning (for 3MF)</li>
        <li><b>Slicing:</b> Generates tool paths using current profile settings</li>
        <li><b>Output Save:</b> Saves the sliced file with timestamp</li>
        <li><b>File Management:</b> Moves original to "sliced" subfolder</li>
        <li><b>Logging:</b> Records result in CSV log file</li>
        </ol>
        
        <p><b>Requirements before starting:</b></p>
        <ul>
        <li>Source and destination folders configured</li>
        <li>At least one file selected for processing</li>
        <li>Valid printer configuration active in Cura</li>
        <li>Sufficient disk space in destination folder</li>
        </ul>

        <h3 style="color: #FFC107;">Skip Current File</h3>
        <p><b>Purpose:</b> Skip the currently processing file and continue with the next one</p>
        <p><b>When to use:</b></p>
        <ul>
        <li>File is taking unusually long to slice</li>
        <li>You notice an issue with the current file</li>
        <li>Need to continue processing other files without stopping the entire batch</li>
        </ul>
        <p><b>What happens:</b></p>
        <ul>
        <li>Current slicing operation is cancelled</li>
        <li>File is marked as "skipped" in the log</li>
        <li>Processing continues with the next file in queue</li>
        <li>Original file remains in source folder (not moved to "sliced")</li>
        </ul>

        <h3 style="color: #FFC107;">Stop Processing</h3>
        <p><b>Purpose:</b> Immediately halt the entire batch processing operation</p>
        <p><b>Behavior:</b></p>
        <ul>
        <li>Completes processing of the current file if possible</li>
        <li>Cancels any pending files in the queue</li>
        <li>Restores original Cura quality profile and settings</li>
        <li>Clears the build plate</li>
        <li>Provides final processing summary</li>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">

        <h2 style="color: #4CAF50;">📊 Progress Section</h2>
        
        <h3 style="color: #FFC107;">Progress Bar</h3>
        <p><b>Visual Indicator:</b> Shows completion percentage of the entire batch</p>
        <p><b>Calculation:</b> Based on number of files processed vs. total selected files</p>
        
        <h3 style="color: #FFC107;">Status Messages</h3>
        <p><b>Common status messages you'll see:</b></p>
        <ul>
        <li><b>"Ready":</b> Plugin is idle and ready to start</li>
        <li><b>"Discovering files...":</b> Scanning source folder for compatible files</li>
        <li><b>"Processing [filename] (X/Y)":</b> Currently working on a specific file</li>
        <li><b>"Slicing with timeout of X seconds...":</b> Model is being sliced with your configured timeout</li>
        <li><b>"Restoring original machine state...":</b> Returning Cura to pre-processing settings</li>
        <li><b>"Completed processing X files successfully":</b> Final success message</li>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">

        <h2 style="color: #4CAF50;">📝 Processing Log</h2>
        
        <h3 style="color: #FFC107;">Real-Time Information</h3>
        <p><b>The log displays:</b></p>
        <ul>
        <li><b>Start/Stop Notifications:</b> When processing begins and ends</li>
        <li><b>File Status Updates:</b> Progress through each file in the batch</li>
        <li><b>Success Messages:</b> Confirmation when files complete successfully</li>
        <li><b style="color: #f44336;">Error Messages (in red):</b> Detailed error information for failed files</li>
        <li><b>Skip Notifications:</b> When files are skipped (manually or automatically)</li>
        <li><b>Profile Changes:</b> Quality profile switches during processing</li>
        <li><b>File Selection Updates:</b> When file selections are modified</li>
        </ul>
        
        <h3 style="color: #FFC107;">Log Features</h3>
        <ul>
        <li><b>Auto-Scroll:</b> Automatically scrolls to show latest messages</li>
        <li><b>Color Coding:</b> Errors in red, normal operations in light gray</li>
        <li><b>Clear Logs Button:</b> Remove all messages for a clean start</li>
        <li><b>Persistent:</b> Log remains visible until manually cleared</li>
        </ul>

        <h3 style="color: #FFC107;">Understanding Error Messages</h3>
        <p><b>Common error types and their meanings:</b></p>
        <ul>
        <li><b>"Failed to load model file":</b> File corruption, unsupported format, or access issues</li>
        <li><b>"Failed to slice model":</b> Invalid geometry, memory issues, or incompatible settings</li>
        <li><b>"Failed to save output file":</b> Disk space, permissions, or destination folder issues</li>
        <li><b>"Insufficient disk space":</b> Less than 100MB available in destination</li>
        <li><b>"No write permission":</b> Destination folder access restrictions</li>
        <li><b>"Slicing timeout":</b> Model took longer than configured timeout value</li>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">

        <h2 style="color: #4CAF50;">💡 Best Practices & Tips</h2>
        
        <h3 style="color: #FFC107;">Getting Started</h3>
        <ul>
        <li><b>Start Small:</b> Test with 2-3 files before processing large batches</li>
        <li><b>Test Profiles:</b> Verify quality settings work correctly with sample files</li>
        <li><b>Check Validation Status:</b> Ensure all extruders show green (valid) status before starting</li>
        <li><b>Resolve Warnings:</b> Address yellow warning indicators for optimal results</li>
        <li><b>Check Disk Space:</b> Ensure adequate storage before starting large batches</li>
        <li><b>Backup Originals:</b> Keep copies of important files elsewhere</li>
        </ul>
        
        <h3 style="color: #FFC107;">Validation Best Practices</h3>
        <ul>
        <li><b>Monitor Extruder Status:</b> Watch for validation icons (⚠️ ❌) that indicate compatibility issues</li>
        <li><b>Fix Errors First:</b> Resolve red error indicators before starting batch processing</li>
        <li><b>Investigate Warnings:</b> Yellow warnings may still work but could affect print quality</li>
        <li><b>Use Tooltips:</b> Hover over validation icons for specific problem descriptions</li>
        <li><b>Real-Time Updates:</b> Status updates automatically when you change materials in Cura</li>
        </ul>
        
        <h3 style="color: #FFC107;">Optimization Tips</h3>
        <ul>
        <li><b>Close Unnecessary Applications:</b> Free up system resources for stable slicing</li>
        <li><b>Use Consistent File Types:</b> Mixing formats may cause processing variations</li>
        <li><b>Monitor First Few Files:</b> Watch initial results to catch issues early</li>
        <li><b>Organize by Complexity:</b> Group similar complexity models for better timeout estimates</li>
        </ul>
        
        <h3 style="color: #FFC107;">Troubleshooting</h3>
        <ul>
        <li><b>Check Error Logs:</b> Detailed error information helps identify issues</li>
        <li><b>Review CSV File:</b> Complete processing history with timestamps</li>
        <li><b>Verify File Integrity:</b> Ensure source files aren't corrupted</li>
        <li><b>Test Individual Files:</b> Process problematic files manually first</li>
        <li><b>Update Timeout:</b> Increase timeout for complex models</li>
        <li><b>Refresh Profiles:</b> Use "Update Profiles" button if quality profiles seem outdated after changing printer settings</li>
        <li><b>Validation Issues:</b> Check printer information section for compatibility warnings</li>
        <li><b>Material Problems:</b> Verify material-variant combinations are supported</li>
        <li><b>Red Status Indicators:</b> Fix critical errors before attempting batch processing</li>
        <li><b>Yellow Warnings:</b> Consider changing materials or variants for better compatibility</li>
        </ul>
        
        <h3 style="color: #FFC107;">Validation Troubleshooting</h3>
        <ul>
        <li><b>"Material not supported":</b> Switch to a compatible material or different variant</li>
        <li><b>"Variant not supported":</b> Use a different nozzle variant or update material</li>
        <li><b>"Material incompatible":</b> Check Cura's material-variant compatibility matrix</li>
        <li><b>Persistent errors:</b> Restart Cura to refresh validation state</li>
        <li><b>Missing validation:</b> Ensure you're using official Cura materials and variants</li>
        </ul>
        
        <h3 style="color: #FFC107;">Performance Considerations</h3>
        <ul>
        <li><b>Memory Usage:</b> Large models require more RAM for processing</li>
        <li><b>CPU Load:</b> Slicing is CPU-intensive; avoid other heavy tasks</li>
        <li><b>Disk I/O:</b> Use fast storage for source and destination folders</li>
        <li><b>Batch Size:</b> Balance efficiency with system stability</li>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">

        <h2 style="color: #4CAF50;">📋 Output Files & Logging</h2>
        
        <h3 style="color: #FFC107;">Generated Files</h3>
        <p><b>In your destination folder, you'll find:</b></p>
        <ul>
        <li><b>Sliced Files:</b> [name]_[timestamp].[format] - Ready for printing</li>
        <li><b>CSV Log:</b> "auto_slicer_progress.csv" - Complete processing record</li>
        </ul>
        
        <h3 style="color: #FFC107;">CSV Log Contents</h3>
        <p><b>The CSV file tracks:</b></p>
        <ul>
        <li><b>filename:</b> Original file name</li>
        <li><b>source_path:</b> Full path to original file</li>
        <li><b>ufp_path:</b> Full path to output file</li>
        <li><b>status:</b> "completed", "failed", or "skipped"</li>
        <li><b>timestamp:</b> When processing occurred</li>
        <li><b>error_message:</b> Details for failed files</li>
        </ul>
        
        <h3 style="color: #FFC107;">File Organization After Processing</h3>
        <p><b>Source Folder Structure:</b></p>
        <ul>
        <li><b>Source Folder/</b></li>
        <ul>
        <li>remaining_unprocessed_files.stl</li>
        <li><b>sliced/</b> (automatically created)</li>
        <ul>
        <li>successfully_processed_file1.stl</li>
        <li>successfully_processed_file2.3mf</li>
        </ul>
        </ul>
        </ul>
        
        <p><b>Destination Folder Structure:</b></p>
        <ul>
        <li><b>Destination Folder/</b></li>
        <ul>
        <li>file1_20250801_14_30.ufp OR file1_20250801_14_30.gcode</li>
        <li>file2_20250801_14_35.ufp OR file2_20250801_14_35.gcode</li>
        <li>auto_slicer_progress.csv</li>
        </ul>
        </ul>

        <hr style="border: 2px solid #555; margin: 20px 0;">
        
        <p style="text-align: center; color: #2196F3; font-weight: bold; font-size: 14px;">
        🚀 Happy Batch Slicing! 🚀<br>
        </p>
        """
        
        help_text.setHtml(help_content)
        layout.addWidget(help_text)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(PluginConstants.CLOSE_BUTTON_STYLE)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)


class AutoSlicerDialog(QDialog):
    """Dialog for configuring and monitoring the auto slicing process."""
    
    # Signals
    startProcessing = pyqtSignal(str, str, int, list, int)  # source_folder, destination_folder, max_files, file_profile_map, slice_timeout
    stopProcessing = pyqtSignal()
    skipCurrentFile = pyqtSignal()  # Signal to skip current file
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto Slicer")
        self.setMinimumSize(PluginConstants.AUTO_SLICER_DIALOG_MIN_WIDTH, PluginConstants.AUTO_SLICER_DIALOG_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        # Set fixed width for consistent dialog width
        self.setFixedWidth(PluginConstants.AUTO_SLICER_DIALOG_MAX_WIDTH)
        # Start with minimum height - will grow as needed
        self.resize(PluginConstants.AUTO_SLICER_DIALOG_MAX_WIDTH, PluginConstants.AUTO_SLICER_DIALOG_MIN_HEIGHT)
        
        # Apply dialog background styling
        self.setStyleSheet(PluginConstants.DIALOG_BACKGROUND_STYLE)
        
        # Initialize controller
        self._controller = AutoSlicerController()
        
        # Connect controller signals
        self._controller.qualityProfilesLoaded.connect(self._onQualityProfilesLoaded)
        self._controller.printerInfoUpdated.connect(self._onPrinterInfoUpdated)
        self._controller.logMessageEmitted.connect(self._logMessage)
        
        # State
        self._is_processing = False
        self._quality_profiles = []
        self._selected_files = []  # Store selected files from child dialog
        
        self._setupUI()
        self._loadSettings()
        
    def _setupUI(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Configuration Section
        config_group = QGroupBox("Configuration")
        config_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        config_layout = QGridLayout()
        
        # Source folder selection
        source_label = QLabel("Source Folder:")
        source_label.setStyleSheet(PluginConstants.LABEL_STYLE)
        config_layout.addWidget(source_label, 0, 0)
        self._source_folder_edit = QLineEdit()
        self._source_folder_edit.setPlaceholderText("Select folder containing STL/3MF files")
        self._source_folder_edit.setStyleSheet(PluginConstants.LINE_EDIT_STYLE)
        self._source_folder_edit.textChanged.connect(self._saveSettings)
        config_layout.addWidget(self._source_folder_edit, 0, 1)
        
        self._source_browse_btn = QPushButton("Browse...")
        self._source_browse_btn.setStyleSheet(PluginConstants.BROWSE_BUTTON_STYLE)
        self._source_browse_btn.clicked.connect(self._browseSourceFolder)
        config_layout.addWidget(self._source_browse_btn, 0, 2)
        
        # Destination folder selection
        dest_label = QLabel("Destination Folder:")
        dest_label.setStyleSheet(PluginConstants.LABEL_STYLE)
        config_layout.addWidget(dest_label, 1, 0)
        self._dest_folder_edit = QLineEdit()
        self._dest_folder_edit.setPlaceholderText("Select folder for Slice output files")
        self._dest_folder_edit.setStyleSheet(PluginConstants.LINE_EDIT_STYLE)
        self._dest_folder_edit.textChanged.connect(self._saveSettings)
        config_layout.addWidget(self._dest_folder_edit, 1, 1)
        
        self._dest_browse_btn = QPushButton("Browse...")
        self._dest_browse_btn.setStyleSheet(PluginConstants.BROWSE_BUTTON_STYLE)
        self._dest_browse_btn.clicked.connect(self._browseDestFolder)
        config_layout.addWidget(self._dest_browse_btn, 1, 2)
        
        # Max files input
        max_files_label = QLabel("Max Files to Process:")
        max_files_label.setStyleSheet(PluginConstants.LABEL_STYLE)
        config_layout.addWidget(max_files_label, 2, 0)
        self._max_files_spin = QSpinBox()
        self._max_files_spin.setMinimum(0)
        self._max_files_spin.setMaximum(1000)
        self._max_files_spin.setValue(10)
        self._max_files_spin.setToolTip("Maximum number of files to process (0 = no limit)")
        self._max_files_spin.setStyleSheet(PluginConstants.LINE_EDIT_STYLE)
        self._max_files_spin.valueChanged.connect(self._saveSettings)
        config_layout.addWidget(self._max_files_spin, 2, 1)
        
        # Slice timeout input
        timeout_label = QLabel("Slice Timeout (seconds):")
        timeout_label.setStyleSheet(PluginConstants.LABEL_STYLE)
        config_layout.addWidget(timeout_label, 3, 0)
        self._slice_timeout_spin = QSpinBox()
        self._slice_timeout_spin.setMinimum(30)
        self._slice_timeout_spin.setMaximum(3600)  # 1 hour max
        self._slice_timeout_spin.setValue(300)  # Default 5 minutes
        self._slice_timeout_spin.setToolTip("Maximum time to wait for each model to slice (30-3600 seconds)")
        self._slice_timeout_spin.setStyleSheet(PluginConstants.LINE_EDIT_STYLE)
        self._slice_timeout_spin.valueChanged.connect(self._saveSettings)
        config_layout.addWidget(self._slice_timeout_spin, 3, 1)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # File Selection Section
        file_selection_group = QGroupBox("File Selection")
        file_selection_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        file_selection_layout = QVBoxLayout()
        
        # Selected files info
        self._selected_files_label = QLabel("No files selected - Click 'Select Files to Process' to begin")
        self._selected_files_label.setStyleSheet(PluginConstants.LABEL_STYLE)
        file_selection_layout.addWidget(self._selected_files_label)
        
        # Select files button
        self._select_files_btn = QPushButton("Select Files to Process...")
        self._select_files_btn.setStyleSheet(PluginConstants.START_BUTTON_STYLE)
        self._select_files_btn.clicked.connect(self._openFileSelectionDialog)
        file_selection_layout.addWidget(self._select_files_btn)
        
        file_selection_group.setLayout(file_selection_layout)
        layout.addWidget(file_selection_group)
        
        # Printer Information Section
        printer_info_group = QGroupBox("Active Printer Information")
        printer_info_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        printer_info_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        printer_info_group.setMinimumHeight(PluginConstants.PRINTER_INFO_SECTION_MIN_HEIGHT)
        printer_info_layout = QVBoxLayout()
        printer_info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Printer name
        self._printer_name_label = QLabel("Printer: Loading...")
        self._printer_name_label.setStyleSheet(PluginConstants.PRINTER_INFO_LABEL_STYLE + "font-weight: bold; font-size: 13px;")
        self._printer_name_label.setMinimumHeight(PluginConstants.PRINTER_INFO_LABEL_MIN_HEIGHT)
        self._printer_name_label.setMaximumHeight(PluginConstants.PRINTER_INFO_LABEL_MAX_HEIGHT)
        printer_info_layout.addWidget(self._printer_name_label)
        
        # Extruders information container
        self._extruders_layout = QVBoxLayout()
        self._extruders_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        printer_info_layout.addLayout(self._extruders_layout)
        
        # Add stretch to push content to top when there are fewer extruders
        printer_info_layout.addStretch()
        
        printer_info_group.setLayout(printer_info_layout)
        layout.addWidget(printer_info_group)
        
        # Control Section
        control_group = QGroupBox("Control")
        control_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        control_layout = QHBoxLayout()
        
        self._start_btn = QPushButton("Start Auto Slicing")
        self._start_btn.setStyleSheet(PluginConstants.START_BUTTON_STYLE)
        self._start_btn.clicked.connect(self._onStartClicked)
        control_layout.addWidget(self._start_btn)
        
        self._skip_btn = QPushButton("Skip Current File")
        self._skip_btn.setStyleSheet(PluginConstants.SKIP_BUTTON_STYLE)
        self._skip_btn.clicked.connect(self._onSkipClicked)
        self._skip_btn.setEnabled(False)
        self._skip_btn.setToolTip("Skip the current file being processed and continue with the next file")
        control_layout.addWidget(self._skip_btn)
        
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setStyleSheet(PluginConstants.STOP_BUTTON_STYLE)
        self._stop_btn.clicked.connect(self._onStopClicked)
        self._stop_btn.setEnabled(False)
        control_layout.addWidget(self._stop_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Progress Section
        progress_group = QGroupBox("Progress")
        progress_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        progress_layout = QVBoxLayout()
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(PluginConstants.AUTO_SLICER_PROGRESS_BAR_STYLE)
        progress_layout.addWidget(self._progress_bar)
        
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(PluginConstants.STATUS_LABEL_STYLE)
        progress_layout.addWidget(self._status_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Log Section
        log_group = QGroupBox("Processing Log")
        log_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        log_layout = QVBoxLayout()
        
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMinimumHeight(100)
        self._log_text.setMaximumHeight(200)
        font = QFont("Consolas", 9)
        self._log_text.setFont(font)
        self._log_text.setStyleSheet(PluginConstants.AUTO_SLICER_LOG_STYLE)
        log_layout.addWidget(self._log_text)
        
        # Clear log button
        clear_log_layout = QHBoxLayout()
        self._clear_log_btn = QPushButton("Clear Logs")
        self._clear_log_btn.setStyleSheet(PluginConstants.BROWSE_BUTTON_STYLE)
        self._clear_log_btn.clicked.connect(self._clearLog)
        clear_log_layout.addWidget(self._clear_log_btn)
        clear_log_layout.addStretch()
        log_layout.addLayout(clear_log_layout)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Bottom buttons
        bottom_layout = QHBoxLayout()
        
        self._help_btn = QPushButton("Help")
        self._help_btn.setStyleSheet(PluginConstants.BROWSE_BUTTON_STYLE)
        self._help_btn.clicked.connect(self._showHelpDialog)
        bottom_layout.addWidget(self._help_btn)
        
        bottom_layout.addStretch()
        
        self._close_btn = QPushButton("Close")
        self._close_btn.setStyleSheet(PluginConstants.CLOSE_BUTTON_STYLE)
        self._close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self._close_btn)
        
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
        
    def _browseSourceFolder(self):
        """Browse for source folder."""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Source Folder",
            self._source_folder_edit.text() or os.path.expanduser("~")
        )
        if folder:
            self._source_folder_edit.setText(folder)
            self._saveSettings()
            # Clear selected files when source folder changes
            self._selected_files = []
            self._updateSelectedFilesLabel()
            
    def _browseDestFolder(self):
        """Browse for destination folder."""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Destination Folder",
            self._dest_folder_edit.text() or os.path.expanduser("~")
        )
        if folder:
            self._dest_folder_edit.setText(folder)
            self._saveSettings()
    
    def _openFileSelectionDialog(self):
        """Open the file selection dialog."""
        source_folder = self._source_folder_edit.text().strip()
        
        if not source_folder:
            self._logMessage("Error: Please select a source folder first", is_error=True)
            return
            
        if not os.path.isdir(source_folder):
            self._logMessage("Error: Source folder does not exist", is_error=True)
            return
            
        if not self._quality_profiles:
            self._logMessage("Error: Quality profiles are not loaded yet. Please wait a moment and try again.", is_error=True)
            return
        
        # Open the file selection dialog with previous selections
        dialog = FileSelectionDialog(
            parent=self,
            source_folder=source_folder,
            max_files=self._max_files_spin.value(),
            quality_profiles=self._quality_profiles,
            previous_selections=self._selected_files,  # Pass previous selections
            controller=self._controller
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._selected_files = dialog.getSelectedFiles()
            self._updateSelectedFilesLabel()
            self._logMessage(f"Selected {len(self._selected_files)} files for processing")
    
    def _updateSelectedFilesLabel(self):
        """Update the label showing selected files count."""
        count = len(self._selected_files)
        if count == 0:
            self._selected_files_label.setText("No files selected - Click 'Select Files to Process' to begin")
        elif count == 1:
            self._selected_files_label.setText("1 file selected")
        else:
            self._selected_files_label.setText(f"{count} files selected")
    
    def _showHelpDialog(self):
        """Show the help dialog."""
        help_dialog = HelpDialog(self)
        help_dialog.exec()
    
    def _onStartClicked(self):
        """Handle start button click."""
        # Validate inputs
        source_folder = self._source_folder_edit.text().strip()
        dest_folder = self._dest_folder_edit.text().strip()
        max_files = self._max_files_spin.value()
        
        # Use controller to validate
        errors = self._controller.validateStartProcessing(source_folder, dest_folder)
        
        if not self._selected_files:
            errors.append("No files selected for processing. Please use 'Select Files to Process' button to choose files.")
        
        if errors:
            for error in errors:
                self._logMessage(f"Error: {error}", is_error=True)
            if not self._selected_files:
                # Highlight the file selection section to guide the user
                self._select_files_btn.setFocus()
            return

        # Start processing
        self._setProcessingState(True)
        self._logMessage("Starting auto slicing process...")
        
        slice_timeout = self._slice_timeout_spin.value()
        self.startProcessing.emit(source_folder, dest_folder, max_files, self._selected_files, slice_timeout)
    
    def _onStopClicked(self):
        """Handle stop button click."""
        self._logMessage("Stopping auto slicing process...")
        self.stopProcessing.emit()

    def _onSkipClicked(self):
        """Handle skip button click."""
        self._logMessage("Skipping current file...")
        self.skipCurrentFile.emit()
    
    def _setProcessingState(self, is_processing):
        """Update UI state based on processing status."""
        self._is_processing = is_processing
        
        # Update button states
        self._start_btn.setEnabled(not is_processing)
        self._stop_btn.setEnabled(is_processing)
        self._skip_btn.setEnabled(is_processing)
        
        # Update input states
        self._source_folder_edit.setEnabled(not is_processing)
        self._dest_folder_edit.setEnabled(not is_processing)
        self._source_browse_btn.setEnabled(not is_processing)
        self._dest_browse_btn.setEnabled(not is_processing)
        self._max_files_spin.setEnabled(not is_processing)
        self._slice_timeout_spin.setEnabled(not is_processing)
        self._select_files_btn.setEnabled(not is_processing)
        
        # Update progress bar
        self._progress_bar.setVisible(is_processing)
        if not is_processing:
            self._progress_bar.setValue(0)
    
    def _logMessage(self, message, is_error=False):
        """Add a message to the log."""
        if is_error:
            formatted_message = f'<span style="color: {PluginConstants.ERROR_TEXT_COLOR_LIGHT_RED};">ERROR: {message}</span>'
            Logger.log("e", message)
        else:
            formatted_message = f'<span style="color: {PluginConstants.TEXT_COLOR_LIGHT_GRAY};">{message}</span>'
            
        self._log_text.append(formatted_message)
        
        # Auto-scroll to bottom
        cursor = self._log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._log_text.setTextCursor(cursor)
    
    def _clearLog(self):
        """Clear the log text area."""
        self._log_text.clear()
    
    def _loadSettings(self):
        """Load saved settings from JSON file."""
        settings = self._controller.loadSettings()
        
        # Load source folder
        if 'source_folder' in settings:
            self._source_folder_edit.setText(settings['source_folder'])
        
        # Load destination folder
        if 'dest_folder' in settings:
            self._dest_folder_edit.setText(settings['dest_folder'])
        
        # Load max files setting
        if 'max_files' in settings:
            self._max_files_spin.setValue(int(settings['max_files']))
        
        # Load slice timeout setting
        if 'slice_timeout' in settings:
            self._slice_timeout_spin.setValue(int(settings['slice_timeout']))
    
    def _saveSettings(self):
        """Save current settings to JSON file."""
        settings = {
            'source_folder': self._source_folder_edit.text(),
            'dest_folder': self._dest_folder_edit.text(),
            'max_files': self._max_files_spin.value(),
            'slice_timeout': self._slice_timeout_spin.value()
        }
        
        self._controller.saveSettings(settings)
    
    # Signal handlers for controller events
    def _onQualityProfilesLoaded(self, quality_profiles):
        """Handle quality profiles loaded from controller."""
        self._quality_profiles = quality_profiles
        if self._selected_files:
            self._logMessage("Quality profiles updated for selected files.")
    
    def _onPrinterInfoUpdated(self, printer_info):
        """Handle printer info updated from controller."""
        self._updatePrinterInfoDisplay(printer_info)
    
    def _updatePrinterInfoDisplay(self, printer_info):
        """Update the printer information display with enhanced validation status."""
        try:
            printer_name = printer_info.get('printer_name', 'Unknown')
            self._printer_name_label.setText(f"Printer: {printer_name}")
            
            self._clearExtrudersInfo()
            
            extruders = printer_info.get('extruders', [])
            for extruder_info in extruders:
                if extruder_info.get('error', False):
                    position = extruder_info.get('position', 0)
                    error_message = extruder_info.get('error_message', 'Unknown error')
                    extruder_text = f"Extruder {position}: {error_message}"
                    extruder_label = QLabel(extruder_text)
                    extruder_label.setStyleSheet(PluginConstants.PRINTER_INFO_ERROR_STYLE)
                    extruder_label.setMinimumHeight(PluginConstants.PRINTER_INFO_LABEL_MIN_HEIGHT)
                    extruder_label.setMaximumHeight(PluginConstants.PRINTER_INFO_LABEL_MAX_HEIGHT)
                    self._extruders_layout.addWidget(extruder_label)
                else:
                    position = extruder_info.get('position', 0)
                    variant_name = extruder_info.get('variant_name', 'Default')
                    original_variant_name = extruder_info.get('original_variant_name', '')
                    nozzle_size = extruder_info.get('nozzle_size', 'Unknown')
                    material_name = extruder_info.get('material_name', 'Unknown')
                    status = extruder_info.get('status', 'Unknown')
                    enabled = extruder_info.get('enabled', False)
                    
                    # Enhanced validation information
                    validation_status = extruder_info.get('validation_status', 'Valid')
                    validation_details = extruder_info.get('validation_details', [])
                    has_errors = extruder_info.get('has_errors', False)
                    has_warnings = extruder_info.get('has_warnings', False)
                    
                    extruder_row_layout = QHBoxLayout()
                    extruder_row_layout.setContentsMargins(0, 5, 0, 5)
                    extruder_row_layout.setSpacing(10)
                    
                    if not original_variant_name or original_variant_name.strip() == "":
                        extruder_info_text = f"Extruder {position}: {nozzle_size}"
                    elif variant_name == nozzle_size:
                        extruder_info_text = f"Extruder {position}: {variant_name}"
                    else:
                        extruder_info_text = f"Extruder {position}: {variant_name} ({nozzle_size})"
                    
                    extruder_info_label = QLabel(extruder_info_text)
                    extruder_info_label.setStyleSheet(PluginConstants.PRINTER_INFO_LABEL_STYLE)
                    extruder_info_label.setMinimumHeight(PluginConstants.PRINTER_INFO_LABEL_MIN_HEIGHT)
                    extruder_info_label.setMaximumHeight(PluginConstants.PRINTER_INFO_LABEL_MAX_HEIGHT)
                    extruder_row_layout.addWidget(extruder_info_label)
                    
                    material_label = QLabel(f"Material: {material_name}")
                    material_label.setStyleSheet(PluginConstants.PRINTER_INFO_LABEL_STYLE)
                    material_label.setMinimumHeight(PluginConstants.PRINTER_INFO_LABEL_MIN_HEIGHT)
                    material_label.setMaximumHeight(PluginConstants.PRINTER_INFO_LABEL_MAX_HEIGHT)
                    extruder_row_layout.addWidget(material_label)
                    
                    # Enhanced status display with validation-aware styling
                    status_text = f"Status: {status}"
                    if validation_details:
                        # Limit the details text to fit in available space
                        details_text = ', '.join(validation_details[:2])  # Max 2 details
                        if len(details_text) > 25:  # Truncate if too long
                            details_text = details_text[:22] + "..."
                        status_text += f" ({details_text})"
                    
                    status_label = QLabel(status_text)
                    status_label.setMinimumHeight(PluginConstants.PRINTER_INFO_LABEL_MIN_HEIGHT)
                    status_label.setMaximumHeight(PluginConstants.PRINTER_INFO_LABEL_MAX_HEIGHT)
                    
                    # Set tooltip with full validation details if text was truncated
                    if validation_details and len(validation_details) > 2 or (validation_details and len(', '.join(validation_details)) > 25):
                        full_details = '\n'.join([f"• {detail}" for detail in validation_details])
                        status_label.setToolTip(f"Validation Status: {validation_status}\n{full_details}")
                    
                    # Color-coded status based on validation state
                    if has_errors or status == "Error":
                        status_label.setStyleSheet(PluginConstants.PRINTER_INFO_ERROR_STYLE)
                    elif has_warnings or status == "Warning":
                        status_label.setStyleSheet(PluginConstants.PRINTER_INFO_WARNING_STYLE)
                    elif enabled and status == "Active":
                        status_label.setStyleSheet(PluginConstants.PRINTER_INFO_ACTIVE_STYLE)
                    else:
                        status_label.setStyleSheet(PluginConstants.PRINTER_INFO_DISABLED_STYLE)
                    
                    extruder_row_layout.addWidget(status_label)
                    
                    # Add validation indicator if there are validation issues
                    if has_errors or has_warnings:
                        validation_icon = "⚠️" if has_warnings and not has_errors else "❌"
                        validation_label = QLabel(validation_icon)
                        validation_label.setStyleSheet("font-size: 14px; padding: 2px;")
                        validation_label.setToolTip(f"Validation: {validation_status}\n" + 
                                                  "\n".join(validation_details) if validation_details else "")
                        extruder_row_layout.addWidget(validation_label)
                    
                    extruder_row_layout.addStretch()
                    
                    extruder_row_widget = QWidget()
                    extruder_row_widget.setLayout(extruder_row_layout)
                    
                    self._extruders_layout.addWidget(extruder_row_widget)

            # Force layout recalculation
            self.layout().activate()
            self.updateGeometry()
            
            # Calculate optimal size based on content
            optimal_size = self.sizeHint()
            current_size = self.size()
            
            # Always use the optimal height, but keep fixed width
            new_width = PluginConstants.AUTO_SLICER_DIALOG_MAX_WIDTH
            new_height = max(optimal_size.height(), current_size.height())
            
            # Apply minimum height constraint
            min_height = PluginConstants.AUTO_SLICER_DIALOG_MIN_HEIGHT
            final_height = max(new_height, min_height)
            
            # Force resize to calculated dimensions
            self.setFixedWidth(new_width)
            self.resize(new_width, final_height)
            
        except Exception as e:
            Logger.log("e", f"Error updating printer info display: {e}")
    
    def _clearExtrudersInfo(self):
        """Clear all extruder information labels."""
        try:
            while self._extruders_layout.count():
                child = self._extruders_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        except Exception as e:
            Logger.log("w", f"Error clearing extruder info: {e}")
    
    # Slots for external updates
    def onProgressUpdate(self, progress):
        """Handle progress update from the processing job."""
        self._progress_bar.setValue(int(progress))
    
    def onStatusUpdate(self, status):
        """Handle status update from the processing job."""
        self._status_label.setText(status)
    
    def onProcessingComplete(self, results):
        """Handle processing completion."""
        self._setProcessingState(False)
        self._status_label.setText("Complete")
        
        success_count = results.get('success_count', 0)
        error_count = results.get('error_count', 0)
        error_details = results.get('error_details', [])
        skipped_files = results.get('skipped_files', [])
        skipped_count = len(skipped_files)
        
        self._logMessage("Processing complete!")
        self._logMessage(f"Successfully processed: {success_count} files")
        
        if skipped_count > 0:
            self._logMessage(f"Files skipped: {skipped_count}")
            for skipped_file in skipped_files:
                self._logMessage(f"  - {skipped_file}")
        
        if error_count > 0:
            self._logMessage(f"Errors encountered: {error_count} files", is_error=True)
            
            # Display detailed error information
            if error_details:
                self._logMessage("─" * 50, is_error=True)  # Visual separator
                self._logMessage("DETAILED ERROR INFORMATION:", is_error=True)
                self._logMessage("─" * 50, is_error=True)  # Visual separator
                
                for i, error_detail in enumerate(error_details, 1):
                    filename = error_detail.get('filename', 'Unknown file')
                    error_message = error_detail.get('error_message', 'Unknown error')
                    
                    # Truncate very long error messages for readability
                    if len(error_message) > 200:
                        error_message = error_message[:200] + "..."
                    
                    self._logMessage(f"{i}. File: {filename}", is_error=True)
                    self._logMessage(f"   Error: {error_message}", is_error=True)
                    if i < len(error_details):  # Add space between entries except for last one
                        self._logMessage("", is_error=True)  # Empty line for spacing
        
        # Clear selected files after processing to ensure users select new files for next batch
        self._selected_files = []
        self._updateSelectedFilesLabel()
        self._logMessage("File selection cleared. Please select new files for the next batch.")
    
    def onProcessingError(self, error_message):
        """Handle processing error."""
        self._setProcessingState(False)
        self._status_label.setText("Error")
        self._logMessage(error_message, is_error=True)
        
        # Clear selected files after a critical error to prompt user to re-select
        # This helps ensure they review their file selection after resolving the issue
        self._selected_files = []
        self._updateSelectedFilesLabel()
        self._logMessage("File selection cleared due to processing error. Please resolve the issue and select files again.")
    
    def onFileError(self, filename, error_message):
        """Handle individual file processing error in real-time."""
        # Truncate long error messages for real-time display
        if len(error_message) > 100:
            display_message = error_message[:100] + "..."
        else:
            display_message = error_message
        
        self._logMessage(f"ERROR processing {filename}: {display_message}", is_error=True)

    def onFileSkipped(self, filename, skip_reason):
        """Handle individual file skip in real-time."""
        self._logMessage(f"SKIPPED {filename}: {skip_reason}")
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self._is_processing:
            # If processing is active, stop it first
            self.stopProcessing.emit()
        
        super().closeEvent(event)
    