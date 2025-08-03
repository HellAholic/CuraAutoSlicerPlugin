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

class PluginConstants:
    # --- Theme Colors ---
    DARK_BACKGROUND_COLOR = "#2d2d2d"
    TEXT_COLOR_LIGHT_GRAY = "#E0E0E0"
    TEXT_INPUT_BG_COLOR_DARK_GRAY = "#3c3c3c"
    TEXT_INPUT_BORDER_COLOR_GRAY = "#505050"
    TEXT_COLOR_HIGHLIGHTED_BG = "#1B1B1B"
    ERROR_TEXT_COLOR_LIGHT_RED = "#FF6B6B"
    GROUPBOX_BORDER_COLOR = "#BBBBBB"
    
    # --- Printer Status Colors ---
    PRINTER_STATUS_ACTIVE_COLOR = "#4CAF50"  # Green for active extruders
    PRINTER_STATUS_DISABLED_COLOR = "#FF9800"  # Orange for disabled extruders
    PRINTER_STATUS_ERROR_COLOR = "#F44336"  # Red for errors/not configured
    PRINTER_STATUS_WARNING_COLOR = "#FFC107"  # Yellow for warnings/compatibility issues
    
    # --- Material Colors ---
    DEFAULT_MATERIAL_COLOR = "#888888"  # Default gray color for materials when color_code is unavailable

    # --- Dialog sizes ---
    AUTO_SLICER_DIALOG_MIN_WIDTH = 600
    AUTO_SLICER_DIALOG_MIN_HEIGHT = 700
    AUTO_SLICER_DIALOG_MAX_WIDTH = 800
    AUTO_SLICER_DIALOG_MAX_HEIGHT = 1200  # Increased to accommodate 8 extruders

    # --- Button Colors ---
    BUTTON_PRIMARY_BG = "#0078d7"
    BUTTON_PRIMARY_HOVER_BG = "#005a9e"
    BUTTON_PRIMARY_TEXT = "#FFFFFF"
    BUTTON_PRIMARY_BORDER = "#FFFFFF"

    BUTTON_CLOSE_BG = "#FFFFFF"
    BUTTON_CLOSE_TEXT = "#e81123"
    BUTTON_CLOSE_BORDER = "#e81123"
    BUTTON_CLOSE_HOVER_BG = "#f4f4f4"

    BUTTON_SECONDARY_BORDER = "#cccccc"
    BUTTON_SECONDARY_BG = "#f9f9f9"
    BUTTON_SECONDARY_TEXT = "#333333"
    BUTTON_SECONDARY_HOVER_BG = "#e0e0e0"
    HIGHLIGHT_COLOR = "#006cc4"

    BUTTON_SKIP_BG = "#f0ce5e"
    BUTTON_SKIP_HOVER_BG = "#e0b84c"

    # --- General Styles ---
    TITLE_STYLE = f"font-size: 13px; font-weight: bold; margin-bottom: 3px; color: {TEXT_COLOR_LIGHT_GRAY};"
    DESCRIPTION_STYLE_MENU = f"font-size: 12px; margin-bottom: 3px; color: {TEXT_COLOR_LIGHT_GRAY};"
    DESCRIPTION_STYLE_FORM = f"font-size: 12px; margin-bottom: 3px; color: {TEXT_COLOR_LIGHT_GRAY};"
    LINE_EDIT_STYLE = f"background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY}; color: {TEXT_COLOR_LIGHT_GRAY}; border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY}; border-radius: 3px; padding: 2px;"
    LABEL_STYLE = f"color: {TEXT_COLOR_LIGHT_GRAY}; font-size: 13px"
    STATUS_LABEL_STYLE = f"color: {TEXT_COLOR_LIGHT_GRAY}; font-size: 13px"
    DIALOG_BACKGROUND_STYLE = f"background-color: {DARK_BACKGROUND_COLOR};"
    
    # --- Printer Information Styles ---
    PRINTER_INFO_LABEL_STYLE = f"color: {TEXT_COLOR_LIGHT_GRAY}; font-size: 12px; margin: 2px 0px;"
    PRINTER_INFO_ACTIVE_STYLE = f"color: {PRINTER_STATUS_ACTIVE_COLOR}; font-size: 12px; margin: 2px 0px;"
    PRINTER_INFO_DISABLED_STYLE = f"color: {PRINTER_STATUS_DISABLED_COLOR}; font-size: 12px; margin: 2px 0px;"
    PRINTER_INFO_ERROR_STYLE = f"color: {PRINTER_STATUS_ERROR_COLOR}; font-size: 12px; margin: 2px 0px;"
    PRINTER_INFO_WARNING_STYLE = f"color: {PRINTER_STATUS_WARNING_COLOR}; font-size: 12px; margin: 2px 0px;"
    
    # --- Printer Information Layout ---
    PRINTER_INFO_LABEL_MIN_HEIGHT = 20
    PRINTER_INFO_LABEL_MAX_HEIGHT = 30
    PRINTER_INFO_SECTION_MIN_HEIGHT = 100
    PRINTER_INFO_SECTION_MAX_HEIGHT = 300

    GROUPBOX_STYLE = f'''
        QGroupBox {{
            border: 2px solid {GROUPBOX_BORDER_COLOR};
            border-radius: 5px;
            margin-top: 20px;
        }}
        QGroupBox::title {{
            color: {TEXT_COLOR_LIGHT_GRAY};
            font-size: 13px;
            font-weight: bold;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0px 5px;
            left: 10px; /* Offset to align title within the border */
        }}
    '''

    # --- Button Styles ---
    BROWSE_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 10px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_PRIMARY_BG}; border: 1px solid {BUTTON_PRIMARY_BORDER};
            color: {BUTTON_PRIMARY_TEXT}; border-radius: 3px; min-width: 80px;
        }} 
        QPushButton:hover {{ 
            background-color: {BUTTON_PRIMARY_HOVER_BG}; 
        }}
        QPushButton:disabled {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            color: {TEXT_INPUT_BORDER_COLOR_GRAY};
        }}
    '''
    CLOSE_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 10px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_CLOSE_BG}; border: 1px solid {BUTTON_CLOSE_BORDER};
            color: {BUTTON_CLOSE_TEXT}; border-radius: 3px; min-width: 80px;
        }} 
        QPushButton:hover {{ 
            background-color: {BUTTON_CLOSE_HOVER_BG}; 
        }}
        QPushButton:disabled {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            color: {TEXT_INPUT_BORDER_COLOR_GRAY};
        }}
    '''
    START_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 15px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_PRIMARY_BG}; border: 1px solid {BUTTON_PRIMARY_BORDER};
            color: {BUTTON_PRIMARY_TEXT}; border-radius: 3px; font-size: 14px
        }} 
        QPushButton:hover {{ 
            background-color: {BUTTON_PRIMARY_HOVER_BG}; 
        }}
        QPushButton:disabled {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            color: {TEXT_INPUT_BORDER_COLOR_GRAY};
        }}
    '''
    STOP_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 15px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_CLOSE_BORDER}; border: 1px solid {BUTTON_CLOSE_BG};
            color: {BUTTON_PRIMARY_TEXT}; border-radius: 3px; min-width: 80px; font-size: 14px
        }} 
        QPushButton:hover {{ 
            background-color: {BUTTON_CLOSE_HOVER_BG};
            border: 1px solid {BUTTON_CLOSE_BORDER};
            color: {BUTTON_CLOSE_TEXT};

        }}
        QPushButton:disabled {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            border: 1px solid {BUTTON_CLOSE_BORDER};
            color: {TEXT_INPUT_BORDER_COLOR_GRAY};
        }}
    '''
    SKIP_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 10px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_SKIP_BG}; border: 1px solid {BUTTON_PRIMARY_BORDER};
            color: {BUTTON_PRIMARY_TEXT}; border-radius: 3px; min-width: 80px;
        }} 
        QPushButton:hover {{ 
            background-color: {BUTTON_SKIP_HOVER_BG}; 
        }}
        QPushButton:disabled {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            color: {TEXT_INPUT_BORDER_COLOR_GRAY};
        }}
    '''

    # --- Auto Slicer Specific Styles ---
    AUTO_SLICER_PROGRESS_BAR_STYLE = f'''
        QProgressBar {{
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            border-radius: 3px;
            text-align: center;
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            color: {TEXT_COLOR_LIGHT_GRAY};
        }}
        QProgressBar::chunk {{
            background-color: {BUTTON_PRIMARY_BG};
            border-radius: 2px;
        }}
    '''

    # --- Log Text Style ---
    AUTO_SLICER_LOG_STYLE = f'''
        QTextEdit {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            color: {TEXT_COLOR_LIGHT_GRAY};
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            padding: 5px;
            border-radius: 3px;
        }}
    '''

    # --- Table Widget Styles ---
    TABLE_WIDGET_STYLE = f'''
        QTableWidget {{
            background-color: #2b2b2b;
            color: #ffffff;
            gridline-color: #555555;
            selection-background-color: #3d5aa3;
            alternate-background-color: #333333;
            border: 1px solid #555555;
        }}
        QTableWidget::item {{
            padding: 3px 5px;
            border: none;
            text-align: left;
        }}
        QTableWidget::item:selected {{
            background-color: #3d5aa3;
            color: #ffffff;
        }}
        QHeaderView::section {{
            background-color: #404040;
            color: #ffffff;
            padding: 8px 5px;
            border: 1px solid #555555;
            font-weight: bold;
            text-align: left;
        }}
    '''

    # --- ComboBox Styles ---
    COMBOBOX_STYLE = f'''
        QComboBox {{
            background-color: #2b2b2b;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 4px 6px;
            margin: 0px;
            min-height: 24px;
            max-height: 32px;
            border-radius: 2px;
        }}
        QComboBox:hover {{
            border: 1px solid #0078d4;
        }}
        QComboBox:focus {{
            border: 1px solid #0078d4;
            outline: none;
        }}
        QComboBox::drop-down {{
            border: none;
            background-color: #3c3c3c;
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid #555555;
        }}
        QComboBox::down-arrow {{
            border: 1px solid #666666;
            border-radius: 2px;
            background-color: #4d4d4d;
            width: 10px;
            height: 10px;
        }}
        QComboBox QAbstractItemView {{
            background-color: #2b2b2b;
            color: #ffffff;
            selection-background-color: #0078d4;
            border: 1px solid #555555;
            margin: 0px;
            padding: 0px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 6px;
            margin: 0px;
            border: none;
            min-height: 20px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: #0078d4;
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: #0078d4;
        }}
        QComboBox QAbstractItemView::item:disabled {{
            background-color: #1e1e1e;
            color: #888888;
            font-weight: bold;
            text-align: center;
        }}
    '''
