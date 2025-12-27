"""
Company Service - Handles company name inputs with suggestion logic.

This script provides:
- Fetching S&P 500 and NASDAQ company lists
- Suggestion functionality for matching company names with fuzzy search
- Flexible company name resolution
"""

import pandas as pd
import requests
from typing import List, Optional, Tuple
from rapidfuzz import fuzz, process


# Global variable to store the company list and name-to-ticker mapping
_company_list: Optional[List[str]] = None
_company_tickers: Optional[dict] = None  # Maps company name -> ticker symbol
_ticker_to_company: Optional[dict] = None  # Cached reverse mapping: ticker -> company name


def fetch_company_lists() -> List[str]:
    """
    Fetches company names from S&P 500 and NASDAQ lists.
    
    Uses Wikipedia as the data source:
    - S&P 500: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
    - NASDAQ 100: https://en.wikipedia.org/wiki/NASDAQ-100
    
    Returns:
        List[str]: A list of unique company names (ticker symbols and company names)
    """
    global _company_list, _company_tickers, _ticker_to_company
    
    if _company_list is not None:
        return _company_list
    
    companies = set()
    tickers = {}  # Maps company name -> ticker symbol
    
    try:
        # Fetch S&P 500 companies
        print("Fetching S&P 500 companies...")
        sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        # Use requests with User-Agent to avoid 403 errors
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(sp500_url, headers=headers)
        response.raise_for_status()
        sp500_tables = pd.read_html(response.text)
        sp500_df = sp500_tables[0]  # First table contains the company list
        
        # Verify we got the right columns
        if 'Security' in sp500_df.columns and 'Symbol' in sp500_df.columns:
            # Create name-to-ticker mapping
            for _, row in sp500_df.iterrows():
                company_name = str(row['Security']).strip()
                ticker = str(row['Symbol']).strip()
                if company_name and ticker:
                    companies.add(company_name)
                    companies.add(ticker)  # Also searchable by ticker
                    tickers[company_name] = ticker
                    tickers[ticker] = ticker  # Ticker maps to itself
        
        print(f"✓ Found {len(sp500_df)} S&P 500 companies")
        
    except Exception as e:
        print(f"✗ Warning: Could not fetch S&P 500 list: {e}")
        print("Using fallback list...")
        # Fallback: Add some common companies with their tickers
        fallback_companies = {
            'Apple Inc.': 'AAPL',
            'Microsoft Corporation': 'MSFT',
            'Amazon.com Inc.': 'AMZN',
            'Alphabet Inc.': 'GOOGL',
            'Meta Platforms Inc.': 'META',
            'Tesla Inc.': 'TSLA',
            'NVIDIA Corporation': 'NVDA',
            'JPMorgan Chase & Co.': 'JPM',
            'Netflix Inc.': 'NFLX',
            'Applied Materials Inc.': 'AMAT',
            'AppFolio Inc.': 'APPF'
        }
        for company, ticker in fallback_companies.items():
            companies.add(company)
            companies.add(ticker)
            tickers[company] = ticker
            tickers[ticker] = ticker
    
    try:
        # Fetch NASDAQ-100 companies
        print("Fetching NASDAQ-100 companies...")
        nasdaq_url = "https://en.wikipedia.org/wiki/NASDAQ-100"
        # Use requests with User-Agent to avoid 403 errors
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(nasdaq_url, headers=headers)
        response.raise_for_status()
        nasdaq_tables = pd.read_html(response.text)
        
        # Try to find the right table - it usually has 'Company' or 'Ticker' column
        nasdaq_df = None
        for table in nasdaq_tables:
            if 'Company' in table.columns or 'Ticker' in table.columns:
                nasdaq_df = table
                break
        
        if nasdaq_df is not None:
            # Add company names with tickers
            if 'Company' in nasdaq_df.columns and 'Ticker' in nasdaq_df.columns:
                for _, row in nasdaq_df.iterrows():
                    company_name = str(row['Company']).strip()
                    ticker = str(row['Ticker']).strip()
                    if company_name and ticker:
                        companies.add(company_name)
                        companies.add(ticker)
                        tickers[company_name] = ticker
                        tickers[ticker] = ticker
            elif 'Company' in nasdaq_df.columns:
                companies.update(nasdaq_df['Company'].str.strip().tolist())
            elif 'Ticker' in nasdaq_df.columns:
                companies.update(nasdaq_df['Ticker'].str.strip().tolist())
            print(f"✓ Found additional NASDAQ companies")
        else:
            print("⚠ Could not find NASDAQ company table structure")
        
    except Exception as e:
        print(f"✗ Warning: Could not fetch NASDAQ list: {e}")
    
    # Remove empty strings and filter out invalid entries
    companies = {c for c in companies if c and len(c.strip()) > 0}
    
    _company_list = sorted(list(companies))
    _company_tickers = tickers
    
    # Pre-build reverse mapping for faster lookups
    _ticker_to_company = {}
    for name, ticker in tickers.items():
        if name != ticker:  # Only map actual company names, not ticker->ticker entries
            _ticker_to_company[ticker] = name
    
    print(f"✓ Total unique companies loaded: {len(_company_list)}")
    
    return _company_list


