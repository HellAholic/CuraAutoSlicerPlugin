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

from UM.Backend.Backend import BackendState
from UM.Job import Job
from UM.Logger import Logger
from UM.Math.Vector import Vector
from UM.Math.Matrix import Matrix
from UM.Mesh.ReadMeshJob import ReadMeshJob
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Signal import Signal

from cura.CuraApplication import CuraApplication
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.ConvexHullDecorator import ConvexHullDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Utils.Threading import call_on_qt_thread
from cura.Machines.ContainerTree import ContainerTree

from .LocalFileOutputDevice import LocalFileOutputDevice

import time
import os
import csv
from datetime import datetime
from typing import Dict, Any
import shutil

class AutoSlicerJob(Job):
    """Background job for processing multiple 3D models through Cura's slicing pipeline."""
    
    statusChanged = Signal()
    fileError = Signal()  # Signal for individual file errors (filename, error_message)
    fileSkipped = Signal()  # Signal for individual file skips (filename, reason)
    skipRequested = Signal()  # Signal to request skipping current file
    
    statusChanged = Signal()

    def __init__(self, source_folder: str, destination_folder: str, max_files: int, file_profile_map: list, slice_timeout: int = 300) -> None:
        super().__init__()
        
        self._source_folder = source_folder
        self._destination_folder = destination_folder
        self._max_files = max_files
        self._file_profile_map = file_profile_map
        self._slice_timeout = slice_timeout  # User-configurable timeout
        
        self._model_list = []
        self._current_progress = 0
        self._current_model_index = 0
        self._current_model_path = ""  # Track current model being processed
        self._mesh_is_loading = False
        self._loaded_nodes = []
        self._is_stopping = False
        self._is_skipping = False  # Flag to skip current file
        self._last_output_path = ""
        self._results = {
            'success_count': 0,
            'error_count': 0,
            'processed_files': [],
            'error_files': [],
            'error_details': [],  # Store detailed error information
            'skipped_files': []  # Track skipped files
        }
        
        self._backend_state = BackendState.NotStarted
        self._previous_backend_state = BackendState.NotStarted
        self._slice_cancelled = False  # Flag to track slice cancellation
        self._application = CuraApplication.getInstance()
        self._machine_manager = self._application.getMachineManager()
        self._backend = self._application.getBackend()

        self._backend.backendStateChange.connect(self._onBackendStateChange)
        
        self._csv_file_path = os.path.join(destination_folder, "auto_slicer_progress.csv")
        
        self._original_quality_id = None
        self._original_quality_changes_id = None
        self._original_intent_category = None

    def _addError(self, filename: str, file_path: str, error_message: str):
        """Helper method to consistently record errors with details."""
        self._results['error_count'] += 1
        self._results['error_files'].append(filename)
        self._results['error_details'].append({
            'filename': filename,
            'error_message': error_message,
            'file_path': file_path
        })
        self._logToCSV(filename, file_path, self._last_output_path, "failed", error_message)
        
        # Emit signal for real-time error reporting
        self.fileError.emit(filename, error_message)

    def _onBackendStateChange(self, state):
        """Track backend state changes for slice monitoring and cancellation detection."""
        self._previous_backend_state = self._backend_state
        self._backend_state = state
        
        # Detect slice cancellation by Cura UI
        # When user cancels from Cura's UI during slicing, the state typically goes:
        # Processing -> NotStarted (or sometimes Processing -> Disabled)
        if (self._previous_backend_state == BackendState.Processing and 
            state in [BackendState.NotStarted, BackendState.Disabled]):
            
            # This indicates the slice was cancelled from Cura's UI
            self._slice_cancelled = True
            Logger.log("i", "Slice cancellation detected from Cura UI")
            
            # If we're currently in auto-slice mode, treat this as a skip request
            if not self._is_stopping and not self._is_skipping:
                self._is_skipping = True

    def stop(self):
        """Stop the processing job gracefully."""
        self._is_stopping = True
        self._slice_cancelled = False  # Reset cancellation flag when stopping
        
        # Cancel any ongoing slice operation
        try:
            backend = self._application.getBackend()
            if self._backend_state in [BackendState.Processing, BackendState.NotStarted]:
                backend.stopSlicing()
        except Exception as e:
            Logger.log("w", f"Error stopping slice: {e}")

    def skipCurrentFile(self):
        """Skip the current file being processed."""
        if not self._is_stopping:
            self._is_skipping = True
            self._slice_cancelled = False  # Reset cancellation flag when manually skipping
            
            # Cancel any ongoing slice operation
            try:
                backend = self._application.getBackend()
                if self._backend_state in [BackendState.Processing, BackendState.NotStarted]:
                    backend.stopSlicing()
            except Exception as e:
                Logger.log("w", f"Error stopping slice for skip: {e}")

    def run(self) -> None:
        """Main job execution method."""
        try:
            self._storeOriginalMachineState()
            
            # Initialize CSV file for logging
            self._writeCSVHeader()
            
            self.statusChanged.emit("Discovering files...")
            self._discoverFiles()
            
            if not self._model_list:
                self.statusChanged.emit("No valid files found to process")
                self._restoreOriginalMachineState()
                return
            
            total_models = len(self._file_profile_map)
            self.statusChanged.emit(f"Processing {total_models} files...")
            
            for index, item in enumerate(self._file_profile_map):                
                if self._is_stopping:
                    self.statusChanged.emit("Processing stopped by user")
                    Logger.log("i", "Processing stopped by user in main loop")
                    break
                
                model_filename = item["file"]
                profile_id = item["profile_id"]
                model_path = os.path.join(self._source_folder, model_filename)

                self._current_model_index = index
                progress = int((index / total_models) * 100)
                self.progress.emit(progress)
                
                self.statusChanged.emit(f"Processing {model_filename} ({index + 1}/{total_models})")
                
                intent_category = item.get("intent_category")
                intent_container_id = item.get("intent_container_id")
                if not self._switchQualityProfile(profile_id, intent_category, intent_container_id):
                    Logger.log("e", f"Failed to switch to profile {profile_id} (intent: {intent_category}) for {model_filename}")
                    continue
                
                self._processModel(model_path)
                        
            self.statusChanged.emit("Restoring original machine state...")
            self._restoreOriginalMachineState()
            
            # Validate and fix any machine state issues after restoration
            self._validateMachineState()
            
            self.progress.emit(100)
            self.statusChanged.emit(f"Completed processing {self._results['success_count']} files successfully")
            
        except Exception as e:
            Logger.logException("e", f"AutoSlicerJob failed: {str(e)}")
            self.statusChanged.emit(f"Job failed: {str(e)}")
            self._restoreOriginalMachineState()
            # Validate and fix any issues even after errors
            self._validateMachineState()
        finally:
            self._cleanup()

    def _discoverFiles(self):
        """Discover and filter STL/3MF files in the source folder."""
        if not os.path.exists(self._source_folder):
            raise FileNotFoundError(f"Source folder does not exist: {self._source_folder}")
        
        self._model_list = []
        
        for file_info in self._file_profile_map:
            filename = file_info['file']
            file_path = os.path.join(self._source_folder, filename)
            
            if os.path.exists(file_path):
                self._model_list.append(file_path)
            else:
                Logger.log("w", f"File not found: {file_path}")

    def _writeCSVHeader(self):
        """Write CSV header if file doesn't exist."""
        try:
            with open(self._csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['filename', 'source_path', 'ufp_path', 'status', 'timestamp', 'error_message']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
        except Exception as e:
            Logger.logException("e", f"Failed to create CSV file: {str(e)}")

    def _logToCSV(self, filename: str, source_path: str, ufp_path: str, status: str, error_message: str = ""):
        """Log processing result to CSV file."""
        try:
            with open(self._csv_file_path, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['filename', 'source_path', 'ufp_path', 'status', 'timestamp', 'error_message']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow({
                    'filename': filename,
                    'source_path': source_path,
                    'ufp_path': ufp_path,
                    'status': status,
                    'timestamp': datetime.now().isoformat(),
                    'error_message': error_message
                })
        except Exception as e:
            Logger.logException("e", f"Failed to write to CSV: {str(e)}")

    def _processModel(self, model_path: str):
        """Process a single 3D model through the complete pipeline."""
        model_filename = os.path.basename(model_path)
        self._last_output_path = ""

        try:
            self._clearBuildPlate()
            load_result = self._loadModel(model_path)
            if not load_result:
                Logger.log("e", f"Failed to load model {model_filename}")
                # Check if this was a user interruption
                if self._is_stopping:
                    raise Exception("Processing stopped by user")
                
                # Check for more specific load failure reasons
                file_size_mb = os.path.getsize(model_path) / (1024 * 1024)
                file_ext = os.path.splitext(model_path)[1].lower()
                
                if file_size_mb > 100:  # Large file
                    raise Exception(f"Failed to load model file (file size: {file_size_mb:.1f}MB). Large files may cause loading issues.")
                elif file_ext not in ['.stl', '.3mf', '.obj', '.ply']:  # Unsupported format
                    raise Exception(f"Failed to load model file. Unsupported file format: {file_ext}")
                else:
                    raise Exception(f"Failed to load model file. The file may be corrupted or contain invalid geometry.")
            
            # Skip positioning for 3MF files (UCP handles positioning)
            file_ext = os.path.splitext(model_path)[1].lower()
            if file_ext != '.3mf':
                self._positionModel()
            
            # Reset slice and skip flags before slicing
            self._is_skipping = False
            self._slice_cancelled = False
            
            if not self._sliceModel():
                Logger.log("e", f"Failed to slice model {model_filename}")
                # Check if this was a user interruption
                if self._is_stopping:
                    raise Exception("Processing stopped by user")
                elif self._is_skipping:
                    # File was skipped
                    filename = os.path.basename(model_path)
                    self._results['skipped_files'].append(filename)
                    self._logToCSV(filename, model_path, "", "skipped", "Skipped by user")
                    Logger.log("i", f"Skipped processing of {filename}")
                    
                    # Emit signal for real-time skip notification
                    self.fileSkipped.emit(filename, "Skipped by user")
                    return  # Skip to next file
                elif self._slice_cancelled:
                    # File was cancelled from Cura UI
                    filename = os.path.basename(model_path)
                    self._results['skipped_files'].append(filename)
                    self._logToCSV(filename, model_path, "", "skipped", "Cancelled from Cura UI")
                    Logger.log("i", f"Cancelled processing of {filename} from Cura UI")
                    
                    # Emit signal for real-time skip notification
                    self.fileSkipped.emit(filename, "Cancelled from Cura UI")
                    return  # Skip to next file
                else:
                    raise Exception("Failed to slice model. This could be due to invalid geometry, print settings issues, or insufficient memory.")
            
            # Check again after slicing in case user skipped or cancelled during slice
            if self._is_skipping:
                filename = os.path.basename(model_path)
                self._results['skipped_files'].append(filename)
                self._logToCSV(filename, model_path, "", "skipped", "Skipped by user")
                Logger.log("i", f"Skipped processing of {filename}")
                
                # Emit signal for real-time skip notification
                self.fileSkipped.emit(filename, "Skipped by user")
                return  # Skip to next file
            
            if self._slice_cancelled:
                filename = os.path.basename(model_path)
                self._results['skipped_files'].append(filename)
                self._logToCSV(filename, model_path, "", "skipped", "Cancelled from Cura UI")
                Logger.log("i", f"Cancelled processing of {filename} from Cura UI")
                
                # Emit signal for real-time skip notification
                self.fileSkipped.emit(filename, "Cancelled from Cura UI")
                return  # Skip to next file

            if not self._saveOutputFile(model_filename):
                Logger.log("e", f"Failed to save output file for {model_filename}")
                # Check if this was a user interruption
                if self._is_stopping:
                    raise Exception("Processing stopped by user")
                
                # Check for more specific save failure reasons
                dest_folder = self._destination_folder
                try:
                    # Check disk space
                    import shutil
                    free_space = shutil.disk_usage(dest_folder).free / (1024 * 1024)  # MB
                    if free_space < 100:  # Less than 100MB
                        raise Exception(f"Failed to save output file. Insufficient disk space (only {free_space:.1f}MB available).")
                    
                    # Check write permissions
                    test_file = os.path.join(dest_folder, "test_write_permission.tmp")
                    try:
                        with open(test_file, 'w') as f:
                            f.write("test")
                        os.remove(test_file)
                    except PermissionError:
                        raise Exception(f"Failed to save output file. No write permission to destination folder: {dest_folder}")
                    except Exception:
                        raise Exception(f"Failed to save output file. Cannot write to destination folder: {dest_folder}")
                    
                    # Generic save failure
                    raise Exception(f"Failed to save output file. The slicing process may have failed or the output format is not supported.")
                
                except Exception as check_error:
                    if "Failed to save output file" in str(check_error):
                        raise check_error
                    else:
                        raise Exception(f"Failed to save output file. {str(check_error)}")
            
            self._moveToSlicedFolder(model_path)
            self._logToCSV(model_filename, model_path, self._last_output_path, "completed")
            self._results['success_count'] += 1
            self._results['processed_files'].append(model_filename)
            
        except Exception as e:
            error_msg = str(e)
            
            # Special handling for user interruption - don't log as an error
            if "Processing stopped by user" in error_msg:
                Logger.log("i", f"Processing of {model_filename} stopped by user")
                # Don't add to error count for user interruptions
                return
            else:
                Logger.logException("e", f"Failed to process {model_filename}: {error_msg}")
                self._addError(model_filename, model_path, error_msg)

    @call_on_qt_thread
    def _clearBuildPlate(self):
        """Clear all objects from the build plate."""
        CuraApplication.getInstance().deleteAll()

    def _loadModel(self, model_path: str) -> bool:
        """Load a 3D model file and add it to the scene."""
        try:
            file_ext = os.path.splitext(model_path)[1].lower()
            
            # For 3MF files, use Cura's workspace loading system to preserve UCP data
            if file_ext == '.3mf':
                return self._load3MFWorkspace(model_path)
            else:
                # For other file types (STL, OBJ, etc.), use the mesh loading system
                return self._loadMeshFile(model_path)
                
        except Exception as e:
            Logger.logException("e", f"Error loading model {model_path}: {str(e)}")
            return False

    def _applyUcpPositioning(self, nodes):
        """Apply UCP-style positioning logic exactly like Cura's ThreeMFWorkspaceReader.
        
        This follows the exact pattern from Cura's read() method for UCP files.
        """
        try:
            from UM.Math.AxisAlignedBox import AxisAlignedBox
            
            if not nodes:
                return
            
            # Follow Cura's exact UCP positioning logic from ThreeMFWorkspaceReader
            # Calculate combined extents of all nodes
            full_extents = None
            for node in nodes:
                if node and hasattr(node, 'getMeshData') and node.getMeshData():
                    extents = node.getMeshData().getExtents()
                    if extents is not None:
                        pos = node.getPosition()
                        node_box = AxisAlignedBox(extents.minimum + pos, extents.maximum + pos)
                        if full_extents is None:
                            full_extents = node_box
                        else:
                            full_extents = full_extents + node_box
            
            # Apply Cura's UCP centering logic
            if full_extents and full_extents.isValid():
                # Center on X and Z, preserve Y - exactly like Cura's UCP logic
                for node in nodes:
                    if node and hasattr(node, 'getPosition'):
                        pos = node.getPosition()
                        # Apply Cura's exact formula: pos.x - full_extents.center.x
                        new_pos = Vector(pos.x - full_extents.center.x, pos.y, pos.z - full_extents.center.z)
                        node.setPosition(new_pos)
            else:
                Logger.log("w", "Could not calculate valid extents for UCP positioning")
                
        except Exception as e:
            Logger.logException("e", f"Error applying UCP positioning: {str(e)}")
            # Don't fail the whole operation if positioning fails

    def _load3MFWorkspace(self, model_path: str) -> bool:
        """Load 3MF file using ReadMeshJob with UCP positioning logic."""
        try:
            self._clearBuildPlate()
            
            # Use ReadMeshJob to load the 3MF file (same as STL loading but with different positioning)
            self._mesh_is_loading = True
            self._loaded_nodes = []
            self._current_model_path = model_path
            
            job = ReadMeshJob(model_path)
            job.finished.connect(self._read3MFFinished)
            job.start()
            
            timeout = 30
            start_time = time.time()
            
            while self._mesh_is_loading and not self._is_stopping:
                if time.time() - start_time > timeout:
                    Logger.log("e", f"Timeout loading 3MF model: {model_path}")
                    return False
                time.sleep(0.1)
            
            if not self._loaded_nodes:
                Logger.log("e", f"No nodes loaded from 3MF file: {model_path}")
                return False
            
            return len(self._loaded_nodes) > 0
            
        except Exception as e:
            Logger.logException("e", f"Error loading 3MF file {model_path}: {str(e)}")
            return False

    def _loadMeshFile(self, model_path: str) -> bool:
        """Load mesh files (STL, etc.) using the traditional mesh loading system."""
        try:
            self._mesh_is_loading = True
            self._loaded_nodes = []
            self._current_model_path = model_path  # Store for use in _readMeshFinished
            
            job = ReadMeshJob(model_path)
            job.finished.connect(self._readMeshFinished)
            job.start()
            
            timeout = 30
            start_time = time.time()
            
            while self._mesh_is_loading and not self._is_stopping:
                if time.time() - start_time > timeout:
                    Logger.log("e", f"Timeout loading model: {model_path}")
                    return False
                time.sleep(0.1)
            
            if not self._loaded_nodes:
                Logger.log("e", f"No nodes loaded from: {model_path}")
                return False
                
            return True
            
        except Exception as e:
            Logger.logException("e", f"Error loading mesh file {model_path}: {str(e)}")
            return False

    @call_on_qt_thread
    def _read3MFFinished(self, job):
        """Handle 3MF mesh loading completion with proper UCP positioning logic.
        
        This follows the same pattern as Cura's ThreeMFWorkspaceReader for loading 3MF files.
        """
        try:
            self._loaded_nodes = []
            
            nodes = job.getResult()
            if not nodes:
                Logger.log("e", "ReadMeshJob returned no nodes for 3MF file")
                return
            
            # Process nodes similar to regular mesh loading but with UCP positioning
            scene = CuraApplication.getInstance().getController().getScene()
            extruder_manager = CuraApplication.getInstance().getExtruderManager()
            
            try:
                default_extruder_id = extruder_manager.getActiveExtruderStack().getId()
            except:
                Logger.log("w", "No active extruder found, using None")
                default_extruder_id = None
            
            # Helper function to recursively process grouped nodes (following Cura's approach)
            def process_node_recursively(node, parent_transformation=None):
                """Process a node and its children recursively to handle grouped models."""
                processed_nodes = []
                
                if not node:
                    return processed_nodes
                
                # Get node's transformation
                if hasattr(node, 'getLocalTransformation'):
                    node_transformation = node.getLocalTransformation()
                else:
                    node_transformation = Matrix()
                
                if parent_transformation:
                    combined_transformation = parent_transformation.multiply(node_transformation, copy=True)
                else:
                    combined_transformation = node_transformation
                
                # If this node has mesh data, create a scene node for it
                if hasattr(node, 'getMeshData') and node.getMeshData():
                    scene_node = CuraSceneNode()
                    scene_node.setMeshData(node.getMeshData())
                    
                    # Apply the combined transformation
                    try:
                        scene_node.setTransformation(combined_transformation)
                    except Exception as transform_error:
                        Logger.log("w", f"Error applying transformation to grouped node: {transform_error}")
                        # Fallback to individual components
                        try:
                            scene_node.setPosition(node.getPosition())
                            if hasattr(node, 'getOrientation'):
                                scene_node.setOrientation(node.getOrientation())
                            if hasattr(node, 'getScale'):
                                scene_node.setScale(node.getScale())
                        except:
                            pass
                    
                    # Set node name
                    node_name = node.getName() if hasattr(node, 'getName') and node.getName() else ""
                    if not node_name:
                        if hasattr(self, '_current_model_path') and self._current_model_path:
                            base_name = os.path.splitext(os.path.basename(self._current_model_path))[0]
                            node_name = f"{base_name}_part_{len(self._loaded_nodes) + len(processed_nodes) + 1}"
                        else:
                            node_name = f"Model_part_{len(self._loaded_nodes) + len(processed_nodes) + 1}"
                    
                    # Ensure name has extension
                    if not os.path.splitext(node_name)[1]:
                        if hasattr(self, '_current_model_path') and self._current_model_path:
                            original_ext = os.path.splitext(self._current_model_path)[1]
                            node_name = node_name + (original_ext if original_ext else ".3mf")
                        else:
                            node_name = node_name + ".3mf"
                    
                    scene_node.setName(node_name)
                    scene_node.setSelectable(True)
                    
                    # Add decorators
                    scene_node.addDecorator(SliceableObjectDecorator())
                    scene_node.addDecorator(ConvexHullDecorator())
                    scene_node.addDecorator(BuildPlateDecorator(0))
                    
                    if default_extruder_id:
                        scene_node.callDecoration("setActiveExtruder", default_extruder_id)
                    
                    processed_nodes.append(scene_node)
                
                # Process children recursively (for grouped models)
                if hasattr(node, 'getChildren') and node.getChildren():
                    for child in node.getChildren():
                        child_nodes = process_node_recursively(child, combined_transformation)
                        processed_nodes.extend(child_nodes)
                
                return processed_nodes
            
            # Process all nodes (including grouped ones)
            all_scene_nodes = []
            for node in nodes:
                scene_nodes = process_node_recursively(node)
                all_scene_nodes.extend(scene_nodes)
            
            # Add all processed nodes to the scene
            for scene_node in all_scene_nodes:
                op = AddSceneNodeOperation(scene_node, scene.getRoot())
                op.push()
                self._loaded_nodes.append(scene_node)
            
            if self._loaded_nodes:
                self._applyUcpPositioning(self._loaded_nodes)
            
        except Exception as e:
            Logger.logException("e", f"Error in _read3MFFinished: {str(e)}")
        finally:
            self._mesh_is_loading = False

    @call_on_qt_thread
    def _readMeshFinished(self, job):
        """Handle mesh loading completion."""
        try:
            self._loaded_nodes = []
            
            nodes = job.getResult()
            if nodes:
                scene = CuraApplication.getInstance().getController().getScene()
                extruder_manager = CuraApplication.getInstance().getExtruderManager()
                default_extruder_id = extruder_manager.getActiveExtruderStack().getId()
                
                for node in nodes:
                    if node and hasattr(node, 'getMeshData') and node.getMeshData():
                        scene_node = CuraSceneNode()
                        scene_node.setMeshData(node.getMeshData())
                        
                        try:
                            scene_node.setPosition(node.getPosition())
                            
                            if hasattr(node, 'getLocalTransformation'):
                                scene_node.setTransformation(node.getLocalTransformation())
                            else:
                                if hasattr(node, 'getOrientation'):
                                    scene_node.setOrientation(node.getOrientation())
                                if hasattr(node, 'getScale'):
                                    scene_node.setScale(node.getScale())
                        except AttributeError:
                            Logger.log("w", "Node transformation methods not available for mesh file")
                        except Exception as transform_error:
                            Logger.log("w", f"Error copying mesh node transformations: {transform_error}")
                        
                        # Set node name to avoid MIME type warnings
                        node_name = node.getName()
                        if not node_name:
                            if hasattr(self, '_current_model_path') and self._current_model_path:
                                node_name = os.path.splitext(os.path.basename(self._current_model_path))[0]
                            else:
                                node_name = "Model"
                        
                        # Ensure name has extension
                        if not os.path.splitext(node_name)[1]:
                            if hasattr(self, '_current_model_path') and self._current_model_path:
                                original_ext = os.path.splitext(self._current_model_path)[1]
                                node_name = node_name + (original_ext if original_ext else ".stl")
                            else:
                                node_name = node_name + ".stl"
                        
                        scene_node.setName(node_name)
                        scene_node.setSelectable(True)
                        
                        scene_node.addDecorator(SliceableObjectDecorator())
                        scene_node.addDecorator(ConvexHullDecorator())
                        scene_node.addDecorator(BuildPlateDecorator(0))
                        scene_node.callDecoration("setActiveExtruder", default_extruder_id)
                        
                        # Auto-center on Y-axis (place on build plate)
                        if scene_node.getBoundingBox():
                            center_y = scene_node.getWorldPosition().y - scene_node.getBoundingBox().bottom
                            scene_node.translate(Vector(0, center_y, 0))
                        
                        # Add to scene
                        op = AddSceneNodeOperation(scene_node, scene.getRoot())
                        op.push()
                        
                        self._loaded_nodes.append(scene_node)
            else:
                Logger.log("e", "ReadMeshJob returned no nodes")
                
        except Exception as e:
            Logger.logException("e", f"Error in _readMeshFinished: {str(e)}")
        finally:
            self._mesh_is_loading = False

    @call_on_qt_thread
    def _positionModel(self):
        """Use Cura's built-in positioning logic for non-3MF file types."""
        try:
            if not self._loaded_nodes:
                return
            
            # Skip positioning for 3MF files (handled by UCP logic)
            file_ext = ""
            if hasattr(self, '_current_model_path') and self._current_model_path:
                file_ext = os.path.splitext(self._current_model_path)[1].lower()
            
            if file_ext == '.3mf':
                return
            
            # Use Cura's arrange functionality for other file types
            application = CuraApplication.getInstance()
            
            try:
                from cura.Arranging.Arrange import Arrange
                arrange = Arrange.create(scene_root=application.getController().getScene().getRoot())
                arrange.arrange()
            except Exception:
                # Fallback: Use scene manipulation
                try:
                    scene = application.getController().getScene()
                    if hasattr(scene, 'arrange'):
                        scene.arrange()
                except Exception:
                    pass  # Preserve original positioning
                    
        except Exception as e:
            Logger.logException("e", f"Error in _positionModel: {str(e)}")

    def _sliceModel(self) -> bool:
        """Slice the loaded model."""
        try:
            backend = CuraApplication.getInstance().getBackend()
            
            # Check what's on the build plate
            scene = CuraApplication.getInstance().getController().getScene()
            all_nodes = []
            sliceable_nodes = []
            
            def collect_nodes(node):
                all_nodes.append(node)
                if hasattr(node, 'callDecoration') and node.callDecoration("isSliceable"):
                    sliceable_nodes.append(node)
                for child in node.getChildren():
                    collect_nodes(child)
            
            collect_nodes(scene.getRoot())
            
            if not backend.hasSlicableObject():
                Logger.log("e", "No sliceable objects found on build plate")
                return False
            
            backend.forceSlice()
            
            # Wait for slice to start
            timeout = 10
            start_time = time.time()
            while self._backend_state == BackendState.NotStarted and not self._is_stopping:
                if time.time() - start_time > timeout:
                    Logger.log("e", "Timeout waiting for slice to start")
                    return False
                time.sleep(0.1)
            
            if self._is_stopping:
                raise Exception("Processing stopped by user")
            
            # Wait for slice to complete
            timeout = self._slice_timeout  # Use user-configurable timeout
            self.statusChanged.emit(f"Slicing with timeout of {timeout} seconds...")
            start_time = time.time()
            
            while self._backend_state != BackendState.Done and not self._is_stopping:
                # Check for user skip request
                if self._is_skipping:
                    Logger.log("i", "Slice was skipped by user")
                    return False
                
                # Check for Cura UI cancellation
                if self._slice_cancelled:
                    Logger.log("i", "Slice was cancelled from Cura UI")
                    return False
                
                if self._backend_state == BackendState.Error:
                    Logger.log("e", "Slicing failed with error state")
                    return False
                
                if time.time() - start_time > timeout:
                    Logger.log("e", "Slicing timeout")
                    return False
                
                time.sleep(0.5)
            
            if self._is_stopping:
                raise Exception("Processing stopped by user")
            
            # Check one more time for skip or cancellation before declaring success
            if self._is_skipping:
                Logger.log("i", "Slice was skipped by user after completion")
                return False
            
            if self._slice_cancelled:
                Logger.log("i", "Slice was cancelled from Cura UI after completion")
                return False
            
            return self._backend_state == BackendState.Done
            
        except Exception as e:
            Logger.logException("e", f"Error during slicing: {str(e)}")
            return False

    def _saveOutputFile(self, model_filename: str) -> bool:
        """Save the sliced model using LocalFileOutputDevice following the exact pattern from RemovableDriveOutputDevice."""
        try:
            base_name = os.path.splitext(model_filename)[0]
            
            # Add timestamp to filename in format YYYYMMDD_HH_MM
            timestamp = datetime.now().strftime("%Y%m%d_%H_%M")
            base_name_with_timestamp = f"{base_name}_{timestamp}"
            
            # Get sliceable nodes from the scene
            scene = self._application.getController().getScene()
            nodes = []
            for node in scene.getRoot().getAllChildren():
                if hasattr(node, 'callDecoration') and node.callDecoration("isSliceable"):
                    nodes.append(node)
            
            if not nodes:
                Logger.log("e", "No sliceable nodes found in scene")
                return False

            # Create LocalFileOutputDevice and use it exactly like RemovableDriveOutputDevice
            device_id = f"local_file_{id(self)}"  # Unique device ID
            local_device = LocalFileOutputDevice(device_id, self._destination_folder)
            
            # Track write completion
            self._write_completed = False
            self._write_error = None
            
            def on_write_success(device):
                self._write_completed = True
                self._write_error = None
            
            def on_write_error(device):
                self._write_completed = True
                self._write_error = "Write operation failed"
                Logger.log("e", "Write operation failed")
            
            def on_write_finished(device):
                self._write_completed = True
            
            # Connect to the device signals
            local_device.writeSuccess.connect(on_write_success)
            local_device.writeError.connect(on_write_error)
            local_device.writeFinished.connect(on_write_finished)
            
            # Use the device to write the file, following exact RemovableDriveOutputDevice pattern
            try:
                local_device.requestWrite(nodes, file_name=base_name_with_timestamp)
                
                # Wait for the write operation to complete
                timeout = 60  # 60 seconds timeout
                start_time = time.time()
                
                while not self._write_completed and not self._is_stopping:
                    if time.time() - start_time > timeout:
                        Logger.log("e", f"Timeout waiting for file write to complete")
                        return False
                    time.sleep(0.1)
                
                if self._is_stopping:
                    raise Exception("Processing stopped by user")
                
                if self._write_error:
                    Logger.log("e", f"Write operation failed: {self._write_error}")
                    return False
                
                # Get the output path from the device (it constructs the full path)
                extension = ""
                file_formats = self._application.getMeshFileHandler().getSupportedFileTypesWrite()
                if file_formats:
                    container = self._application.getGlobalContainerStack().findContainer({"file_formats": "*"})
                    if container:
                        machine_file_formats = [file_type.strip() for file_type in container.getMetaDataEntry("file_formats").split(";")]
                        format_by_mimetype = {format["mime_type"]: format for format in file_formats}
                        filtered_formats = [format_by_mimetype[mimetype] for mimetype in machine_file_formats if mimetype in format_by_mimetype]
                        if filtered_formats:
                            # Apply same logic as LocalFileOutputDevice: prefer uncompressed G-code if available
                            preferred_format = filtered_formats[0]
                            if (preferred_format["mime_type"] == "application/gzip" and 
                                any(fmt["mime_type"] == "text/x-gcode" for fmt in filtered_formats)):
                                preferred_format = next(fmt for fmt in filtered_formats if fmt["mime_type"] == "text/x-gcode")
                            
                            extension = preferred_format["extension"]
                            if extension and not extension.startswith("."):
                                extension = "." + extension
                
                expected_output_path = os.path.join(self._destination_folder, base_name_with_timestamp + extension)
                self._last_output_path = expected_output_path
                
                # Verify the file was created and has reasonable size
                if os.path.exists(expected_output_path):
                    file_size = os.path.getsize(expected_output_path)
                    min_size_threshold = 20 * 1024  # 20 KB minimum
                    
                    if file_size >= min_size_threshold:
                        return True
                    else:
                        size_kb = file_size / 1024
                        Logger.log("e", f"Output file seems too small: {size_kb:.1f} KB (minimum: 20 KB) - likely incomplete")
                        try:
                            os.remove(expected_output_path)  # Clean up incomplete file
                        except Exception:
                            pass
                        return False
                else:
                    Logger.log("e", f"Output file was not created: {expected_output_path}")
                    return False
                    
            except Exception as device_error:
                Logger.logException("e", f"Error using LocalFileOutputDevice: {str(device_error)}")
                return False

        except Exception as e:
            Logger.logException("e", f"Error saving output file: {str(e)}")
            return False

    def _switchQualityProfile(self, profile_id: str, intent_category: str = None, intent_container_id: str = None) -> bool:
        """Switch to the specified quality profile using Cura's high-level group management API."""
        try:
            machine_manager = self._machine_manager
            if not machine_manager:
                Logger.log("e", "No machine manager found")
                return False
            
            container_registry = self._application.getContainerRegistry()
            
            # Check if it's a quality_changes (custom profile)
            quality_changes_containers = container_registry.findInstanceContainers(type="quality_changes", id=profile_id)
            if quality_changes_containers:
                # For custom profiles, find the quality changes group
                quality_changes = quality_changes_containers[0]
                
                # Get the container tree to find the quality changes group
                container_tree = ContainerTree.getInstance()
                
                # Find the quality changes group for this profile
                quality_changes_groups = container_tree.getCurrentQualityChangesGroups()
                target_group = None
                
                for group in quality_changes_groups:
                    if hasattr(group, 'name') and group.name == quality_changes.getName():
                        target_group = group
                        break
                    # Also check if the group contains our target container
                    if hasattr(group, 'quality_changes_containers'):
                        for container in group.quality_changes_containers.values():
                            if container and container.getId() == profile_id:
                                target_group = group
                                break
                
                if target_group:
                    # Use the high-level group method
                    machine_manager.setQualityChangesGroup(target_group, no_dialog=True)
                else:
                    # Fallback to direct setting
                    active_machine = machine_manager.activeMachine
                    if active_machine:
                        active_machine.setQualityChanges(quality_changes)
                    else:
                        Logger.log("e", "No active machine for fallback")
                        return False
            else:
                # Check if it's a base quality profile
                quality_containers = container_registry.findInstanceContainers(type="quality", id=profile_id)
                if quality_containers:
                    quality = quality_containers[0]
                    
                    # Get the container tree to find the quality group
                    container_tree = ContainerTree.getInstance()
                    
                    # Find the quality group for this profile
                    quality_groups = container_tree.getCurrentQualityGroups()
                    target_group = None
                    
                    for group_name, group in quality_groups.items():
                        if hasattr(group, 'quality_type') and group.quality_type == quality.getMetaDataEntry("quality_type"):
                            target_group = group
                            break
                    
                    if target_group:
                        # Use the high-level group method
                        machine_manager.setQualityGroup(target_group, no_dialog=True, global_stack=None)
                    else:
                        # Fallback to direct setting
                        active_machine = machine_manager.activeMachine
                        if active_machine:
                            active_machine.setQuality(quality)
                            
                            # Clear any existing quality_changes
                            empty_quality_changes = container_registry.findInstanceContainers(
                                type="quality_changes", 
                                name="empty"
                            )
                            if empty_quality_changes:
                                active_machine.setQualityChanges(empty_quality_changes[0])
                        else:
                            Logger.log("e", "No active machine for fallback")
                            return False
                else:
                    Logger.log("e", f"Profile not found: {profile_id}")
                    return False
            
            # Set intent if specified
            if intent_category:
                try:
                    machine_manager.setIntentByCategory(intent_category)
                except Exception as intent_error:
                    Logger.log("w", f"Failed to set intent {intent_category}: {intent_error}")
            
            # Give Cura time to process the changes and update the UI
            time.sleep(0.2)
            
            return True
                
        except Exception as e:
            Logger.logException("e", f"Error switching quality profile: {str(e)}")
            return False

    def _storeOriginalMachineState(self):
        """Store the original machine state to restore later."""
        try:
            active_machine = self._machine_manager.activeMachine
            if active_machine:
                # Store the original state with validation
                quality_id = active_machine.quality.getId()
                quality_changes_id = active_machine.qualityChanges.getId()
                intent_category = self._machine_manager.activeIntentCategory
                
                # Validate and store the IDs
                self._original_quality_id = quality_id if quality_id and quality_id.lower() not in ["none", ""] else None
                self._original_quality_changes_id = quality_changes_id if quality_changes_id and quality_changes_id.lower() not in ["none", ""] else None
                self._original_intent_category = intent_category
                
                # If quality_changes_id is "not_supported", store as None to prevent restoration issues
                if self._original_quality_changes_id and self._original_quality_changes_id.lower() == "not_supported":
                    self._original_quality_changes_id = None
                    
            else:
                Logger.log("w", "No active machine found when storing original state")
                self._original_quality_id = None
                self._original_quality_changes_id = None
                self._original_intent_category = None
        except Exception as e:
            Logger.logException("e", f"Error storing original machine state: {str(e)}")
            # Initialize to safe defaults
            self._original_quality_id = None
            self._original_quality_changes_id = None
            self._original_intent_category = None

    def _restoreOriginalMachineState(self):
        """Restore the original machine state after processing using the correct Cura API."""
        try:
            machine_manager = self._machine_manager
            if not machine_manager:
                Logger.log("w", "No machine manager found for restoration")
                return
            
            active_machine = machine_manager.activeMachine
            if not active_machine:
                Logger.log("w", "No active machine found for restoration")
                return
            
            # Determine which profile to restore - prioritize quality_changes over base quality
            if (self._original_quality_changes_id and 
                self._original_quality_changes_id.lower() not in ["empty", "not_supported", "none"]):
                
                # Try to restore custom profile using the working method
                success = self._switchQualityProfile(self._original_quality_changes_id, self._original_intent_category)
                if success:
                    Logger.log("i", f"Restored original custom profile: {self._original_quality_changes_id}")
                else:
                    Logger.log("w", "Failed to restore custom profile, trying base quality")
                    if self._original_quality_id:
                        self._restoreBaseQuality()
                        
            elif self._original_quality_id and self._original_quality_id.lower() not in ["empty", "not_supported", "none"]:
                self._restoreBaseQuality()
            else:
                Logger.log("w", "No valid original profile to restore")
                
            # Restore intent if specified
            if self._original_intent_category:
                try:
                    machine_manager.setIntentByCategory(self._original_intent_category)
                    Logger.log("i", f"Restored original intent: {self._original_intent_category}")
                except Exception as intent_error:
                    Logger.log("w", f"Failed to restore intent: {intent_error}")
                
        except Exception as e:
            Logger.logException("e", f"Error restoring original machine state: {str(e)}")
            # Try to clear problematic states as fallback
            try:
                self._clearQualityChanges()
            except Exception as fallback_error:
                Logger.log("w", f"Fallback quality changes clearing also failed: {fallback_error}")

    def _restoreBaseQuality(self):
        """Restore base quality profile using the correct API."""
        try:
            success = self._switchQualityProfile(self._original_quality_id, self._original_intent_category)
            if success:
                Logger.log("i", f"Restored original base quality: {self._original_quality_id}")
            else:
                Logger.log("w", "Failed to restore original quality profile")
        except Exception as q_error:
            Logger.log("w", f"Failed to restore quality: {q_error}")

    def _restoreProfileWithUserSettings(self, profile_id: str, intent_category: str = None) -> bool:
        """Restore a profile while preserving and restoring original user settings."""
        try:
            container_registry = self._application.getContainerRegistry()
            active_machine = self._machine_manager.activeMachine
            
            if not active_machine:
                Logger.log("e", "No active machine found for profile restoration")
                return False
            
            # Find the profile to restore
            quality_containers = container_registry.findInstanceContainers(type="quality", id=profile_id)
            quality_changes_containers = container_registry.findInstanceContainers(type="quality_changes", id=profile_id)
            
            target_container = None
            container_type = None
            
            if quality_containers:
                target_container = quality_containers[0]
                container_type = "quality"
            elif quality_changes_containers:
                target_container = quality_changes_containers[0]
                container_type = "quality_changes"
            else:
                Logger.log("e", f"Profile not found for restoration: {profile_id}")
                return False
            
            # Restore the profile
            if container_type == "quality_changes":
                # For quality_changes, we need to find and set the appropriate base quality
                quality_type = target_container.getMetaDataEntry("quality_type", "default")
                
                # Find compatible base quality
                base_quality_containers = container_registry.findInstanceContainers(
                    type="quality",
                    quality_type=quality_type
                )
                
                # Use inheritance-aware matching
                machine_definition_id = active_machine.definition.getId()
                compatible_definitions = [machine_definition_id]
                
                # Add inherited definitions
                inherited_from = active_machine.definition.getMetaDataEntry("inherits", "")
                if inherited_from:
                    compatible_definitions.append(inherited_from)
                
                quality_definition = active_machine.definition.getMetaDataEntry("quality_definition", machine_definition_id)
                if quality_definition and quality_definition not in compatible_definitions:
                    compatible_definitions.append(quality_definition)
                
                compatible_base = None
                for base_quality in base_quality_containers:
                    base_definition = base_quality.getMetaDataEntry("definition", "")
                    if base_definition in compatible_definitions:
                        compatible_base = base_quality
                        break
                
                if not compatible_base and base_quality_containers:
                    compatible_base = base_quality_containers[0]
                
                if compatible_base:
                    active_machine.setQuality(compatible_base)
                    active_machine.setQualityChanges(target_container)
                else:
                    Logger.log("e", f"No compatible base quality found for restoration")
                    return False
            else:
                # For base quality profiles, set the quality and clear quality_changes
                active_machine.setQuality(target_container)
                
                # Clear quality_changes
                empty_quality_changes = container_registry.findInstanceContainers(
                    type="quality_changes", 
                    name="empty"
                )
                if empty_quality_changes:
                    active_machine.setQualityChanges(empty_quality_changes[0])
            
            # Set intent if specified
            if intent_category:
                try:
                    self._machine_manager.setIntentByCategory(intent_category)
                except Exception as intent_error:
                    Logger.log("w", f"Failed to restore intent category {intent_category}: {intent_error}")
            
            # Restore original user setting overrides
            self._restoreUserSettingOverrides()
            
            # Trigger settings refresh
            try:
                backend = self._application.getBackend()
                if backend and hasattr(backend, 'settingsChanged'):
                    backend.settingsChanged.emit()
            except Exception as refresh_error:
                Logger.log("w", f"Failed to refresh settings during restoration: {refresh_error}")
            
            return True
            
        except Exception as e:
            Logger.logException("e", f"Error in profile restoration with user settings: {str(e)}")
            return False

    def _clearQualityChanges(self):
        """Clear quality changes to prevent 'not_supported' profile issues."""
        try:
            container_registry = self._application.getContainerRegistry()
            active_machine = self._machine_manager.activeMachine
            
            if active_machine:
                # Find and set empty quality changes for global container
                empty_quality_changes = container_registry.findInstanceContainers(
                    type="quality_changes", 
                    name="empty"
                )
                if empty_quality_changes:
                    active_machine.setQualityChanges(empty_quality_changes[0])
                    Logger.log("i", "Cleared global quality changes to prevent profile issues")
                
                # Also clear quality changes for all extruders to prevent extruder errors
                for extruder_index, extruder in enumerate(active_machine.extruderList):
                    try:
                        # Find empty quality changes for this extruder
                        extruder_empty_quality_changes = container_registry.findInstanceContainers(
                            type="quality_changes",
                            name="empty",
                            extruder=str(extruder_index)
                        )
                        
                        if not extruder_empty_quality_changes:
                            # Fallback to generic empty quality changes
                            extruder_empty_quality_changes = empty_quality_changes
                        
                        if extruder_empty_quality_changes:
                            extruder.setQualityChanges(extruder_empty_quality_changes[0])
                            Logger.log("d", f"Cleared quality changes for extruder {extruder_index}")
                    except Exception as extruder_error:
                        Logger.log("w", f"Failed to clear quality changes for extruder {extruder_index}: {extruder_error}")
                
                # Trigger settings refresh to update UI
                try:
                    backend = self._application.getBackend()
                    if backend and hasattr(backend, 'settingsChanged'):
                        backend.settingsChanged.emit()
                except Exception as refresh_error:
                    Logger.log("w", f"Failed to refresh settings after clearing quality changes: {refresh_error}")
                
            else:
                Logger.log("w", "Could not find active machine to clear quality changes")
        except Exception as e:
            Logger.log("w", f"Failed to clear quality changes: {e}")

    def _validateMachineState(self):
        """Validate the current machine state and fix common issues."""
        try:
            active_machine = self._machine_manager.activeMachine
            if not active_machine:
                Logger.log("w", "No active machine found for validation")
                return False
            
            # Check if quality_changes are in a problematic state
            quality_changes = active_machine.qualityChanges
            if quality_changes:
                quality_changes_name = quality_changes.getName().lower()
                if quality_changes_name in ["not_supported", "not supported"]:
                    Logger.log("w", "Detected 'not_supported' quality changes, clearing...")
                    self._clearQualityChanges()
            
            # Validate extruder states
            for extruder_index, extruder in enumerate(active_machine.extruderList):
                try:
                    extruder_quality_changes = extruder.qualityChanges
                    if extruder_quality_changes:
                        extruder_qc_name = extruder_quality_changes.getName().lower()
                        if extruder_qc_name in ["not_supported", "not supported"]:
                            Logger.log("w", f"Detected 'not_supported' quality changes for extruder {extruder_index}, clearing...")
                            
                            # Find and set empty quality changes for this specific extruder
                            container_registry = self._application.getContainerRegistry()
                            empty_quality_changes = container_registry.findInstanceContainers(
                                type="quality_changes", 
                                name="empty"
                            )
                            if empty_quality_changes:
                                extruder.setQualityChanges(empty_quality_changes[0])
                                Logger.log("d", f"Fixed extruder {extruder_index} quality changes")
                except Exception as extruder_error:
                    Logger.log("w", f"Error validating extruder {extruder_index}: {extruder_error}")
            
            return True
            
        except Exception as e:
            Logger.logException("e", f"Error validating machine state: {str(e)}")
            return False

    def _moveToSlicedFolder(self, original_path: str):
        """Move the original file to a 'sliced' subfolder."""
        try:
            sliced_folder = os.path.join(self._source_folder, "sliced")
            
            if not os.path.exists(sliced_folder):
                os.makedirs(sliced_folder)
            
            filename = os.path.basename(original_path)
            destination_path = os.path.join(sliced_folder, filename)
            
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(destination_path):
                new_filename = f"{base_name}_{counter}{ext}"
                destination_path = os.path.join(sliced_folder, new_filename)
                counter += 1
            
            shutil.move(original_path, destination_path)
            
        except Exception as e:
            Logger.logException("e", f"Failed to move file to sliced folder: {str(e)}")

    def _cleanup(self):
        """Clean up resources and clear build plate."""
        try:
            self._clearBuildPlate()
        except Exception as e:
            Logger.logException("e", f"Error during cleanup: {str(e)}")

    def getResult(self) -> Dict[str, Any]:
        """Get the processing results."""
        return self._results
