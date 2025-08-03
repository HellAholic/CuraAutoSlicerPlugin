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
import json
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from UM.Logger import Logger
from cura.CuraApplication import CuraApplication
from cura.Machines.ContainerTree import ContainerTree


class AutoSlicerController(QObject):
    """Controller class that handles all business logic for the AutoSlicer plugin."""
    
    # Signals
    qualityProfilesLoaded = pyqtSignal(list)  # quality_profiles
    printerInfoUpdated = pyqtSignal(dict)  # printer_info
    logMessageEmitted = pyqtSignal(str, bool)  # message, is_error
    
    # Settings file path - store in the same directory as this plugin file
    SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "autoslicer_settings.json")
    
    def __init__(self):
        super().__init__()
        self._quality_profiles = []
        self._is_machine_change_refresh = False
        
        # Connect to machine change signals
        self._connectMachineChangeSignals()
        
        # Load quality profiles asynchronously
        self._loadQualityProfilesAsync()
        
        # Update printer information
        self._updatePrinterInfo()
    
    def getQualityProfiles(self):
        """Get the current quality profiles."""
        return self._quality_profiles
    
    def loadSettings(self):
        """Load saved settings from JSON file."""
        try:
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                return settings
            else:
                return {}
        except Exception as e:
            Logger.log("w", f"Failed to load Auto Slicer settings: {str(e)}")
            return {}
    
    def saveSettings(self, settings):
        """Save current settings to JSON file."""
        try:
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            Logger.log("w", f"Failed to save Auto Slicer settings: {str(e)}")
    
    def validateStartProcessing(self, source_folder, dest_folder):
        """Validate inputs before starting processing."""
        errors = []
        
        if not source_folder:
            errors.append("Please select a source folder")
        elif not os.path.exists(source_folder):
            errors.append(f"Source folder does not exist: {source_folder}")
            
        if not dest_folder:
            errors.append("Please select a destination folder")
        elif not os.path.exists(dest_folder):
            errors.append(f"Destination folder does not exist: {dest_folder}")
            
        if not self._quality_profiles:
            errors.append("No quality profiles available. Please wait for profiles to load or ensure you have quality profiles configured for your printer.")
        
        return errors
    
    def getFilesFromFolder(self, source_folder, max_files=0):
        """Get list of supported files from source folder."""
        if not os.path.isdir(source_folder):
            return []

        supported_extensions = ['.stl', '.3mf']
        files = [f for f in os.listdir(source_folder) 
                if os.path.isfile(os.path.join(source_folder, f)) 
                and os.path.splitext(f)[1].lower() in supported_extensions]
        files.sort()

        if max_files > 0:
            files = files[:max_files]

        return files
    
    def getCurrentMachineInfo(self):
        """Get current machine profile information."""
        try:
            machine_manager = CuraApplication.getInstance().getMachineManager()
            active_machine = machine_manager.activeMachine
            if active_machine:
                return {
                    'current_quality_id': active_machine.quality.getId(),
                    'current_quality_changes_id': active_machine.qualityChanges.getId(),
                    'current_intent_category': machine_manager.activeIntentCategory,
                    'current_quality_name': active_machine.quality.getName(),
                    'current_quality_changes_name': active_machine.qualityChanges.getName(),
                    'has_active_quality_changes': (active_machine.qualityChanges.getName() and 
                                                 active_machine.qualityChanges.getName().lower() not in ["empty", "not_supported"])
                }
        except Exception as e:
            Logger.log("w", f"Error getting current profile info: {e}")
        
        return {
            'current_quality_id': None,
            'current_quality_changes_id': None,
            'current_intent_category': None,
            'current_quality_name': None,
            'current_quality_changes_name': None,
            'has_active_quality_changes': False
        }
    
    def normalizeIntentName(self, intent_category):
        """Normalize intent category names for display with proper frontend name mapping."""
        if not intent_category or intent_category in ["", "default"]:
            return "Balanced"
        
        intent_mapping = {
            "default": "Balanced",
            "engineering": "Engineering",
            "accurate": "Engineering",
            "draft": "Draft",
            "quick": "Draft",
            "balanced": "Balanced",
            "fast": "Fast", 
            "fine": "Fine",
            "high_quality": "High Quality",
            "smooth": "Smooth",
            "strong": "Strong",
            "visual": "Visual"
        }
        
        return intent_mapping.get(intent_category.lower(), intent_category.title())
    
    def _logMessage(self, message, is_error=False):
        """Emit a log message signal."""
        self.logMessageEmitted.emit(message, is_error)
        if is_error:
            Logger.log("e", message)
    
    def _updatePrinterInfo(self):
        """Update the printer information display with enhanced validation status."""
        try:
            application = CuraApplication.getInstance()
            global_stack = application.getGlobalContainerStack()
            
            if not global_stack:
                printer_info = {'printer_name': "No active machine", 'extruders': []}
                self.printerInfoUpdated.emit(printer_info)
                return
            
            printer_name = global_stack.definition.getName()
            extruders = []
            
            extruder_manager = application.getExtruderManager()
            machine_manager = application.getMachineManager()
            
            # Get the machine error checker for validation status
            machine_error_checker = None
            try:
                machine_error_checker = application.getMachineErrorChecker()
            except Exception as e:
                Logger.log("w", f"Could not get machine error checker: {e}")
            
            for position in range(global_stack.getProperty("machine_extruder_count", "value")):
                try:
                    extruder_stack = extruder_manager.getExtruderStack(position)
                    if extruder_stack:
                        extruder_enabled = extruder_stack.getMetaDataEntry("enabled", "True") == "True"
                            
                        variant_name = extruder_stack.variant.getName()
                        
                        material_container = extruder_stack.material
                        material_name = material_container.getName()
                        material_brand = material_container.getMetaDataEntry("brand", "Generic")
                        
                        if material_brand.lower() not in material_name.lower():
                            full_material_name = f"{material_brand} {material_name}"
                        else:
                            full_material_name = material_name
                        
                        nozzle_size = extruder_stack.variant.getMetaDataEntry("hardware_compatible_nozzle_size", "Unknown")
                        if not nozzle_size or nozzle_size == "Unknown":
                            nozzle_size = extruder_stack.getProperty("machine_nozzle_size", "value")
                            if nozzle_size:
                                nozzle_size = f"{nozzle_size}mm"
                            else:
                                nozzle_size = "Unknown"
                        
                        original_variant_name = variant_name
                        if not variant_name or variant_name.strip() == "" or variant_name.lower() == "empty" or variant_name.lower() == "default":
                            if nozzle_size != "Unknown":
                                variant_name = nozzle_size
                            else:
                                variant_name = "Default"
                        
                        # Enhanced validation status checking
                        validation_status = "Valid"
                        validation_details = []
                        has_errors = False
                        has_warnings = False
                        
                        # Skip validation checks for disabled extruders
                        if extruder_enabled:
                            # Check for validation errors using Cura's error checker
                            if machine_error_checker:
                                try:
                                    has_errors = machine_error_checker.hasError
                                    if has_errors:
                                        validation_status = "Error"
                                        validation_details.append("Config errors")
                                        
                                    # Check for warnings using machine error checker
                                    if hasattr(machine_error_checker, 'hasWarning'):
                                        has_warnings = machine_error_checker.hasWarning
                                        if has_warnings and validation_status == "Valid":
                                            validation_status = "Warning"
                                            validation_details.append("Config warnings")
                                except Exception as e:
                                    Logger.log("w", f"Error checking validation status: {e}")
                            
                            # Check material-variant compatibility
                            try:
                                # Check if material and variant are compatible
                                material_type = material_container.getMetaDataEntry("material", "unknown")
                                variant_type = extruder_stack.variant.getMetaDataEntry("hardware_type", "unknown")
                                
                                # Check if the variant shows "Not supported" status (common Cura validation pattern)
                                variant_supported = extruder_stack.variant.getMetaDataEntry("supported", True)
                                material_supported = material_container.getMetaDataEntry("supported", True)
                                
                                # Check for explicit compatibility flags
                                material_compatible = material_container.getMetaDataEntry("compatible", True)
                                variant_compatible = extruder_stack.variant.getMetaDataEntry("compatible", True)
                                
                                # Additional checks for warning conditions - check container names
                                material_name_lower = material_name.lower()
                                variant_name_lower = variant_name.lower()
                                
                                # Check for "not supported" in names (common pattern)
                                if "not supported" in material_name_lower or "not supported" in variant_name_lower:
                                    has_warnings = True
                                    validation_details.append("Not supported config")
                                    if validation_status == "Valid":
                                        validation_status = "Warning"
                                
                                # Check for "empty" materials or variants which can indicate incompatibility
                                if "empty" in material_name_lower or "empty" in variant_name_lower:
                                    has_warnings = True
                                    validation_details.append("Empty config")
                                    if validation_status == "Valid":
                                        validation_status = "Warning"
                                
                                # Check container compatibility flags
                                if not variant_supported:
                                    has_warnings = True
                                    validation_details.append("Variant unsupported")
                                    if validation_status == "Valid":
                                        validation_status = "Warning"
                                
                                if not material_supported:
                                    has_warnings = True
                                    validation_details.append("Material unsupported")
                                    if validation_status == "Valid":
                                        validation_status = "Warning"
                                        
                                if not variant_compatible:
                                    has_warnings = True
                                    validation_details.append("Variant incompatible")
                                    if validation_status == "Valid":
                                        validation_status = "Warning"
                                
                                # Check for material-variant compatibility using container metadata
                                if not material_compatible:
                                    has_errors = True
                                    validation_status = "Error"
                                    validation_details.append("Incompatible config")
                                
                                # Check quality profile compatibility with material/variant
                                try:
                                    quality_stack = global_stack.quality
                                    if quality_stack:
                                        quality_supported = quality_stack.getMetaDataEntry("supported", True)
                                        quality_compatible = quality_stack.getMetaDataEntry("compatible", True)
                                        
                                        if not quality_supported or not quality_compatible:
                                            has_warnings = True
                                            validation_details.append("Quality unsupported")
                                            if validation_status == "Valid":
                                                validation_status = "Warning"
                                except Exception:
                                    pass
                                    
                            except Exception as e:
                                Logger.log("w", f"Error checking material-variant compatibility: {e}")
                        
                        # Set overall status based on validation
                        if not extruder_enabled:
                            status = "Disabled"
                        elif has_errors:
                            status = "Error"
                        elif has_warnings:
                            status = "Warning"
                        else:
                            status = "Active"
                        
                        extruder_info = {
                            'position': position + 1,
                            'variant_name': variant_name,
                            'original_variant_name': original_variant_name,
                            'nozzle_size': nozzle_size,
                            'material_name': full_material_name,
                            'status': status,
                            'enabled': extruder_enabled,
                            'validation_status': validation_status,
                            'validation_details': validation_details,
                            'has_errors': has_errors,
                            'has_warnings': has_warnings
                        }
                        extruders.append(extruder_info)
                    else:
                        extruder_info = {
                            'position': position + 1,
                            'error': True,
                            'error_message': "Not configured",
                            'status': "Error",
                            'validation_status': "Error",
                            'has_errors': True,
                            'has_warnings': False
                        }
                        extruders.append(extruder_info)
                        
                except Exception as extruder_error:
                    Logger.log("w", f"Error getting extruder {position} info: {extruder_error}")
                    extruder_info = {
                        'position': position + 1,
                        'error': True,
                        'error_message': "Error loading info",
                        'status': "Error",
                        'validation_status': "Error",
                        'has_errors': True,
                        'has_warnings': False
                    }
                    extruders.append(extruder_info)
            
            printer_info = {
                'printer_name': printer_name,
                'extruders': extruders
            }
            self.printerInfoUpdated.emit(printer_info)
            
        except Exception as e:
            Logger.log("e", f"Error updating printer info: {e}")
            printer_info = {
                'printer_name': "Error loading information",
                'extruders': []
            }
            self.printerInfoUpdated.emit(printer_info)

    def _connectMachineChangeSignals(self):
        """Connect to machine change signals to automatically update quality profiles and printer info."""
        try:
            application = CuraApplication.getInstance()
            
            if hasattr(application, 'globalContainerStackChanged'):
                application.globalContainerStackChanged.connect(self._onMachineChanged)
                
            machine_manager = application.getMachineManager()
            if hasattr(machine_manager, 'globalContainerChanged'):
                machine_manager.globalContainerChanged.connect(self._onMachineChanged)
            
            if hasattr(machine_manager, 'numberExtrudersEnabledChanged'):
                machine_manager.numberExtrudersEnabledChanged.connect(self._updatePrinterInfo)
            
            # Connect to validation change signals for real-time compatibility monitoring
            if hasattr(machine_manager, 'stacksValidationChanged'):
                machine_manager.stacksValidationChanged.connect(self._updatePrinterInfo)
            if hasattr(machine_manager, 'activeStackValidationChanged'):
                machine_manager.activeStackValidationChanged.connect(self._updatePrinterInfo)
                
            extruder_manager = application.getExtruderManager()
            if hasattr(extruder_manager, 'extrudersChanged'):
                extruder_manager.extrudersChanged.connect(self._updatePrinterInfo)
            if hasattr(extruder_manager, 'activeExtruderChanged'):
                extruder_manager.activeExtruderChanged.connect(self._updatePrinterInfo)
                
        except Exception as e:
            Logger.log("w", f"Could not connect to some machine change signals: {e}")
            
        try:                
            container_tree = ContainerTree.getInstance()
            if hasattr(container_tree, 'containerTreeChanged'):
                container_tree.containerTreeChanged.connect(self._onMachineChanged)
                
        except Exception as e:
            Logger.log("w", f"Could not connect to some machine change signals: {e}")

    def _buildCompatibleDefinitionsList(self, machine_definition_id, global_stack):
        """Build a list of compatible definition IDs using Cura's proper inheritance chain."""
        current_definition = global_stack.definition
        quality_definition = current_definition.getMetaDataEntry("quality_definition", machine_definition_id)
        
        compatible_definitions = [machine_definition_id]
        
        if quality_definition and quality_definition not in compatible_definitions:
            compatible_definitions.append(quality_definition)
        
        try:
            # Use metadata to get inheritance chain instead of getAncestors()
            inherited_from = current_definition.getMetaDataEntry("inherits", "")
            if inherited_from and inherited_from not in compatible_definitions:
                compatible_definitions.append(inherited_from)
        except Exception as ancestor_error:
            Logger.log("w", f"Could not get inheritance chain: {ancestor_error}")
            inherited_from = current_definition.getMetaDataEntry("inherits", "")
            if inherited_from and inherited_from not in compatible_definitions:
                compatible_definitions.append(inherited_from)
        
        return compatible_definitions

    def _onMachineChanged(self):
        """Handle machine change events by refreshing quality profiles and printer info."""
        try:            
            self._is_machine_change_refresh = True
            QTimer.singleShot(500, self._loadQualityProfiles)
            QTimer.singleShot(100, self._updatePrinterInfo)
            
        except Exception as e:
            Logger.log("e", f"Error handling machine change: {e}")

    def _loadQualityProfilesAsync(self):
        """Load quality profiles asynchronously to avoid blocking the UI."""
        self._logMessage("Loading quality profiles...")
        QTimer.singleShot(100, self._loadQualityProfiles)

    def _loadQualityProfiles(self):
        """Load available quality profiles using the proper Cura API."""
        try:
            application = CuraApplication.getInstance()
            global_stack = application.getGlobalContainerStack()
            
            if not global_stack:
                self._logMessage("No active machine found.", is_error=True)
                return

            machine_name = global_stack.definition.getName()
            machine_definition_id = global_stack.definition.getId()
            
            machine_manufacturer = global_stack.definition.getMetaDataEntry("manufacturer", "Unknown")
            self._logMessage(f"Detected machine: {machine_name} (ID: {machine_definition_id})")
            self._logMessage(f"Machine details - Manufacturer: {machine_manufacturer}")
            
            actual_machine_id = machine_definition_id
            if machine_definition_id == "fdmprinter":
                Logger.log("w", "Machine detected as fdmprinter - this may indicate a configuration issue")
                self._logMessage("Warning: Machine detected as generic fdmprinter - looking for specific definition...")
                
                container_registry = application.getContainerRegistry()
                
                all_machine_definitions = container_registry.findDefinitionContainers(type="machine")
                
                potential_matches = []
                for definition in all_machine_definitions:
                    def_id = definition.getId()
                    def_name = definition.getName().lower()
                    
                    machine_name_words = machine_name.lower().split()
                    if any(word in def_name for word in machine_name_words if len(word) > 2):
                        potential_matches.append((def_id, definition.getName()))
                
                if potential_matches:
                    actual_machine_id = potential_matches[0][0]
                    self._logMessage(f"Found specific machine definition: {potential_matches[0][1]} ({actual_machine_id})")
                else:
                    self._logMessage("No specific machine definition found, using generic profiles")
            
            machine_definition_id = actual_machine_id
            
            self._quality_profiles = []
            
            try:
                from cura.Machines.ContainerTree import ContainerTree
                container_tree = ContainerTree.getInstance()
                machine_definition_id = global_stack.definition.getId()
                
                machine_node = container_tree.machines[machine_definition_id]
                                
                # Get current machine configuration
                variant_names = [extruder.variant.getName() for extruder in global_stack.extruderList]
                material_bases = [extruder.material.getMetaDataEntry("base_file") for extruder in global_stack.extruderList]
                
                # Collect available quality_types for this machine/variant/material combination
                available_quality_types = set()
                
                # Get the current variant and material nodes for the first extruder (or global)
                current_variant = machine_node.variants.get(variant_names[0]) if variant_names else None
                if current_variant and material_bases[0]:
                    current_material = current_variant.materials.get(material_bases[0])
                    if current_material:
                        # Iterate through all quality nodes for this material to collect available quality_types
                        for quality_node in current_material.qualities.values():
                            available_quality_types.add(quality_node.quality_type)
                            
                            # Check if this quality node has intent profiles
                            if hasattr(quality_node, 'intents') and quality_node.intents:
                                # Process each intent profile for this quality
                                for intent_id, intent_node in quality_node.intents.items():                                    
                                    try:
                                        intent_container = intent_node.container
                                        if not intent_container:
                                            Logger.log("w", f"Intent {intent_id} has no container")
                                            continue
                                            
                                        # Get intent metadata - handle empty_intent as default
                                        if intent_id == "empty_intent":
                                            intent_category = "default"
                                        else:
                                            intent_category = intent_node.intent_category
                                        
                                        # Get the quality name from the base quality container, not the intent container
                                        quality_name = quality_node.container.getName()
                                        quality_type = quality_node.quality_type

                                        # Create a profile entry with the intent-specific information
                                        profile_entry = {
                                            'display_name': f"[M] {quality_name}",
                                            'container': quality_node.container,
                                            'intent': intent_category,
                                            'quality_name': quality_name,
                                            'quality_group': None,
                                            'quality_type': quality_type,
                                            'is_available': True,
                                            'intent_container': intent_container
                                        }
                                        self._quality_profiles.append(profile_entry)
                                        
                                    except Exception as intent_error:
                                        Logger.log("w", f"Error processing intent {intent_id}: {intent_error}")
                            else:
                                # No intents available, add the base quality profile with default intent
                                try:
                                    quality_name = quality_node.container.getName()
                                    quality_type = quality_node.quality_type
                                    
                                    profile_entry = {
                                        'display_name': quality_name,
                                        'container': quality_node.container,
                                        'intent': "default",
                                        'quality_name': quality_name,
                                        'quality_group': None,
                                        'quality_type': quality_type,
                                        'is_available': True
                                    }
                                    self._quality_profiles.append(profile_entry)
                                except Exception as base_error:
                                    Logger.log("w", f"Error adding base quality {quality_node.container_id}: {base_error}")
                    else:
                        Logger.log("w", f"No material node found for base: {material_bases[0]}")
                else:
                    Logger.log("w", f"No variant node found for: {variant_names[0] if variant_names else 'No variant'}")
                                        
            except Exception as tree_error:
                Logger.log("w", f"ContainerTree intent scanning failed: {tree_error}, falling back to container registry")
                available_quality_types = set()  # Initialize empty set for fallback
            
            # Always scan for user-defined quality_changes profiles with enhanced inheritance support
            container_registry = application.getContainerRegistry()
            all_quality_changes = container_registry.findInstanceContainers(type="quality_changes")
            quality_changes_containers = []  # Initialize the list
            
            # Build inheritance chain using Cura's proper getAncestors method
            current_definition = global_stack.definition
            quality_definition = current_definition.getMetaDataEntry("quality_definition", machine_definition_id)
            
            # Build list of compatible definition IDs using proper inheritance chain
            # Build compatibility list using inheritance chain
            compatible_definitions = self._buildCompatibleDefinitionsList(machine_definition_id, global_stack)
            
            # Add quality_definition if different from machine_definition_id
            if quality_definition and quality_definition not in compatible_definitions:
                compatible_definitions.append(quality_definition)
                        
            for qc_container in all_quality_changes:
                try:
                    qc_name = qc_container.getName()
                    qc_definition = qc_container.getMetaDataEntry("definition", "unknown")
                    qc_position = qc_container.getMetaDataEntry("position")
                    qc_quality_type = qc_container.getMetaDataEntry("quality_type", "normal")
                                        
                    # Skip if this is an extruder-specific container (we want global ones for now)
                    if qc_position is not None:
                        continue
                        
                    # Enhanced compatibility check using expanded definition list
                    is_compatible = False
                    compatibility_reason = "unknown"
                    
                    # Check if the quality_changes definition matches any compatible definition
                    if qc_definition in compatible_definitions:
                        is_compatible = True
                        compatibility_reason = f"definition_match ({qc_definition})"
                    
                    # Additional fallback for unknown definitions
                    elif qc_definition == "unknown":
                        is_compatible = True
                        compatibility_reason = "unknown_definition_fallback"
                    
                    # NEW: Check if the quality_type is available for current nozzle/material combination
                    # Only apply quality_type filtering if we have available_quality_types data
                    if is_compatible and available_quality_types:
                        if qc_quality_type not in available_quality_types:
                            is_compatible = False
                            compatibility_reason = f"quality_type_not_available ({qc_quality_type} not in {sorted(available_quality_types)})"
                            Logger.log("i", f"Filtering out quality_changes '{qc_name}' - {compatibility_reason}")
                    elif is_compatible and not available_quality_types:
                        # If we don't have available_quality_types data (fallback scenario), allow all quality_changes
                        # This ensures compatibility when ContainerTree fails
                        Logger.log("i", f"No quality_type filtering applied for '{qc_name}' (fallback mode)")
                    
                    if is_compatible:
                        quality_changes_containers.append(qc_container)
                        
                except Exception as qc_error:
                    Logger.log("w", f"Error checking quality_changes compatibility for {qc_container.getId()}: {qc_error}")
                    continue
            
            # Process found user-defined quality changes
            for quality_changes_container in quality_changes_containers:
                try:
                    quality_name = quality_changes_container.getName()
                    intent_category = quality_changes_container.getMetaDataEntry("intent_category", "default")
                    quality_type = quality_changes_container.getMetaDataEntry("quality_type", "normal")
                    
                    # Filter out unwanted profiles
                    if quality_name.lower() in ["empty", "not_supported"] or intent_category == "Not_Supported":
                        continue
                    
                    # Enhanced intent detection for quality changes
                    if intent_category == "default" or not intent_category:
                        # Try alternative metadata fields for intent
                        alt_intent = quality_changes_container.getMetaDataEntry("intent", "")
                        if alt_intent and alt_intent != "default":
                            intent_category = alt_intent
                        else:
                            intent_category = "default"
                                        
                    # Create a profile entry for quality changes (user-defined) - mark it clearly
                    profile_entry = {
                        'display_name': f"* {quality_name}",  # Add star to indicate user-defined
                        'container': quality_changes_container,
                        'intent': intent_category,
                        'quality_name': quality_name,
                        'quality_group': None,
                        'quality_type': quality_type,
                        'is_available': True,
                        'is_user_defined': True
                    }
                    
                    self._quality_profiles.append(profile_entry)
                    
                except Exception as profile_error:
                    Logger.log("w", f"Error processing quality changes container {quality_changes_container.getId()}: {profile_error}")
                    continue
            
            # Log filtering results
            if available_quality_types:
                total_quality_changes = len(all_quality_changes)
                filtered_quality_changes = len(quality_changes_containers)
                filtered_out_count = total_quality_changes - filtered_quality_changes
                if filtered_out_count > 0:
                    Logger.log("i", f"Quality changes filtering: {filtered_out_count} custom profiles filtered out due to nozzle/material incompatibility")
            
            # Fallback approach using container registry if the tree approach didn't find profiles
            if not self._quality_profiles:
                self._fallbackLoadQualityProfiles(application, machine_definition_id, global_stack)
            
            # Sort profiles by intent category, then quality name
            self._quality_profiles.sort(key=lambda x: (x['intent'], x['quality_name']))
            
            # Ensure we have default profiles - if no profiles have "default" intent, create them from existing profiles
            has_default_intent = any(profile['intent'] == 'default' for profile in self._quality_profiles)
            if not has_default_intent and self._quality_profiles:
                Logger.log("w", "No default intent profiles found, creating default entries from available profiles")
                # Group by quality type to create default profiles
                quality_types = {}
                for profile in self._quality_profiles:
                    quality_type = profile['quality_type']
                    if quality_type not in quality_types:
                        quality_types[quality_type] = profile
                
                # Create default intent versions of each quality type
                for quality_type, representative_profile in quality_types.items():
                    default_profile = {
                        'display_name': representative_profile['quality_name'],
                        'container': representative_profile['container'],
                        'intent': 'default',  # Force default intent
                        'quality_name': representative_profile['quality_name'],
                        'quality_group': representative_profile['quality_group'],
                        'quality_type': quality_type,
                        'is_available': True
                    }
                    self._quality_profiles.append(default_profile)
            
            # Summary
            base_profiles_count = len([p for p in self._quality_profiles if not p.get('is_user_defined', False)])
            custom_profiles_count = len([p for p in self._quality_profiles if p.get('is_user_defined', False)])
            self._logMessage(f"Loaded {len(self._quality_profiles)} quality profiles for current configuration.")
            self._logMessage(f"  - {base_profiles_count} machine profiles")
            self._logMessage(f"  - {custom_profiles_count} custom profiles (filtered by nozzle/material compatibility)")
            
            # Emit signal with loaded profiles
            self.qualityProfilesLoaded.emit(self._quality_profiles.copy())
            
            # Refresh notification for machine changes
            if hasattr(self, '_is_machine_change_refresh') and self._is_machine_change_refresh:
                self._logMessage("Quality profiles refreshed for new machine configuration.")
                self._is_machine_change_refresh = False
                    
        except Exception as main_error:
            Logger.log("e", f"Error loading quality profiles: {main_error}")
            self._logMessage("Failed to load quality profiles.", is_error=True)
            
            # Final fallback
            if not self._quality_profiles:
                try:
                    self._finalFallbackLoadQualityProfiles(CuraApplication.getInstance(), global_stack)
                except Exception as fallback_error:
                    Logger.log("e", f"Final fallback also failed: {fallback_error}")
                    self._logMessage("Could not load quality profiles.", is_error=True)
    
    def _fallbackLoadQualityProfiles(self, application, machine_definition_id, global_stack):
        """Fallback method to load quality profiles using container registry."""
        container_registry = application.getContainerRegistry()
        
        # Get all quality containers for this machine - try machine-specific first
        quality_containers = container_registry.findInstanceContainers(
            type="quality",
            definition=machine_definition_id
        )
        
        # Also get quality changes (user-defined profiles) - use proper Cura API
        all_quality_changes = container_registry.findInstanceContainers(type="quality_changes")
        quality_changes_containers = []
        
        # Build list of compatible definitions using proper inheritance chain
        compatible_definitions = self._buildCompatibleDefinitionsList(machine_definition_id, global_stack)
                        
        for qc_container in all_quality_changes:
            try:
                qc_definition = qc_container.getMetaDataEntry("definition", "unknown")
                qc_position = qc_container.getMetaDataEntry("position")
                                        
                # Skip if this is an extruder-specific container (we want global ones for now)
                if qc_position is not None:
                    continue
                    
                # Enhanced compatibility check using expanded definition list
                is_compatible = False
                
                # Check if the quality_changes definition matches any compatible definition
                if qc_definition in compatible_definitions:
                    is_compatible = True
                elif qc_definition == "unknown":
                    is_compatible = True

                if is_compatible:
                    quality_changes_containers.append(qc_container)
                    
            except Exception as qc_error:
                Logger.log("w", f"Error checking quality_changes compatibility for {qc_container.getId()}: {qc_error}")
                continue
        
        # Get intent containers for this machine
        intent_containers = container_registry.findInstanceContainers(
            type="intent",
            definition=machine_definition_id
        )
        
        # If no machine-specific profiles found, try to find inherited or compatible profiles
        if not quality_containers and not quality_changes_containers and not intent_containers:
            Logger.log("w", f"No containers found for {machine_definition_id}, trying broader search")
            
            # Try searching without definition filter and manually filter
            all_quality = container_registry.findInstanceContainers(type="quality")
            all_quality_changes = container_registry.findInstanceContainers(type="quality_changes")
            all_intents = container_registry.findInstanceContainers(type="intent")
            
            # Filter by definition metadata using proper inheritance check
            quality_containers = []
            quality_changes_containers = []
            intent_containers = []
            
            # Check each container for compatibility (handles inheritance)
            for container in all_quality:
                container_def = container.getMetaDataEntry("definition")
                if container_def in compatible_definitions:
                    quality_containers.append(container)
            
            # For quality_changes, use proper definition compatibility check
            for container in all_quality_changes:
                try:
                    # Skip extruder-specific containers
                    if container.getMetaDataEntry("position") is not None:
                        continue
                    # Check definition compatibility using inheritance chain
                    container_def = container.getMetaDataEntry("definition")
                    
                    if container_def in compatible_definitions:
                        quality_changes_containers.append(container)
                except Exception as container_error:
                    Logger.log("e", f"Error checking quality_changes container {container.getId()}: {container_error}")

            for container in all_intents:
                container_def = container.getMetaDataEntry("definition")
                if container_def in compatible_definitions:
                    intent_containers.append(container)
            
            # Only use fdmprinter as absolute last resort
            if not quality_containers and not quality_changes_containers and not intent_containers:
                Logger.log("w", f"No machine-specific profiles found for {machine_definition_id}, using fdmprinter as last resort")
                quality_containers = container_registry.findInstanceContainers(type="quality", definition="fdmprinter")
                intent_containers = container_registry.findInstanceContainers(type="intent", definition="fdmprinter")
                        
        # Process containers and create profiles
        self._processQualityContainers(quality_changes_containers, quality_containers, intent_containers, machine_definition_id)
    
    def _processQualityContainers(self, quality_changes_containers, quality_containers, intent_containers, machine_definition_id):
        """Process quality containers and create profile entries."""
        # Process user-defined quality changes first (highest priority)
        for quality_changes_container in quality_changes_containers:
            try:
                quality_name = quality_changes_container.getName()
                intent_category = quality_changes_container.getMetaDataEntry("intent_category", "default")
                quality_type = quality_changes_container.getMetaDataEntry("quality_type", "normal")
                
                # Enhanced intent detection for quality changes
                if intent_category == "default" or not intent_category:
                    # Try alternative metadata fields for intent
                    alt_intent = quality_changes_container.getMetaDataEntry("intent", "")
                    if alt_intent and alt_intent != "default":
                        intent_category = alt_intent
                    else:
                        intent_category = "default"
                
                # Create a profile entry for quality changes (user-defined) - mark it clearly
                profile_entry = {
                    'display_name': f"* {quality_name}",  # Add star to indicate user-defined
                    'container': quality_changes_container,
                    'intent': intent_category,
                    'quality_name': quality_name,
                    'quality_group': None,
                    'quality_type': quality_type,
                    'is_available': True,
                    'is_user_defined': True
                }
                
                self._quality_profiles.append(profile_entry)
                
            except Exception as profile_error:
                Logger.log("w", f"Error processing quality changes container {quality_changes_container.getId()}: {profile_error}")
                continue
        
        # Process quality containers second (machine-specific profiles)
        for quality_container in quality_containers:
            try:
                quality_name = quality_container.getName()
                intent_category = quality_container.getMetaDataEntry("intent_category", "default")
                quality_type = quality_container.getMetaDataEntry("quality_type", "normal")
                container_definition = quality_container.getMetaDataEntry("definition", "unknown")
                
                # Enhanced intent detection for quality containers
                if intent_category == "default" or not intent_category:
                    # Try alternative metadata fields for intent
                    alt_intent = quality_container.getMetaDataEntry("intent", "")
                    if alt_intent and alt_intent != "default":
                        intent_category = alt_intent
                    else:
                        intent_category = "default"
                
                # Mark if this is a machine-specific profile or generic
                is_machine_specific = container_definition == machine_definition_id
                profile_prefix = "[M] " if is_machine_specific and machine_definition_id != "fdmprinter" else ""
                                        
                # Create a profile entry
                profile_entry = {
                    'display_name': f"{profile_prefix}{quality_name}",
                    'container': quality_container,
                    'intent': intent_category,
                    'quality_name': quality_name,
                    'quality_group': None,
                    'quality_type': quality_type,
                    'is_available': True,
                    'is_user_defined': False,
                    'is_machine_specific': is_machine_specific
                }
                
                self._quality_profiles.append(profile_entry)
                
            except Exception as profile_error:
                Logger.log("w", f"Error processing quality container {quality_container.getId()}: {profile_error}")
                continue
        
        # Process intent containers third (intent-specific profiles)
        for intent_container in intent_containers:
            try:
                intent_name = intent_container.getName()
                intent_category = intent_container.getMetaDataEntry("intent_category", "default")
                quality_type = intent_container.getMetaDataEntry("quality_type", "normal")
                container_definition = intent_container.getMetaDataEntry("definition", "unknown")
                
                # Enhanced intent detection for intent containers
                if intent_category == "default" or not intent_category:
                    # Try alternative metadata fields for intent
                    alt_intent = intent_container.getMetaDataEntry("intent", "")
                    if alt_intent and alt_intent != "default":
                        intent_category = alt_intent
                    else:
                        intent_category = "default"
                
                # Mark if this is a machine-specific profile or generic
                is_machine_specific = container_definition == machine_definition_id
                profile_prefix = "[M] " if is_machine_specific and machine_definition_id != "fdmprinter" else "[I] "
                                        
                # Create a profile entry for intent
                profile_entry = {
                    'display_name': f"{profile_prefix}{intent_name}",
                    'container': intent_container,
                    'intent': intent_category,
                    'quality_name': intent_name,
                    'quality_group': None,
                    'quality_type': quality_type,
                    'is_available': True,
                    'is_user_defined': False,
                    'is_machine_specific': is_machine_specific
                }
                
                self._quality_profiles.append(profile_entry)
                
            except Exception as intent_error:
                Logger.log("w", f"Error processing intent container {intent_container.getId()}: {intent_error}")
                continue
    
    def _finalFallbackLoadQualityProfiles(self, application, global_stack):
        """Final fallback method to load any available quality profiles."""
        container_registry = application.getContainerRegistry()
        machine_definition_id = global_stack.definition.getId()
        
        Logger.log("w", f"No profiles loaded yet, trying final fallback for machine: {machine_definition_id}")
        
        # Get all quality containers for this machine - be more specific
        quality_containers = container_registry.findInstanceContainers(
            type="quality",
            definition=machine_definition_id
        )
        
        # Also get quality changes (user-defined profiles) - use machine manager compatibility
        all_quality_changes = container_registry.findInstanceContainers(type="quality_changes")
        quality_changes_containers = []
        
        for qc_container in all_quality_changes:
            try:
                # Skip extruder-specific containers
                if qc_container.getMetaDataEntry("position") is not None:
                    continue
                # Enhanced definition compatibility check
                container_def = qc_container.getMetaDataEntry("definition")
                
                # Build compatibility list using inheritance chain
                compatible_definitions = self._buildCompatibleDefinitionsList(machine_definition_id, global_stack)
                
                if container_def in compatible_definitions:
                    quality_changes_containers.append(qc_container)
            except Exception as fallback_error:
                Logger.log("e", f"Error checking fallback quality_changes container {qc_container.getId()}: {fallback_error}")

        # If still no machine-specific profiles, try broader search
        if not quality_containers and not quality_changes_containers:
            Logger.log("w", f"No machine-specific profiles found for {machine_definition_id}, trying broader search")
            
            # Try without definition filter for quality containers
            all_quality_containers = container_registry.findInstanceContainers(type="quality")
            quality_containers = [c for c in all_quality_containers if c.getMetaDataEntry("definition") == machine_definition_id]
            
            # Try without definition filter for quality changes - use definition check
            all_quality_changes = container_registry.findInstanceContainers(type="quality_changes")
            quality_changes_containers = []
            for qc_container in all_quality_changes:
                try:
                    # Skip extruder-specific containers
                    if qc_container.getMetaDataEntry("position") is not None:
                        continue
                    # Check definition compatibility
                    container_def = qc_container.getMetaDataEntry("definition")
                    
                    # Build compatibility list using inheritance chain
                    compatible_definitions = self._buildCompatibleDefinitionsList(machine_definition_id, global_stack)
                    
                    if container_def in compatible_definitions:
                        quality_changes_containers.append(qc_container)
                except Exception as broad_error:
                    Logger.log("e", f"Error checking broad search quality_changes container {qc_container.getId()}: {broad_error}")

            # If still nothing, try fdmprinter as last resort
            if not quality_containers and not quality_changes_containers:
                Logger.log("w", f"Still no profiles found, using fdmprinter as last resort")
                quality_containers = container_registry.findInstanceContainers(
                    type="quality",
                    definition="fdmprinter"
                )
        
        # Process final fallback containers
        self._processFinalFallbackContainers(quality_changes_containers, quality_containers)
    
    def _processFinalFallbackContainers(self, quality_changes_containers, quality_containers):
        """Process final fallback containers."""
        # Process user-defined quality changes first
        for quality_changes_container in quality_changes_containers:
            try:
                quality_name = quality_changes_container.getName()
                intent_category = quality_changes_container.getMetaDataEntry("intent_category", "default")
                quality_type = quality_changes_container.getMetaDataEntry("quality_type", "normal")
                
                # Enhanced intent detection - try multiple metadata fields
                if intent_category == "default" or not intent_category:
                    # Try alternative metadata fields for intent
                    alt_intent = quality_changes_container.getMetaDataEntry("intent", "")
                    if alt_intent and alt_intent != "default":
                        intent_category = alt_intent
                    else:
                        # Keep as default - it will be mapped to "Balanced" in the UI
                        intent_category = "default"
                
                # Create a profile entry for user-defined profiles
                profile_entry = {
                    'display_name': quality_name,
                    'container': quality_changes_container,
                    'intent': intent_category,
                    'quality_name': quality_name,
                    'quality_group': None,
                    'quality_type': quality_type,
                    'is_available': True,
                    'is_user_defined': True
                }
                
                self._quality_profiles.append(profile_entry)
                
            except Exception as profile_error:
                Logger.log("w", f"Error processing user-defined quality changes container {quality_changes_container.getId()}: {profile_error}")
                continue
        
        # Process quality containers
        for quality_container in quality_containers:
            try:
                quality_name = quality_container.getName()
                intent_category = quality_container.getMetaDataEntry("intent_category", "default")
                quality_type = quality_container.getMetaDataEntry("quality_type", "normal")
                
                # Enhanced intent detection - try multiple metadata fields
                if intent_category == "default" or not intent_category:
                    # Try alternative metadata fields for intent
                    alt_intent = quality_container.getMetaDataEntry("intent", "")
                    if alt_intent and alt_intent != "default":
                        intent_category = alt_intent
                    else:
                        # Keep as default - it will be mapped to "Balanced" in the UI
                        intent_category = "default"
                
                # Create a profile entry
                profile_entry = {
                    'display_name': quality_name,
                    'container': quality_container,
                    'intent': intent_category,
                    'quality_name': quality_name,
                    'quality_group': None,
                    'quality_type': quality_type,
                    'is_available': True,
                    'is_user_defined': False
                }
                
                self._quality_profiles.append(profile_entry)
                
            except Exception as profile_error:
                Logger.log("w", f"Error processing quality container {quality_container.getId()}: {profile_error}")
                continue
        
        # Sort profiles by quality name
        self._quality_profiles.sort(key=lambda x: x['quality_name'])
                    
        self._logMessage(f"Loaded {len(self._quality_profiles)} quality profiles for current configuration.")
        
        # Emit signal with loaded profiles
        self.qualityProfilesLoaded.emit(self._quality_profiles.copy())
