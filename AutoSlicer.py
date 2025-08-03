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

from UM.Extension import Extension
from UM.Message import Message
from UM.Logger import Logger

from .AutoSlicerDialog import AutoSlicerDialog
from .AutoSlicerJob import AutoSlicerJob


class AutoSlicer(Extension):
    """Main extension class for the Auto Slicer plugin."""
    
    def __init__(self):
        super().__init__()
        self.addMenuItem("Auto Slicer", self.showDialog)
        
        # Plugin state
        self._dialog = None
        self._job = None
        self._is_running = False
        
    def showDialog(self):
        """Show the Auto Slicer configuration dialog."""
        if self._dialog is None:
            self._dialog = AutoSlicerDialog()
            self._dialog.startProcessing.connect(self.startAutoSlicing)
            self._dialog.stopProcessing.connect(self.stopAutoSlicing)
            self._dialog.skipCurrentFile.connect(self.skipCurrentFile)
        
        self._dialog.show()
        self._dialog.raise_()
    
    def startAutoSlicing(self, source_folder, destination_folder, max_files, file_profile_map, slice_timeout):
        """Start the auto slicing process."""
        if self._is_running:
            Logger.log("w", "Auto slicing is already running")
            return
        
        try:
            self._is_running = True
            
            # Create and start the slicing job
            self._job = AutoSlicerJob(source_folder, destination_folder, max_files, file_profile_map, slice_timeout)
            self._job.progress.connect(self._onProgress)
            self._job.finished.connect(self._onJobCompleted)
            self._job.statusChanged.connect(self._onJobStatusChanged)
            self._job.fileError.connect(self._onFileError)  # Connect file error signal
            self._job.fileSkipped.connect(self._onFileSkipped)  # Connect file skipped signal
            self._job.start()
            
            # Show progress message
            self._message = Message(
                title="Auto Slicer", 
                text="Starting auto slicing process...", 
                lifetime=0, 
                dismissable=False, 
                progress=-1
            )
            self._message.show()
            
        except Exception as e:
            Logger.logException("e", f"Failed to start auto slicing: {str(e)}")
            self._is_running = False
            if self._dialog:
                self._dialog.onProcessingError(f"Failed to start: {str(e)}")
    
    def stopAutoSlicing(self):
        """Stop the auto slicing process."""
        if not self._is_running:
            Logger.log("w", "No auto slicing process is running")
            return
        
        try:
            if self._job:
                self._job.stop()
            
            self._is_running = False
            
            if self._message:
                self._message.hide()
                
        except Exception as e:
            Logger.logException("e", f"Error stopping auto slicing: {str(e)}")

    def skipCurrentFile(self):
        """Skip the current file being processed."""
        if not self._is_running:
            Logger.log("w", "No auto slicing process is running")
            return
        
        try:
            if self._job:
                self._job.skipCurrentFile()
                
        except Exception as e:
            Logger.logException("e", f"Error skipping current file: {str(e)}")

    def skipCurrentFile(self):
        """Skip the current file being processed."""
        if not self._is_running:
            Logger.log("w", "No auto slicing process is running")
            return
        
        try:
            if self._job:
                self._job.skipCurrentFile()
                Logger.log("i", "Requested to skip current file")
                
        except Exception as e:
            Logger.logException("e", f"Error skipping current file: {str(e)}")
    
    def _onProgress(self, progress):
        """Handle progress updates from the job."""
        if self._message:
            self._message.setProgress(progress)
        
        if self._dialog:
            self._dialog.onProgressUpdate(progress)
    
    def _onJobStatusChanged(self, status_text):
        """Handle status updates from the job."""
        if self._message:
            self._message.setText(status_text)
        
        if self._dialog:
            self._dialog.onStatusUpdate(status_text)
    
    def _onFileError(self, filename, error_message):
        """Handle individual file errors from the job."""
        Logger.log("w", f"File error: {filename} - {error_message}")
        
        if self._dialog:
            self._dialog.onFileError(filename, error_message)

    def _onFileSkipped(self, filename, skip_reason):
        """Handle individual file skips from the job."""
        Logger.log("i", f"File skipped: {filename} - {skip_reason}")
        
        if self._dialog:
            self._dialog.onFileSkipped(filename, skip_reason)
    
    def _onJobCompleted(self, job):
        """Handle job completion."""        
        self._is_running = False
        
        if self._message:
            self._message.hide()
        
        try:
            # Get results from job
            results = job.getResult()
            success_count = results.get('success_count', 0)
            error_count = results.get('error_count', 0)
            skipped_count = len(results.get('skipped_files', []))
            
            # Create completion message with all counts
            total_processed = success_count + error_count + skipped_count
            message_parts = [f"Processing finished. {success_count} files processed successfully"]
            
            if skipped_count > 0:
                message_parts.append(f"{skipped_count} files skipped")
            
            if error_count > 0:
                message_parts.append(f"{error_count} errors")
            
            completion_text = ", ".join(message_parts) + "."
            
            # Show completion message
            completion_message = Message(
                title="Auto Slicer Complete",
                text=completion_text,
                message_type=Message.MessageType.POSITIVE if error_count == 0 else Message.MessageType.WARNING
            )
            completion_message.show()
            
            if self._dialog:
                self._dialog.onProcessingComplete(results)
                
        except Exception as e:
            Logger.logException("e", f"Error handling job completion: {str(e)}")
            if self._dialog:
                self._dialog.onProcessingError(f"Error completing job: {str(e)}")
    
    @property
    def isRunning(self):
        """Check if auto slicing is currently running."""
        return self._is_running
