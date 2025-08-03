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

# Based on Cura's RemovableDriveOutputDevice

import os
import os.path

from UM.Application import Application
from UM.Logger import Logger
from UM.FileHandler.WriteFileJob import WriteFileJob
from UM.FileHandler.FileWriter import FileWriter
from UM.Scene.Iterator.BreadthFirstIterator import BreadthFirstIterator
from UM.OutputDevice.OutputDevice import OutputDevice
from UM.OutputDevice import OutputDeviceError

from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

class LocalFileOutputDevice(OutputDevice):
    """Local file output device for silent file saving to a specified directory."""
    
    def __init__(self, device_id, destination_folder: str):
        super().__init__(device_id)
        
        self._destination_folder = destination_folder
        
        self.setName("Local File Device")
        self.setShortDescription("Save to Local Folder")
        self.setDescription(f"Save to Local Folder {destination_folder}")
        self.setIconName("save")
        self.setPriority(1)
        
        self._writing = False
        self._stream = None

    def requestWrite(self, nodes, file_name=None, filter_by_machine=False, file_handler=None, **kwargs):
        """Request the specified nodes to be written to the local folder.

        :param nodes: A collection of scene nodes that should be written to the
            local folder.
        :param file_name: A suggestion for the file name to write to.
            If none is provided, a file name will be made from the names of the
            meshes.
        :param filter_by_machine: Should we limit the available MIME types to the
            MIME types available to the currently active machine?
        """
        
        filter_by_machine = True  # This plugin is intended to be used by machine
        if self._writing:
            raise OutputDeviceError.DeviceBusyError()

        # Formats supported by this application (File types that we can actually write)
        if file_handler:
            file_formats = file_handler.getSupportedFileTypesWrite()
        else:
            file_formats = Application.getInstance().getMeshFileHandler().getSupportedFileTypesWrite()

        if filter_by_machine:
            container = Application.getInstance().getGlobalContainerStack().findContainer({"file_formats": "*"})

            # Create a list from supported file formats string
            machine_file_formats = [file_type.strip() for file_type in container.getMetaDataEntry("file_formats").split(";")]
            # Take the intersection between file_formats and machine_file_formats.
            format_by_mimetype = {format["mime_type"]: format for format in file_formats}
            file_formats = [format_by_mimetype[mimetype] for mimetype in machine_file_formats if mimetype in format_by_mimetype]  # Keep them ordered according to the preference in machine_file_formats.

        if len(file_formats) == 0:
            Logger.log("e", "There are no file formats available to write with!")
            raise OutputDeviceError.WriteRequestFailedError("There are no file formats available to write with!")
        
        preferred_format = file_formats[0]
        
        # Special case: if preferred format is compressed G-code but uncompressed is also available,
        # switch to uncompressed to avoid .gcode.gz files
        if (preferred_format["mime_type"] == "application/gzip" and 
            any(fmt["mime_type"] == "text/x-gcode" for fmt in file_formats)):
            preferred_format = next(fmt for fmt in file_formats if fmt["mime_type"] == "text/x-gcode")

        # Just take the first file format available.
        if file_handler is not None:
            writer = file_handler.getWriterByMimeType(preferred_format["mime_type"])
        else:
            writer = Application.getInstance().getMeshFileHandler().getWriterByMimeType(preferred_format["mime_type"])

        extension = preferred_format["extension"]

        if file_name is None:
            file_name = self._automaticFileName(nodes)

        if extension:  # Not empty string.
            extension = "." + extension
        
        # Use destination folder instead of device ID
        file_name = os.path.join(self._destination_folder, file_name + extension)
        self._performWrite(file_name, preferred_format, writer, nodes)

    def _performWrite(self, file_name, preferred_format, writer, nodes):
        """Writes the specified nodes to the local folder. This is split from
        requestWrite to allow interception in other plugins.

        :param file_name: File path to write to.
        :param preferred_format: Preferred file format to write to.
        :param writer: Writer for writing to the file.
        :param nodes: A collection of scene nodes that should be written to the
        file.
        """

        # Manually trigger post-processing scripts before writing
        # This ensures post-processing happens even though we're not using the normal OutputDeviceManager flow
        try:
            post_processing_plugin = Application.getInstance().getPluginRegistry().getPluginObject("PostProcessingPlugin")
            if post_processing_plugin:
                Logger.log("d", "Executing post-processing scripts...")
                post_processing_plugin.execute(self)
                Logger.log("d", "Post-processing scripts completed")
        except Exception as e:
            Logger.log("w", "Could not execute post-processing scripts: %s", str(e))

        try:
            Logger.log("d", "Writing to %s", file_name)
            # Using buffering greatly reduces the write time for many lines of gcode
            if preferred_format["mode"] == FileWriter.OutputMode.TextMode:
                self._stream = open(file_name, "wt", buffering=1, encoding="utf-8")
            else:  # Binary mode.
                self._stream = open(file_name, "wb", buffering=1)
            
            writer_args = {}
            job = WriteFileJob(writer, self._stream, nodes, preferred_format["mode"], writer_args)
            job.setFileName(file_name)
            job.progress.connect(self._onProgress)
            job.finished.connect(self._onFinished)

            # Emit writeStarted signal
            self.writeStarted.emit(self)

            self._writing = True
            job.start()
            
        except PermissionError as e:
            Logger.log("e", "Permission denied when trying to write to %s: %s", file_name, str(e))
            raise OutputDeviceError.PermissionDeniedError(f"Could not save to {file_name}: {str(e)}") from e
        except OSError as e:
            Logger.log("e", "Operating system would not let us write to %s: %s", file_name, str(e))
            raise OutputDeviceError.WriteRequestFailedError(f"Could not save to {file_name}: {str(e)}") from e

    def _automaticFileName(self, nodes):
        """Generate a file name automatically for the specified nodes to be saved in.

        The name generated will be the name of one of the nodes. Which node that
        is can not be guaranteed.

        :param nodes: A collection of nodes for which to generate a file name.
        """
        for root in nodes:
            for child in BreadthFirstIterator(root):
                if child.getMeshData():
                    name = child.getName()
                    if name:
                        return name
        raise OutputDeviceError.WriteRequestFailedError("Could not find a file name when trying to write to local device.")

    def _onProgress(self, job, progress):
        self.writeProgress.emit(self, progress)

    def _onFinished(self, job):
        if self._stream:
            error = job.getError()
            try:
                # Explicitly closing the stream flushes the write-buffer
                self._stream.close()
            except Exception as e:
                if not error:
                    # Only log new error if there was no previous one
                    error = e

            self._stream = None
            self._writing = False
            self.writeFinished.emit(self)

            if not error:
                Logger.log("d", "Successfully saved to %s", job.getFileName())
                self.writeSuccess.emit(self)
            else:
                try:
                    os.remove(job.getFileName())
                except Exception as e:
                    Logger.logException("e", "Exception when trying to remove incomplete exported file %s", str(job.getFileName()))
                Logger.log("e", "Could not save to local folder: %s", str(job.getError()))
                self.writeError.emit(self)

    def getDestinationFolder(self):
        """Get the destination folder for this output device."""
        return self._destination_folder
