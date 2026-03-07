from datetime import date, datetime
from bs4 import BeautifulSoup
from typing import Optional


def check_page_freshness(html_content: str) -> Optional[date]: # type: ignore
    """
    Check the freshness of the IRS tax bracket page by extracting the last updated date.
    
    Args:
        html_content (str): The HTML content of the IRS tax bracket page.
        
    Returns:
        date: The last updated date extracted from the page, or None if it cannot be determined.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    page_status = soup.find('div', class_='pup-content-revision')
    if page_status:
        last_updated_text = page_status.get_text(strip=True)
        # Current format: "Page Last Reviewed or Updated: 01-Jan-2024"
        if "Page Last Reviewed or Updated:" in last_updated_text:
            try:
                last_updated_str = last_updated_text.split("Page Last Reviewed or Updated:")[1].strip()
                last_updated_date = datetime.strptime(last_updated_str, "%d-%b-%Y").date()
                return last_updated_date
            except ValueError:
                pass  # If date parsing fails, we can return None or handle it as needed
    return None
