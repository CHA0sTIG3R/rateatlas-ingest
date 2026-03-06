# tax_bracket_ingest/parser/parser.py
from bs4 import BeautifulSoup
import bs4
import pandas as pd

def parse_html(html_content: str) -> dict:
    """
    Parse the HTML content and extract relevant data.
    This function looks for specific tags (h2, h4, table) and extracts their text.
    It organizes the data into a dictionary where headers are keys and their corresponding
    table data is stored as values.

    Args:
        html_content (str): The HTML content to parse.

    Returns:
        dict : A dictionary containing extracted data.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    data = {}
    
    for tag in soup.find_all(['h2','h4','table']):
        if tag.name in ['h2', 'h4']: # type: ignore
            # Use the text of the header as a key
            header_text = tag.get_text(strip=True)
            data[header_text] = {}
        elif tag.name == 'table': # type: ignore
            # Use the last header as the key for the table data
            if data:
                current_header = list(data.keys())[-1]
                data[current_header]['table'] = parse_table(tag) # type: ignore
    return data

def parse_table(table : 'bs4.element.Tag') -> dict:
    """
    Parse a table element and extract tax rates and ranges.
    Args:
        table (bs4.element.Tag): The table element to parse.
    Returns:
        dict: A dictionary containing tax rates and their corresponding ranges.
    """
    data = {}
    # Find all rows in the table
    rows = table.find_all('tr')
    for row in rows:
        # Find all cells in the row
        cells = row.find_all(['th', 'td']) # type: ignore
        if len(cells) >= 2:  # Ensure there are at least two cells
            # Use the first cell as the key and the second as the value
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            data[key] = value
    return data

def parse_irs_data(html_content: str) -> dict:
    """
    Parse the IRS data from the provided HTML content.
    Args:
        html_content (str): The HTML content to parse.
    Returns:
        dict: A dictionary containing structured IRS tax bracket data.
    """
    
    raw_tax_bracket = parse_html(html_content)
    
    irs_tax_bracket = {k: v for k, v in raw_tax_bracket.items() if v and any(v.values())}
    return irs_tax_bracket

def parse_irs_data_to_dataframe(irs_data: dict) -> pd.DataFrame:
    """
    Convert the parsed IRS data dictionary into a pandas DataFrame.
    
    Args:
        irs_data (dict): The parsed IRS data dictionary.
        
    Returns:
        pd.DataFrame: A DataFrame containing the structured IRS tax bracket data.
    """
    # Flatten the dictionary and convert it to a DataFrame
    rows = []
    for header, content in irs_data.items():
        if 'table' in content:
            for key, value in content['table'].items():
                rows.append({'Header': header, 'Rate': key, 'Range': value})
    
    return pd.DataFrame(rows)