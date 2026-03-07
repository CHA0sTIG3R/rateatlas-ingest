# tests/unit/test_normalize.py

import pytest
from tax_bracket_ingest.parser.normalize import (
    process_irs_dataframe, 
    drop_one_duplicate
)
import pandas as pd
from datetime import datetime

def test_process_irs_dataframe(sample_raw_csv):
    """Test the process_irs_dataframe function to ensure it normalizes the DataFrame correctly."""
    normalized_df = process_irs_dataframe(sample_raw_csv)
    
    # Check if the DataFrame has the expected columns
    expected_columns = ['Year', 'Married Filing Jointly (Rates/Brackets)', 
                        'Married Filing Separately (Rates/Brackets)', 
                        'Single Filer (Rates/Brackets)', 
                        'Head of Household (Rates/Brackets)', 
                        'S Range Start', 'S Range End']
    assert all(col in normalized_df.columns for col in expected_columns), "Normalized DataFrame should contain expected columns."
    
    expected_year = int(sample_raw_csv['Header'][0].split(' ')[0])
    assert (normalized_df['Year'] == expected_year).all(), "Year column should match the year in the sample data."
    expected_row_count = 7 
    assert len(normalized_df) == expected_row_count, f"Normalized DataFrame should have {expected_row_count} rows."
    
def test_drop_one_duplicate(sample_raw_csv):
    """Test the drop_one_duplicate function to ensure it removes column name duplicates correctly."""
    df_copy_1 = sample_raw_csv.copy()
    df_copy_2 = sample_raw_csv.copy()
    df_copy_3 = sample_raw_csv.copy()
    df_with_duplicates = pd.concat([df_copy_1, df_copy_2, df_copy_3], axis=1)
    
    assert df_with_duplicates.columns.tolist().count('Header') > 1, "There should be multiple 'Header' columns before dropping duplicates."
    len_before = len(df_with_duplicates.columns)
    
    cleaned_df = drop_one_duplicate(df_with_duplicates, 'Header')
    
    len_after = len(cleaned_df.columns)  
    assert len_after == len_before - 2, "One duplicate 'Header' column should be removed."
    assert cleaned_df.columns.tolist().count('Header') == 1, "There should be only one 'Header' column in the cleaned DataFrame."
    

if __name__ == "__main__":
    pytest.main()