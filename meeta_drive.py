import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import uuid
import re
import io
import openpyxl
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="MEETA DRIVE",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
if 'spreadsheet_data' not in st.session_state:
    st.session_state.spreadsheet_data = {
        'activeSheet': 'sheet1',
        'sheets': [{
            'id': 'sheet1',
            'name': 'Sheet1',
            'cells': {},
            'columns': {},
            'rows': {}
        }]
    }

if 'current_file' not in st.session_state:
    st.session_state.current_file = None

if 'is_modified' not in st.session_state:
    st.session_state.is_modified = False

if 'formula_value' not in st.session_state:
    st.session_state.formula_value = ""

if 'active_cell' not in st.session_state:
    st.session_state.active_cell = None

if 'data_directory' not in st.session_state:
    # Create a data directory if it doesn't exist
    data_dir = 'data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    st.session_state.data_directory = data_dir

# Helper functions for cell references and formulas
def index_to_column(index):
    """Convert a 0-based column index to Excel-style column letter(s)"""
    result = ""
    while True:
        if index >= 0:
            remainder = index % 26
            result = chr(65 + remainder) + result
            index = index // 26 - 1
            if index < 0:
                break
        else:
            break
    return result

def column_to_index(column):
    """Convert Excel-style column letter(s) to 0-based column index"""
    result = 0
    for char in column:
        result = result * 26 + (ord(char) - 64)
    return result - 1

def cell_ref_to_indices(cell_ref):
    """Convert cell reference (e.g., 'A1') to row and column indices"""
    match = re.match(r"([A-Z]+)(\d+)", cell_ref)
    if not match:
        return None
    column = match.group(1)
    row = int(match.group(2)) - 1
    col = column_to_index(column)
    return {'rowIndex': row, 'colIndex': col}

def indices_to_cell_ref(row_index, col_index):
    """Convert row and column indices to cell reference (e.g., 'A1')"""
    column = index_to_column(col_index)
    return f"{column}{row_index + 1}"

def parse_formula(formula, sheet):
    """Basic formula parser for MEETA DRIVE"""
    # Remove the '=' prefix
    formula_text = formula[1:].strip() if formula.startswith('=') else formula.strip()
    
    # Check for SUM function
    if formula_text.startswith("SUM(") and formula_text.endswith(")"):
        range_text = formula_text[4:-1]
        if ":" in range_text:
            # Handle range like SUM(A1:B3)
            start_ref, end_ref = range_text.split(":")
            start_indices = cell_ref_to_indices(start_ref)
            end_indices = cell_ref_to_indices(end_ref)
            
            if start_indices and end_indices:
                sum_value = 0
                min_row = min(start_indices['rowIndex'], end_indices['rowIndex'])
                max_row = max(start_indices['rowIndex'], end_indices['rowIndex'])
                min_col = min(start_indices['colIndex'], end_indices['colIndex'])
                max_col = max(start_indices['colIndex'], end_indices['colIndex'])
                
                for row in range(min_row, max_row + 1):
                    for col in range(min_col, max_col + 1):
                        cell_ref = indices_to_cell_ref(row, col)
                        if cell_ref in sheet['cells'] and sheet['cells'][cell_ref].get('value'):
                            try:
                                sum_value += float(sheet['cells'][cell_ref]['value'])
                            except ValueError:
                                pass
                return sum_value
        else:
            # Handle list like SUM(A1,B1,C1)
            cell_refs = [ref.strip() for ref in range_text.split(",")]
            sum_value = 0
            for cell_ref in cell_refs:
                if cell_ref in sheet['cells'] and sheet['cells'][cell_ref].get('value'):
                    try:
                        sum_value += float(sheet['cells'][cell_ref]['value'])
                    except ValueError:
                        pass
            return sum_value
    
    # Check for AVERAGE function
    if formula_text.startswith("AVERAGE(") and formula_text.endswith(")"):
        range_text = formula_text[8:-1]
        if ":" in range_text:
            # Handle range like AVERAGE(A1:B3)
            start_ref, end_ref = range_text.split(":")
            start_indices = cell_ref_to_indices(start_ref)
            end_indices = cell_ref_to_indices(end_ref)
            
            if start_indices and end_indices:
                values = []
                min_row = min(start_indices['rowIndex'], end_indices['rowIndex'])
                max_row = max(start_indices['rowIndex'], end_indices['rowIndex'])
                min_col = min(start_indices['colIndex'], end_indices['colIndex'])
                max_col = max(start_indices['colIndex'], end_indices['colIndex'])
                
                for row in range(min_row, max_row + 1):
                    for col in range(min_col, max_col + 1):
                        cell_ref = indices_to_cell_ref(row, col)
                        if cell_ref in sheet['cells'] and sheet['cells'][cell_ref].get('value'):
                            try:
                                values.append(float(sheet['cells'][cell_ref]['value']))
                            except ValueError:
                                pass
                if values:
                    return sum(values) / len(values)
                return 0
    
    # If formula can't be parsed, return the formula text
    return formula_text

