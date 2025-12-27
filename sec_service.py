"""
SEC Service - The 'Librarian' of the app.

This script provides:
- Company name/ticker to CIK resolution
- SEC filing metadata retrieval (10-K, 8-K, 10-Q, etc.)
- Filing download functionality (on-demand)
"""

import sys
import os
import re
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
try:
    from edgar import Company, Filing
except ImportError:
    # Fallback: try alternative import
    try:
        from edgartools import Company, Filing  # type: ignore
    except ImportError:
        print("Error: edgartools not installed. Please run: pip install edgartools")
        sys.exit(1)

# Import company service to leverage ticker mapping
try:
    from company_service import fetch_company_lists, _company_tickers
except ImportError:
    print("Warning: company_service.py not found. Ticker mapping will be limited.")
    _company_tickers = None


# SEC required User-Agent header
SEC_USER_AGENT = 'FinScope contact@email.com'

# Configure edgar User-Agent - SEC requires this
try:
    from edgar import set_identity
    set_identity(SEC_USER_AGENT)
except ImportError:
    try:
        import edgar
        if hasattr(edgar, 'set_identity'):
            edgar.set_identity(SEC_USER_AGENT)
    except:
        try:
            import edgartools  # type: ignore
            if hasattr(edgartools, 'set_identity'):
                edgartools.set_identity(SEC_USER_AGENT)
        except:
            pass


def get_cik_from_ticker(ticker: str) -> Optional[str]:
    """
    Attempts to find a CIK using the ticker symbol.
    
    Uses the company_service ticker mapping, then queries SEC EDGAR
    to get the CIK for that ticker.
    
    Args:
        ticker: The ticker symbol (e.g., 'AAPL', 'MSFT')
    
    Returns:
        str: The CIK number (as string, e.g., '0000320193'), or None if not found
    """
    if not ticker or not ticker.strip():
        return None
    
    ticker_upper = ticker.strip().upper()
    
    try:
        # Use edgar to search by ticker
        # The Company class can search by ticker symbol
        company = Company(ticker_upper)
        if company and hasattr(company, 'cik') and company.cik:
            cik_value = company.cik
            # Check if CIK is valid (not -999999999 which means not found)
            if cik_value and cik_value != -999999999:
                cik_str = str(cik_value).zfill(10)  # CIK should be 10 digits
                return cik_str
    except Exception as e:
        pass
    
    return None


def get_cik_from_company_name(company_name: str) -> Optional[str]:
    """
    Searches for CIK by company name.
    
    First tries to use company_service to find the ticker,
    then uses that ticker to get the CIK.
    
    Args:
        company_name: The company name to search for
    
    Returns:
        str: The CIK number (as string), or None if not found
    """
    if not company_name or not company_name.strip():
        return None
    
    # Strategy 1: Use company_service to get ticker, then get CIK from ticker
    try:
        from company_service import get_suggestions
        suggestions = get_suggestions(company_name.strip(), max_results=1)
        if suggestions:
            # Get the ticker from the first suggestion
            ticker = suggestions[0][1]  # (company_name, ticker)
            if ticker and ticker != 'N/A':
                print(f"  Found ticker '{ticker}' from company service, looking up CIK...")
                cik = get_cik_from_ticker(ticker)
                if cik:
                    return cik
    except Exception as e:
        pass
    
    # Strategy 2: Try direct company name search (usually doesn't work well)
    try:
        company = Company(company_name.strip())
        if company and hasattr(company, 'cik'):
            cik_value = company.cik
            # Check if CIK is valid (not -999999999 which means not found)
            if cik_value and cik_value != -999999999:
                return str(cik_value).zfill(10)  # CIK should be 10 digits
    except Exception as e:
        pass
    
    return None


def get_company_cik(company_name_or_ticker: str) -> Optional[str]:
    """
    Main function to resolve company name or ticker to CIK.
    
    Search Logic:
    1. First, try to find CIK using ticker mapping (if it looks like a ticker)
    2. If no ticker found, use Company Name Search to get CIK from SEC EDGAR
    
    Args:
        company_name_or_ticker: Company name or ticker symbol
    
    Returns:
        str: The CIK number (as string), or None if not found
    """
    if not company_name_or_ticker or not company_name_or_ticker.strip():
        return None
    
    input_clean = company_name_or_ticker.strip()
    
    # Heuristic: If input is short (<=5 chars) and all uppercase/letters, likely a ticker
    is_likely_ticker = len(input_clean) <= 5 and input_clean.replace(' ', '').isalpha()
    
    # Strategy 1: Try ticker mapping first (if it looks like a ticker or if we have mapping)
    if is_likely_ticker or (_company_tickers and input_clean.upper() in _company_tickers):
        ticker = input_clean.upper()
        print(f"Attempting to find CIK for ticker: {ticker}")
        cik = get_cik_from_ticker(ticker)
        if cik and cik != '0000000000':
            print(f"✓ Found CIK: {cik}")
            return cik
    
    # Strategy 2: Try company name search (which will use company_service internally)
    print(f"Searching for company: {input_clean}")
    cik = get_cik_from_company_name(input_clean)
    if cik and cik != '0000000000':
        print(f"✓ Found CIK: {cik}")
        return cik
    
    print(f"✗ Could not find CIK for '{input_clean}'")
    return None