def get_suggestions(user_input: str, max_results: int = 10) -> List[Tuple[str, str]]:
    """
    Returns a list of company names with their ticker symbols that match the user input.
    
    Uses a three-tier matching approach:
    1. Exact substring matches (case-insensitive) - highest priority
    2. "Starts with" matches (e.g., "palu" matches "Palantir") - very high priority
    3. Fuzzy matches using rapidfuzz for typos and partial matches - lower priority
    
    Args:
        user_input: The string to search for (e.g., 'App', 'netf', 'palu')
        max_results: Maximum number of suggestions to return (default: 10)
    
    Returns:
        List[Tuple[str, str]]: List of (company_name, ticker) tuples, sorted by relevance
    """
    if not user_input or not user_input.strip():
        return []
    
    company_list = fetch_company_lists()
    tickers = _company_tickers or {}
    ticker_to_company = _ticker_to_company or {}
    user_input_clean = user_input.strip()
    user_input_lower = user_input_clean.lower()
    
    # Helper function to get company name and ticker
    def get_company_info(match: str) -> Tuple[str, str]:
        """Returns (company_name, ticker) for a match."""
        # Check if match is a ticker symbol
        if match in ticker_to_company:
            company_name = ticker_to_company[match]
            return (company_name, match)
        # Otherwise, match is a company name
        ticker = tickers.get(match, 'N/A')
        return (match, ticker)
    
    # Tier 1: Exact substring matches (highest priority)
    exact_matches = [
        company for company in company_list
        if user_input_lower in company.lower()
    ]
    exact_matches_set = set(exact_matches)  # For faster lookups
    
    # Tier 2: "Starts with" matches (very high priority - e.g., "palu" matches "Palantir")
    starts_with_matches = [
        company for company in company_list
        if company.lower().startswith(user_input_lower) and company not in exact_matches_set
    ]
    starts_with_matches_set = set(starts_with_matches)  # For faster lookups
    
    # Tier 3a: Prefix matches (e.g., "palu" -> "Palantir" because both start with "pal")
    # This must be done explicitly to catch companies that might not score well in fuzzy matching
    prefix_matches = []
    if len(user_input_lower) >= 3:
        input_prefix = user_input_lower[:3]
        # Only check companies not already matched (optimization: use set for fast lookup)
        already_matched = exact_matches_set | starts_with_matches_set
        for company in company_list:
            if company not in already_matched:
                company_lower = company.lower()
                if company_lower.startswith(input_prefix):
                    prefix_matches.append((company, 80))  # High score for prefix match
    
    # Early exit: If we have enough exact/starts_with/prefix matches, skip expensive fuzzy matching
    combined_exact_count = len(exact_matches) + len(starts_with_matches) + len(prefix_matches)
    if combined_exact_count >= max_results:
        # We have enough high-quality matches, skip fuzzy matching for speed
        fuzzy_matches = []
    else:
        # Tier 3b: Fuzzy matches for typos and partial matches
        # Optimized: Use single scoring method + prefix boost for speed
        fuzzy_matches = []
        if len(user_input_clean) >= 3:  # Only use fuzzy for inputs of 3+ characters
            # Use only partial_ratio (fastest and best for partial matches)
            # Limit to smaller set for speed (we only need enough to fill remaining slots)
            remaining_slots = max_results - combined_exact_count
            already_matched = exact_matches_set | starts_with_matches_set | {p[0] for p in prefix_matches}
            
            fuzzy_results = process.extract(
                user_input_clean,
                company_list,
                scorer=fuzz.partial_ratio,
                limit=remaining_slots * 3  # Get more candidates to account for filtering
            )
            
            # Process results and boost prefix matches
            input_prefix = user_input_lower[:3] if len(user_input_lower) >= 3 else ""
            for company, score, _ in fuzzy_results:
                if company in already_matched:
                    continue
                
                # Boost score if company starts with same prefix (additional boost beyond prefix_matches)
                company_lower = company.lower()
                if input_prefix and company_lower.startswith(input_prefix):
                    score = min(score + 25, 100)  # Significant boost for prefix match
                
                if score >= 50:  # Minimum threshold
                    fuzzy_matches.append((company, score))
    
    # Combine results with proper prioritization
    seen = set()
    results = []
    
    # Add exact substring matches first (highest priority)
    for company in exact_matches:
        if company not in seen:
            company_info = get_company_info(company)
            if company_info[0] not in seen:
                results.append(company_info)
                seen.add(company_info[0])
                seen.add(company)
    
    # Add "starts with" matches (very high priority)
    for company in starts_with_matches:
        if company not in seen and len(results) < max_results:
            company_info = get_company_info(company)
            if company_info[0] not in seen:
                results.append(company_info)
                seen.add(company_info[0])
                seen.add(company)
    
    # Add prefix matches (high priority - e.g., "palu" -> "Palantir")
    for company, score in prefix_matches:
        if company not in seen and len(results) < max_results:
            company_info = get_company_info(company)
            if company_info[0] not in seen:
                results.append(company_info)
                seen.add(company_info[0])
                seen.add(company)
    
    # Add fuzzy matches sorted by score (highest first)
    fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
    for company, score in fuzzy_matches:
        if company not in seen and len(results) < max_results:
            company_info = get_company_info(company)
            if company_info[0] not in seen:
                results.append(company_info)
                seen.add(company_info[0])
                seen.add(company)
    
    # Return top matches, limited by max_results
    return results[:max_results]