def evaluate_worksheet_formulas(worksheet):
    """Evaluate all formulas in the worksheet"""
    for cell_ref, cell_data in worksheet['cells'].items():
        if cell_data.get('formula'):
            cell_data['cachedValue'] = parse_formula(cell_data['formula'], worksheet)
    return worksheet

def update_cell(sheet_id, cell_ref, data):
    """Update cell data in the spreadsheet"""
    sheet = next((s for s in st.session_state.spreadsheet_data['sheets'] if s['id'] == sheet_id), None)
    if not sheet:
        return
    
    if cell_ref not in sheet['cells']:
        sheet['cells'][cell_ref] = {}
    
    for key, value in data.items():
        sheet['cells'][cell_ref][key] = value
    
    # Set the modified flag
    st.session_state.is_modified = True
    
    # Re-evaluate formulas if needed
    if 'formula' in data or 'value' in data:
        evaluate_worksheet_formulas(sheet)

def get_cell_display_value(cell):
    """Get the display value for a cell"""
    if not cell:
        return ""
    
    if 'formula' in cell and cell['formula']:
        if 'cachedValue' in cell:
            return str(cell['cachedValue'])
        return cell['formula']
    
    if 'value' in cell:
        return str(cell['value'])
    
    return ""

def save_spreadsheet(name=None):
    """Save the current spreadsheet to a file"""
    if not name and not st.session_state.current_file:
        return False
    
    filename = name or st.session_state.current_file['name']
    file_id = str(uuid.uuid4()) if not st.session_state.current_file else st.session_state.current_file['id']
    now = datetime.now().isoformat()
    
    file_data = {
        'id': file_id,
        'name': filename,
        'data': st.session_state.spreadsheet_data,
        'updatedAt': now,
        'createdAt': st.session_state.current_file['createdAt'] if st.session_state.current_file else now,
        'userId': 1  # Default user ID
    }
    
    try:
        with open(os.path.join(st.session_state.data_directory, f"{file_id}.json"), 'w') as f:
            json.dump(file_data, f)
        
        st.session_state.current_file = file_data
        st.session_state.is_modified = False
        return True
    except Exception as e:
        st.error(f"Error saving spreadsheet: {str(e)}")
        return False

def load_spreadsheet(file_id):
    """Load a spreadsheet from a file"""
    try:
        with open(os.path.join(st.session_state.data_directory, f"{file_id}.json"), 'r') as f:
            file_data = json.load(f)
        
        st.session_state.spreadsheet_data = file_data['data']
        st.session_state.current_file = file_data
        st.session_state.is_modified = False
        
        # Evaluate formulas
        for sheet in st.session_state.spreadsheet_data['sheets']:
            evaluate_worksheet_formulas(sheet)
        
        return True
    except Exception as e:
        st.error(f"Error loading spreadsheet: {str(e)}")
        return False

def new_spreadsheet():
    """Create a new empty spreadsheet"""
    st.session_state.spreadsheet_data = {
        'activeSheet': 'sheet1',
        'sheets': [{
            'id': 'sheet1',
            'name': 'Sheet1',
            'cells': {},
            'columns': {},
            'rows': {}
        }]
    }
    st.session_state.current_file = None
    st.session_state.is_modified = False
    st.session_state.active_cell = None
    st.session_state.formula_value = ""

def add_sheet():
    """Add a new sheet to the spreadsheet"""
    sheet_id = f"sheet{len(st.session_state.spreadsheet_data['sheets']) + 1}"
    sheet_name = f"Sheet{len(st.session_state.spreadsheet_data['sheets']) + 1}"
    
    new_sheet = {
        'id': sheet_id,
        'name': sheet_name,
        'cells': {},
        'columns': {},
        'rows': {}
    }
    
    st.session_state.spreadsheet_data['sheets'].append(new_sheet)
    st.session_state.spreadsheet_data['activeSheet'] = sheet_id
    st.session_state.is_modified = True

def remove_sheet(sheet_id):
    """Remove a sheet from the spreadsheet"""
    if len(st.session_state.spreadsheet_data['sheets']) <= 1:
        return  # Don't remove the last sheet
    
    st.session_state.spreadsheet_data['sheets'] = [
        s for s in st.session_state.spreadsheet_data['sheets'] if s['id'] != sheet_id
    ]
    
    # If we removed the active sheet, set a new active sheet
    if st.session_state.spreadsheet_data['activeSheet'] == sheet_id:
        st.session_state.spreadsheet_data['activeSheet'] = st.session_state.spreadsheet_data['sheets'][0]['id']
    
    st.session_state.is_modified = True