def get_filings_list(cik: str, years: int = 3) -> List[Dict[str, str]]:
    """
    Fetches a list of all 10-K, 8-K, 10-Q, etc. filings from the last N years.
    
    Args:
        cik: The CIK number (as string, e.g., '0000320193')
        years: Number of years to look back (default: 3)
    
    Returns:
        List[Dict]: List of filing dictionaries with keys:
            - 'form_type': Form type (e.g., '10-K', '8-K', '10-Q')
            - 'filing_date': Filing date (YYYY-MM-DD)
            - 'accession_number': SEC accession number (unique ID)
            Sorted chronologically (newest first)
    """
    if not cik:
        return []
    
    try:
        # Ensure identity is set (required by SEC)
        try:
            from edgar import set_identity
            set_identity(SEC_USER_AGENT)
        except:
            pass
        
        # Calculate date range (from N years ago to present)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        # Get company object - Company takes CIK as positional argument, not keyword
        # Remove leading zeros for the CIK (Company expects integer or string without leading zeros)
        cik_clean = str(int(cik))  # Convert to int then back to string to remove leading zeros
        company = Company(cik_clean)
        
        # Get filings - edgartools supports filtering by form type and date
        # We'll get all filings and filter for common forms
        common_forms = ['10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '8-K/A']
        
        # Get filings from the company
        # Note: get_filings() doesn't support date filtering, so we get all and filter manually
        try:
            # Get all filings (or filtered by form if supported)
            try:
                filings = company.get_filings(form=common_forms)
            except TypeError:
                # If form parameter not supported, get all filings
                filings = company.get_filings()
        except Exception as e:
            print(f"Error getting filings: {e}")
            filings = []
        
        # Filter by date and form type manually
        filtered_filings = []
        for f in filings:
            # Check form type
            form_type = None
            if hasattr(f, 'form'):
                form_type = f.form
            elif hasattr(f, 'form_type'):
                form_type = f.form_type
            
            if form_type not in common_forms:
                continue
            
            # Check filing date
            filing_date = None
            if hasattr(f, 'filing_date'):
                filing_date = f.filing_date
            elif hasattr(f, 'date'):
                filing_date = f.date
            
            if not filing_date:
                continue
            
            # Convert date to datetime if needed
            from datetime import date as date_type
            if isinstance(filing_date, str):
                try:
                    filing_date = datetime.strptime(filing_date, '%Y-%m-%d')
                except:
                    try:
                        filing_date = datetime.strptime(filing_date, '%Y%m%d')
                    except:
                        continue
            elif isinstance(filing_date, date_type):
                # Convert date to datetime for comparison
                filing_date = datetime.combine(filing_date, datetime.min.time())
            
            # Check if date is within range
            if isinstance(filing_date, datetime) and start_date <= filing_date <= end_date:
                filtered_filings.append(f)
        
        filings = filtered_filings
        
        # Extract metadata
        filings_list = []
        for filing in filings:
            # Handle different date formats and attribute names
            filing_date = None
            if hasattr(filing, 'filing_date'):
                filing_date = filing.filing_date
            elif hasattr(filing, 'date'):
                filing_date = filing.date
            
            if filing_date:
                if hasattr(filing_date, 'strftime'):
                    date_str = filing_date.strftime('%Y-%m-%d')
                elif isinstance(filing_date, str):
                    date_str = filing_date
                else:
                    date_str = str(filing_date)
            else:
                continue  # Skip if no date
            
            # Get form type
            form_type = 'UNKNOWN'
            if hasattr(filing, 'form'):
                form_type = filing.form
            elif hasattr(filing, 'form_type'):
                form_type = filing.form_type
            
            # Get accession number
            accession = None
            if hasattr(filing, 'accession_number'):
                accession = filing.accession_number
            elif hasattr(filing, 'accession'):
                accession = filing.accession
            
            if accession:  # Only add if we have an accession number
                filings_list.append({
                    'form_type': form_type,
                    'filing_date': date_str,
                    'accession_number': accession
                })
        
        # Sort by filing date (newest first)
        filings_list.sort(key=lambda x: x['filing_date'], reverse=True)
        
        return filings_list
        
    except Exception as e:
        print(f"Error fetching filings for CIK {cik}: {e}")
        return []


def download_filing_as_text(accession_number: str, cik: Optional[str] = None) -> Optional[str]:
    """
    Downloads a filing as clean text.
    
    This function does NOT run automatically. It should only be called when needed.
    The output is suitable for AI (Gemini) to read - clean text with no HTML tags.
    
    Args:
        accession_number: The SEC accession number (e.g., '0000320193-24-000001')
        cik: Optional CIK number to speed up lookup (if not provided, will search)
    
    Returns:
        str: Absolute path to the downloaded file, or None if failed
    """
    if not accession_number:
        print("Error: No accession number provided")
        return None
    
    try:
        # Ensure identity is set
        try:
            from edgar import set_identity
            set_identity(SEC_USER_AGENT)
        except:
            pass
        
        # Get the filing - we need to get it from the company object
        filing = None
        
        if cik:
            # Use provided CIK
            cik_clean = str(int(cik))
            company = Company(cik_clean)
            # Search through filings to find the one with matching accession number
            all_filings = company.get_filings()
            for f in all_filings:
                if hasattr(f, 'accession_number') and f.accession_number == accession_number:
                    filing = f
                    break
        else:
            # Try to extract CIK from accession number (first 10 digits)
            try:
                cik_from_accession = accession_number.split('-')[0]
                if len(cik_from_accession) == 10:
                    cik_clean = str(int(cik_from_accession))
                    company = Company(cik_clean)
                    all_filings = company.get_filings()
                    for f in all_filings:
                        if hasattr(f, 'accession_number') and f.accession_number == accession_number:
                            filing = f
                            break
            except:
                pass
        
        if not filing:
            print(f"✗ Could not find filing with accession number {accession_number}")
            return None
        
        # Get company name for filename
        company_name = "Unknown"
        try:
            if hasattr(company, 'name') and company.name:
                company_name = company.name
            elif hasattr(company, 'display_name') and company.display_name:
                company_name = company.display_name
        except:
            pass
        
        # Download as clean text using .text() method
        try:
            text_content = filing.text()
        except Exception as e:
            print(f"✗ Error getting text content: {e}")
            return None
        
        if text_content:
            # Create temporary file using tempfile module (stateless architecture)
            # Use delete=False so we can manually control deletion via cleanup_session
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            temp_file.write(text_content)
            temp_file.close()
            
            abs_path = os.path.abspath(temp_file.name)
            print(f"✓ Downloaded text to temp file: {abs_path}")
            return abs_path
        else:
            print(f"✗ Could not retrieve text for {accession_number}")
            return None
                
    except Exception as e:
        print(f"Error downloading filing {accession_number}: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_filings_list(filings: List[Dict[str, str]]):
    """
    Pretty-prints the filings list.
    
    Args:
        filings: List of filing dictionaries
    """
    if not filings:
        print("\nNo filings found.")
        return
    
    print(f"\n{'='*80}")
    print(f"Found {len(filings)} filing(s) from the last 3 years:")
    print(f"{'='*80}")
    print(f"{'#':<4} {'Form Type':<10} {'Filing Date':<12} {'Accession Number':<30}")
    print(f"{'-'*80}")
    
    for i, filing in enumerate(filings, 1):
        print(f"{i:<4} {filing['form_type']:<10} {filing['filing_date']:<12} {filing['accession_number']:<30}")
    
    print(f"{'='*80}\n")


def validate_downloaded_text_file(filepath: str, preview_chars: int = 500) -> bool:
    """
    Validation script to check downloaded text file.
    
    Checks:
    1. File exists
    2. File is readable
    3. Contains clean text (no HTML tags)
    4. Prints first N characters for verification
    
    Args:
        filepath: Path to the text file to validate
        preview_chars: Number of characters to preview (default: 500)
    
    Returns:
        bool: True if file is valid, False otherwise
    """
    print("\n" + "="*80)
    print("VALIDATION SCRIPT - Text File Check")
    print("="*80)
    
    # Check if file exists
    if not os.path.exists(filepath):
        print(f"✗ ERROR: File does not exist: {filepath}")
        return False
    
    print(f"✓ File exists: {filepath}")
    print(f"  Absolute path: {os.path.abspath(filepath)}")
    
    # Check file size
    file_size = os.path.getsize(filepath)
    print(f"  File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
    if file_size == 0:
        print("✗ ERROR: File is empty")
        return False
    
    # Read and validate content
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for HTML tags
        html_indicators = ['<div', '<table', '<span', '<p>', '<br>', '<html', '<body']
        has_html = any(indicator in content[:5000].lower() for indicator in html_indicators)
        
        if has_html:
            print("⚠ WARNING: File appears to contain HTML tags")
        else:
            print("✓ File contains clean text (no HTML tags detected)")
        
        # Print preview
        print(f"\n{'='*80}")
        print(f"PREVIEW - First {preview_chars} characters:")
        print(f"{'='*80}")
        preview = content[:preview_chars]
        print(preview)
        if len(content) > preview_chars:
            print(f"\n... (showing first {preview_chars} of {len(content):,} total characters)")
        
        # Look for common sections
        print(f"\n{'='*80}")
        print("CONTENT ANALYSIS:")
        print(f"{'='*80}")
        
        sections_found = []
        content_lower = content.lower()
        
        if 'executive summary' in content_lower or 'executive' in content_lower[:5000]:
            sections_found.append("Executive Summary")
        if 'business' in content_lower[:10000]:
            sections_found.append("Business Section")
        if 'risk factors' in content_lower:
            sections_found.append("Risk Factors")
        if 'management' in content_lower[:10000]:
            sections_found.append("Management Discussion")
        
        if sections_found:
            print(f"✓ Found sections: {', '.join(sections_found)}")
        else:
            print("⚠ No common sections detected in preview")
        
        print(f"\n{'='*80}")
        print("VALIDATION COMPLETE")
        print(f"{'='*80}\n")
        
        return True
        
    except Exception as e:
        print(f"✗ ERROR reading file: {e}")
        return False


if __name__ == "__main__":
    """
    Terminal interface for testing the SEC service.
    
    Test command: Enter 'Apple' and it prints a list of filings without downloading.
    """
    print("=" * 80)
    print("SEC Service - Terminal Interface")
    print("=" * 80)
    print("\nCommands:")
    print("  - Type a company name or ticker to see filings list")
    print("  - Type 'download:<accession_number>' to download a filing as clean text")
    print("  - Type 'quit' or 'exit' to exit")
    print("=" * 80)
    
    # Pre-load company lists if available
    try:
        from company_service import fetch_company_lists
        print("\nLoading company lists...")
        fetch_company_lists()
        print("Ready!\n")
    except ImportError:
        print("\nNote: company_service.py not available. Ticker mapping limited.\n")
    
    # Store last CIK for faster downloads
    last_cik = None
    
    while True:
        try:
            user_input = input("\nEnter company name/ticker (or command): ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            # Handle download command
            if user_input.startswith('download:'):
                accession_number = user_input.replace('download:', '').strip()
                
                if not accession_number:
                    print("✗ Error: Please provide an accession number")
                    print("  Usage: download:<accession_number>")
                    continue
                
                print(f"\nDownloading filing: {accession_number}")
                # Use the last known CIK if available (from previous search)
                result = download_filing_as_text(accession_number, cik=last_cik)
                if result:
                    abs_path = os.path.abspath(result)
                    print(f"✓ Successfully downloaded to: {abs_path}")
                    
                    # Run validation automatically
                    validate_downloaded_text_file(result)
                else:
                    print("✗ Download failed")
                continue
            
            # Search for company and get filings
            print(f"\nSearching for: {user_input}")
            cik = get_company_cik(user_input)
            
            if not cik:
                print(f"\n✗ Could not find company '{user_input}'. Please try again.")
                continue
            
            # Store CIK for faster downloads
            last_cik = cik
            
            # Get filings list
            print(f"\nFetching filings for CIK {cik}...")
            filings = get_filings_list(cik, years=3)
            
            # Print the list
            print_filings_list(filings)
            
            if filings:
                print("\nTo download a filing, use:")
                print("  download:<accession_number>")
                print("\nExample:")
                print(f"  download:{filings[0]['accession_number']}")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()


# Validation script can be run directly
if __name__ == "__main__" and len(sys.argv) > 1:
    # Allow running validation from command line
    # Usage: python sec_service.py validate_text <filepath>
    if sys.argv[1] == "validate_text" and len(sys.argv) > 2:
        validate_downloaded_text_file(sys.argv[2])