def resolve_company(name: str) -> str:
    """
    Resolves a company name input to a canonical company name from our list.
    
    If the name matches a company in our suggestion list (exact or very close fuzzy match),
    it returns the canonical company name from our list. Otherwise, it accepts any string 
    as valid and returns it as-is (for companies not in S&P 500/NASDAQ).
    
    Args:
        name: The company name to resolve
    
    Returns:
        str: The resolved company name (canonical form if found, otherwise the input as-is)
    """
    if not name or not name.strip():
        return ""
    
    company_list = fetch_company_lists()
    name_clean = name.strip()
    
    # Check for exact match (case-insensitive) first
    for company in company_list:
        if company.lower() == name_clean.lower():
            return company  # Return the canonical form from our list
    
    # If no exact match, try fuzzy matching for very close matches
    if len(name_clean) >= 3:
        best_match = process.extractOne(
            name_clean,
            company_list,
            scorer=fuzz.ratio
        )
        # Only use fuzzy match if it's very close (score >= 90)
        if best_match and best_match[1] >= 90:
            return best_match[0]
    
    # If not found in list, accept it as-is (flexible input - allows custom company names)
    return name_clean


if __name__ == "__main__":
    """
    Terminal interface for testing the company service.
    """
    print("=" * 60)
    print("Company Service - Terminal Interface")
    print("=" * 60)
    print("\nCommands:")
    print("  - Type a company name to see suggestions")
    print("  - Type 'resolve:<name>' to resolve a company name")
    print("  - Type 'quit' or 'exit' to exit")
    print("=" * 60)
    
    # Pre-load the company list
    print("\nLoading company lists...")
    fetch_company_lists()
    print("Ready!\n")
    
    while True:
        try:
            user_input = input("\nEnter company name (or command): ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            # Handle resolve command
            if user_input.startswith('resolve:'):
                company_name = user_input.replace('resolve:', '').strip()
                resolved = resolve_company(company_name)
                print(f"\nResolved: '{resolved}'")
                continue
            
            # Show suggestions
            suggestions = get_suggestions(user_input)
            
            if suggestions:
                print(f"\nFound {len(suggestions)} suggestion(s):")
                for i, (company, ticker) in enumerate(suggestions, 1):
                    print(f"  {i}. {company} ({ticker})")
            else:
                print(f"\nNo suggestions found for '{user_input}'")
                print("(This is okay - you can still use this name)")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