def rename_sheet(sheet_id, new_name):
    """Rename a sheet in the spreadsheet"""
    for sheet in st.session_state.spreadsheet_data['sheets']:
        if sheet['id'] == sheet_id:
            sheet['name'] = new_name
            st.session_state.is_modified = True
            break

def set_active_sheet(sheet_id):
    """Set the active sheet"""
    st.session_state.spreadsheet_data['activeSheet'] = sheet_id

def handle_cell_click(cell_ref):
    """Handle cell click event"""
    st.session_state.active_cell = cell_ref
    
    # Get current cell data
    active_sheet_id = st.session_state.spreadsheet_data['activeSheet']
    active_sheet = next((s for s in st.session_state.spreadsheet_data['sheets'] if s['id'] == active_sheet_id), None)
    
    if active_sheet and cell_ref in active_sheet['cells']:
        cell = active_sheet['cells'][cell_ref]
        if 'formula' in cell:
            st.session_state.formula_value = cell['formula']
        else:
            st.session_state.formula_value = cell.get('value', '')
    else:
        st.session_state.formula_value = ""

def commit_formula_value():
    """Commit the formula bar value to the active cell"""
    if not st.session_state.active_cell:
        return
    
    value = st.session_state.formula_value
    active_sheet_id = st.session_state.spreadsheet_data['activeSheet']
    
    # Check if it's a formula
    if value and isinstance(value, str) and value.startswith('='):
        update_cell(active_sheet_id, st.session_state.active_cell, {
            'formula': value,
            'value': None
        })
    else:
        update_cell(active_sheet_id, st.session_state.active_cell, {
            'value': value,
            'formula': None
        })

# UI Components
def render_toolbar():
    """Render the toolbar with actions and formatting options"""
    st.markdown("""
    <style>
    .toolbar {
        display: flex;
        padding: 5px;
        background-color: #f0f0f0;
        border-bottom: 1px solid #ccc;
    }
    .toolbar-section {
        margin-right: 15px;
        padding-right: 15px;
        border-right: 1px solid #ddd;
    }
    .toolbar-section:last-child {
        border-right: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns([1, 1.5, 1.5, 1.5, 1.5])
    
    with col1:
        st.markdown("## MEETA DRIVE")
    
    with col2:
        if st.button("New"):
            new_spreadsheet()
    
    with col3:
        spreadsheet_name = st.text_input("File Name", 
                                        value=st.session_state.current_file['name'] if st.session_state.current_file else "Untitled Spreadsheet",
                                        key="spreadsheet_name")
    
    with col4:
        if st.button("Save"):
            if save_spreadsheet(spreadsheet_name):
                st.success(f"Saved as {spreadsheet_name}")
            else:
                st.error("Failed to save spreadsheet")
    
    with col5:
        available_files = []
        for filename in os.listdir(st.session_state.data_directory):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(st.session_state.data_directory, filename), 'r') as f:
                        file_data = json.load(f)
                        available_files.append((file_data['id'], file_data['name']))
                except:
                    pass
        
        file_options = ["Select a file to open"] + [name for _, name in available_files]
        file_ids = [None] + [id for id, _ in available_files]
        
        selected_index = st.selectbox("Open", options=file_options, index=0)
        if selected_index != "Select a file to open" and selected_index != file_options[0]:
            selected_id = file_ids[file_options.index(selected_index)]
            if selected_id:
                load_spreadsheet(selected_id)

def render_formula_bar():
    """Render the formula bar"""
    st.markdown("""
    <style>
    .formula-bar {
        display: flex;
        padding: 5px;
        background-color: #f8f9fa;
        border-bottom: 1px solid #ddd;
        align-items: center;
    }
    .cell-address {
        width: 80px;
        padding: 5px;
        background-color: white;
        border: 1px solid #ddd;
        margin-right: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 6])
    
    with col1:
        st.markdown(f"**{st.session_state.active_cell or ''}**")
    
    with col2:
        formula_input = st.text_input("", 
                                     value=st.session_state.formula_value,
                                     key="formula_input",
                                     on_change=commit_formula_value)
        st.session_state.formula_value = formula_input

def render_sheet_tabs():
    """Render the sheet tabs"""
    st.markdown("""
    <style>
    .sheet-tabs {
        display: flex;
        padding: 5px;
        background-color: #f0f0f0;
        border-top: 1px solid #ddd;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Get the active sheet
    active_sheet_id = st.session_state.spreadsheet_data['activeSheet']
    sheets = st.session_state.spreadsheet_data['sheets']
    
    # Create columns for each sheet plus an "Add" button
    cols = st.columns(len(sheets) + 1)
    
    # Render sheet tabs
    for i, sheet in enumerate(sheets):
        with cols[i]:
            if st.button(sheet['name'], key=f"sheet_{sheet['id']}",
                        use_container_width=True,
                        type="primary" if sheet['id'] == active_sheet_id else "secondary"):
                set_active_sheet(sheet['id'])
    
    # Render "Add Sheet" button
    with cols[-1]:
        if st.button("+", key="add_sheet_button", use_container_width=True):
            add_sheet()

def render_spreadsheet_grid():
    """Render the main spreadsheet grid"""
    # Get the active sheet
    active_sheet_id = st.session_state.spreadsheet_data['activeSheet']
    active_sheet = next((s for s in st.session_state.spreadsheet_data['sheets'] if s['id'] == active_sheet_id), None)
    
    if not active_sheet:
        st.error("No active sheet found")
        return
    
    # Define grid dimensions
    DEFAULT_ROWS = 20
    DEFAULT_COLUMNS = 10
    
    # Create an empty DataFrame for the grid
    columns = [' '] + [index_to_column(i) for i in range(DEFAULT_COLUMNS)]
    data = []
    
    # Add header row with column indices
    header_row = {' ': ''}
    for i in range(DEFAULT_COLUMNS):
        col_letter = index_to_column(i)
        header_row[col_letter] = col_letter
    data.append(header_row)
    
    # Add data rows
    for row in range(DEFAULT_ROWS):
        row_data = {' ': str(row + 1)}  # Row header
        for col in range(DEFAULT_COLUMNS):
            cell_ref = indices_to_cell_ref(row, col)
            cell_data = active_sheet['cells'].get(cell_ref, {})
            row_data[index_to_column(col)] = get_cell_display_value(cell_data)
        data.append(row_data)
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Function to handle edited cell values
    def handle_edited_cells(edited_rows):
        for idx, row in enumerate(edited_rows):
            if idx == 0:  # Skip header row
                continue
            
            row_index = idx - 1  # Adjust for header row
            
            for col_name, value in row.items():
                if col_name != ' ':  # Skip row header column
                    col_index = column_to_index(col_name)
                    cell_ref = indices_to_cell_ref(row_index, col_index)
                    
                    # Skip if the value hasn't changed
                    cell_data = active_sheet['cells'].get(cell_ref, {})
                    current_value = get_cell_display_value(cell_data)
                    
                    if str(value) != str(current_value):
                        # The value has changed, update the cell
                        if str(value).startswith('='):
                            update_cell(active_sheet_id, cell_ref, {
                                'formula': str(value),
                                'value': None
                            })
                        else:
                            update_cell(active_sheet_id, cell_ref, {
                                'value': str(value),
                                'formula': None
                            })
    
    # Render the editable grid
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="fixed",
        key="spreadsheet_grid",
        on_change=lambda: handle_edited_cells(st.session_state.spreadsheet_grid),
        column_config={
            ' ': st.column_config.Column(
                width="small",
                disabled=True
            )
        },
        hide_index=True
    )
    
    # Handle clicking a cell to set it as active
    if 'spreadsheet_grid' in st.session_state and st.session_state.spreadsheet_grid is not None:
        for idx, row in enumerate(st.session_state.spreadsheet_grid):
            if idx == 0:  # Skip header row
                continue
            
            row_index = idx - 1  # Adjust for header row
            
            for col_name, value in row.items():
                if col_name != ' ':  # Skip row header column
                    col_index = column_to_index(col_name)
                    cell_ref = indices_to_cell_ref(row_index, col_index)
                    
                    # If this is the active cell (detected by editing), update the active cell reference
                    if 'edited_rows' in st.session_state and idx in st.session_state.edited_rows:
                        if col_name in st.session_state.edited_rows[idx]:
                            handle_cell_click(cell_ref)

def render_status_bar():
    """Render the status bar"""
    st.markdown("""
    <style>
    .status-bar {
        display: flex;
        padding: 5px;
        background-color: #f0f0f0;
        border-top: 1px solid #ddd;
        font-size: 12px;
        color: #666;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        status = "Ready"
        if st.session_state.is_modified:
            status += " (Modified)"
        st.text(status)
    
    with col2:
        if st.session_state.current_file:
            last_saved = datetime.fromisoformat(st.session_state.current_file['updatedAt']).strftime("%Y-%m-%d %H:%M:%S")
            st.text(f"Last saved: {last_saved}")

# Main app layout
def main():
    render_toolbar()
    render_formula_bar()
    render_spreadsheet_grid()
    render_sheet_tabs()
    render_status_bar()

if __name__ == "__main__":
    main()