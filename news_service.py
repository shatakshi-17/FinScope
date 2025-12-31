"""
News Service - The Intelligence News Agent.

This script provides:
- Fetching relevant news articles from Google News RSS
- Relevance scoring and ranking of articles
- Using article headlines as snippets (fast, no deep scraping)
"""

import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from thefuzz import fuzz, process
from dateutil import parser as date_parser
import urllib.parse
import requests
from urllib.parse import urlparse, parse_qs


# Preferred financial news domains (get priority boost, but all domains are allowed)
PREFERRED_DOMAINS = [
    'bloomberg.com', 'reuters.com', 'wsj.com', 'cnbc.com', 'marketwatch.com',
    'ft.com', 'finance.yahoo.com', 'seekingalpha.com', 'investing.com',
    'fool.com', 'forbes.com', 'barrons.com', 'businessinsider.com', 'apnews.com'
]


def extract_actual_url(google_news_url: str) -> Optional[str]:
    """
    Extracts the actual article URL from a Google News redirect URL.
    
    Google News URLs are redirects. We follow them to get the actual article URL.
    Uses a very fast timeout to minimize latency.
    
    Args:
        google_news_url: The Google News redirect URL
    
    Returns:
        str: The actual article URL, or None if extraction fails
    """
    try:
        # Follow redirect to get actual URL
        # Use HEAD request with very short timeout for speed (1 second)
        response = requests.head(google_news_url, allow_redirects=True, timeout=1, 
                                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        final_url = response.url if hasattr(response, 'url') else None
        if final_url and final_url != google_news_url and 'news.google.com' not in final_url:
            return final_url
        return None
    except:
        # If HEAD fails quickly, don't try GET (saves time)
        return None


def get_domain_from_url(url: str) -> Optional[str]:
    """
    Extracts the domain from a URL.
    
    Args:
        url: The URL
    
    Returns:
        str: The domain (e.g., 'reuters.com'), or None
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return None


def is_preferred_domain(url: str) -> bool:
    """
    Checks if the URL belongs to a preferred financial news domain.
    
    Args:
        url: The URL to check
    
    Returns:
        bool: True if domain is preferred (gets priority boost)
    """
    domain = get_domain_from_url(url)
    if not domain:
        return False
    
    # Check if any preferred domain matches
    for preferred in PREFERRED_DOMAINS:
        if domain == preferred or domain.endswith('.' + preferred):
            return True
    
    return False


def fetch_google_news_rss(company_name: str, num_results: int = 50, use_strict_query: bool = True) -> List[Dict[str, str]]:
    """
    Fetches news articles from Google News RSS feed with advanced query syntax.
    
    Args:
        company_name: The company name to search for
        num_results: Maximum number of results to fetch (default: 50)
        use_strict_query: If True, use exact phrase matching with boolean operators
    
    Returns:
        List[Dict]: List of article dictionaries with keys:
            - 'title': Article title
            - 'link': Article URL
            - 'published': Publication date
            - 'summary': Article summary/description
    """
    # Construct Google News RSS URL with advanced query syntax
    if use_strict_query:
        # Use smarter query that allows shorthand while excluding noise
        # Format: ("Full Name" OR "Shorthand") AND (keywords including ticker)
        # Extract shorthand if company name has multiple words (e.g., "Palo Alto Networks" -> "Palo Alto")
        company_words = company_name.split()
        if len(company_words) >= 2:
            # Use first two words as shorthand (e.g., "Palo Alto" from "Palo Alto Networks")
            shorthand = ' '.join(company_words[:2])
            exact_phrase = f'"{company_name}" OR "{shorthand}"'
        else:
            exact_phrase = f'"{company_name}"'
        
        # Try to extract ticker if company name suggests it (e.g., for Palo Alto Networks, ticker is PANW)
        # For now, we'll add common tickers or let the user specify
        # Keywords include business terms and potential ticker
        keywords = 'stock OR earnings OR cybersecurity OR revenue OR PANW OR partnership OR deal OR acquisition OR merger OR lawsuit OR regulatory OR financial OR quarterly OR annual OR sec OR filing'
        query = f'({exact_phrase}) AND ({keywords})'
    else:
        # Fallback: simple query with location exclusion
        query = f'{company_name} -location'
    
    # URL encode the query
    encoded_query = urllib.parse.quote_plus(query)
    # Add when parameter for last 30 days (Google News uses when:30d)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en&when=30d"
    
    try:
        # Parse the RSS feed
        feed = feedparser.parse(rss_url)
        
        articles = []
        processed = 0
        # Process up to num_results entries
        max_entries = num_results
        for entry in feed.entries[:max_entries]:
            processed += 1
            
            # Extract publication date
            published_date = None
            if hasattr(entry, 'published'):
                try:
                    # Parse the date string
                    published_date = entry.published
                except:
                    pass
            
            google_link = entry.link if hasattr(entry, 'link') else ''
            
            if not google_link:
                continue
            
            title = entry.title if hasattr(entry, 'title') else ''
            summary = entry.summary if hasattr(entry, 'summary') else ''
            
            # Optimize: Skip URL extraction for speed - infer source from title/summary first
            # Only extract URL if we can't infer source (saves time on most articles)
            title_lower = (title + ' ' + summary).lower()
            source = None
            actual_url = google_link  # Default to Google link (faster)
            
            # Try to infer source from title/summary first (no HTTP request needed)
            domain_hints = {
                'bloomberg': 'bloomberg.com',
                'reuters': 'reuters.com',
                'wsj': 'wsj.com',
                'wall street journal': 'wsj.com',
                'cnbc': 'cnbc.com',
                'marketwatch': 'marketwatch.com',
                'financial times': 'ft.com',
                'ft.com': 'ft.com',
                'yahoo finance': 'finance.yahoo.com',
                'seeking alpha': 'seekingalpha.com',
                'investing.com': 'investing.com',
                'motley fool': 'fool.com',
                'fool.com': 'fool.com',
                'forbes': 'forbes.com',
                "barron's": 'barrons.com',
                'barrons': 'barrons.com',
                'business insider': 'businessinsider.com',
                'ap news': 'apnews.com',
                'associated press': 'apnews.com',
                'sc media': 'scmagazine.com',
                'sc world': 'scworld.com',
                'scmagazine': 'scmagazine.com',
                'sc magazine': 'scmagazine.com'
            }
            
            # Check if we can infer source from title/summary
            for hint, domain in domain_hints.items():
                if hint in title_lower:
                    source = domain
                    break
            
            # Only extract URL if we couldn't infer source AND it might be a preferred domain
            # This skips slow HTTP requests for most articles
            if not source:
                # Quick check: try URL extraction only if title suggests it might be preferred
                # (This is a heuristic to avoid unnecessary requests)
                might_be_preferred = any(hint in title_lower for hint in ['bloomberg', 'reuters', 'wsj', 'cnbc', 'marketwatch', 'ft', 'yahoo', 'forbes'])
                if might_be_preferred:
                    # Only extract URL for potentially preferred domains
                    extracted_url = extract_actual_url(google_link)
                    if extracted_url:
                        actual_url = extracted_url
                        source = get_domain_from_url(extracted_url)
                    else:
                        # Extraction failed, use Google link
                        actual_url = google_link
                else:
                    # Not likely a preferred domain, skip extraction (use Google link)
                    actual_url = google_link
            else:
                # We inferred source, use Google link (no extraction needed)
                actual_url = google_link
            
            # If we still don't have a source, try multiple methods
            if not source:
                # Method 1: Try to extract from actual URL
                if actual_url and 'news.google.com' not in actual_url:
                    source = get_domain_from_url(actual_url)
                
                # Method 2: Try to extract from Google News URL structure
                if not source and google_link:
                    try:
                        # Google News URLs sometimes have domain info in the path
                        parsed = urlparse(google_link)
                        # Check if there's domain info in query params
                        params = parse_qs(parsed.query)
                        if 'url' in params:
                            url_param = params['url'][0]
                            source = get_domain_from_url(url_param)
                    except:
                        pass
                
                # Method 3: Try to extract from summary/title if it mentions a source
                if not source:
                    combined_text = (title + ' ' + summary).lower()
                    # Look for common source patterns in text
                    source_patterns = [
                        (r'via\s+([a-z0-9.-]+\.(com|net|org|io))', 1),
                        (r'from\s+([a-z0-9.-]+\.(com|net|org|io))', 1),
                        (r'@([a-z0-9.-]+\.(com|net|org|io))', 1),
                        (r'([a-z0-9.-]+\.(com|net|org|io))\s+reports', 1),
                    ]
                    import re
                    for pattern, group in source_patterns:
                        match = re.search(pattern, combined_text)
                        if match:
                            source = match.group(group)
                            break
                
                # Method 4: Add more domain hints for common sources
                if not source:
                    title_lower = (title + ' ' + summary).lower()
                    extended_domain_hints = {
                        'sc media': 'scmagazine.com',
                        'sc world': 'scworld.com',
                        'scmagazine': 'scmagazine.com',
                        'unit 42': 'unit42.paloaltonetworks.com',
                        'palo alto networks': 'paloaltonetworks.com',
                        'techcrunch': 'techcrunch.com',
                        'the verge': 'theverge.com',
                        'ars technica': 'arstechnica.com',
                        'zdnet': 'zdnet.com',
                        'cnet': 'cnet.com',
                        'engadget': 'engadget.com',
                        'wired': 'wired.com',
                        'gizmodo': 'gizmodo.com',
                    }
                    for hint, domain in extended_domain_hints.items():
                        if hint in title_lower:
                            source = domain
                            break
                
                # Method 5: Last resort - try to parse from link structure
                if not source and actual_url:
                    # Sometimes the domain is in the path or subdomain
                    try:
                        parsed = urlparse(actual_url)
                        # Check if it's a subdomain we can identify
                        hostname = parsed.netloc.lower()
                        if hostname and '.' in hostname:
                            # Remove www. and common prefixes
                            hostname = hostname.replace('www.', '')
                            # Take the main domain part
                            parts = hostname.split('.')
                            if len(parts) >= 2:
                                # Get last two parts (e.g., example.com)
                                source = '.'.join(parts[-2:])
                    except:
                        pass
                
                # Final fallback
                if not source:
                    source = 'Unknown'
            
            articles.append({
                'title': title,
                'link': actual_url,  # Use actual URL if extracted, otherwise Google link
                'google_link': google_link,  # Keep original for fallback
                'published': published_date,
                'summary': summary,
                'source': source or 'Unknown'
            })
            
            # Stop when we have enough articles
            if len(articles) >= num_results:
                break
        
        return articles
    
    except Exception as e:
        print(f"Error fetching RSS feed: {e}")
        return []


def score_relevance(article: Dict[str, str], company_name: str) -> float:
    """
    Scores an article's relevance to the company.
    
    Scoring logic:
    - Exact company name in title: 100 points
    - Partial match in title (fuzzy): 50-99 points
    - Company name in summary: 30 points
    - Finance/administrative keywords: +20 bonus
    - Base score: 0-50 points (fuzzy match on title)
    - REQUIRES company name context (not just random word matches)
    
    Args:
        article: Article dictionary with 'title' and 'summary'
        company_name: The company name to match against
    
    Returns:
        float: Relevance score (0-120, capped at 120), or 0 if not relevant
    """
    title = article.get('title', '').lower()
    summary = article.get('summary', '').lower()
    company_lower = company_name.lower()
    combined_text = title + ' ' + summary
    
    # CRITICAL: Check if company name appears as a whole phrase (not just random words)
    # Split company name into words
    company_words = [w for w in company_lower.split() if len(w) > 2]  # Only meaningful words
    
    # Require at least 2 words from company name to appear together (context requirement)
    if len(company_words) >= 2:
        # Check if at least 2 consecutive words from company name appear together
        company_phrases = []
        for i in range(len(company_words) - 1):
            phrase = f"{company_words[i]} {company_words[i+1]}"
            company_phrases.append(phrase)
        
        # Also check for 3-word phrases if available
        if len(company_words) >= 3:
            for i in range(len(company_words) - 2):
                phrase = f"{company_words[i]} {company_words[i+1]} {company_words[i+2]}"
                company_phrases.append(phrase)
        
        # Require at least one phrase match (ensures context, not random word matches)
        has_phrase_match = any(phrase in combined_text for phrase in company_phrases)
        
        # If no phrase match, check if all major words appear (but require they're close together)
        if not has_phrase_match:
            # Check if all words appear, but require they're within reasonable distance
            all_words_present = all(word in combined_text for word in company_words)
            if all_words_present:
                # Check word proximity - words should be close together
                word_positions = []
                for word in company_words:
                    pos = combined_text.find(word)
                    if pos != -1:
                        word_positions.append(pos)
                
                if len(word_positions) == len(company_words):
                    # Check if words are within reasonable distance (relaxed to 200 chars)
                    word_positions.sort()
                    max_distance = max(word_positions) - min(word_positions)
                    if max_distance > 200:  # Words too far apart = likely not about the company
                        # Give a low score instead of 0
                        return 15.0  # Low relevance but still include it
            else:
                # Not all words present - give low score instead of 0
                return 10.0
    elif len(company_words) == 1:
        # Single word company name - require it appears with context
        word = company_words[0]
        # Common words that need context (like "networks", "systems", "solutions")
        generic_words = ['networks', 'systems', 'solutions', 'technologies', 'services', 
                         'group', 'holdings', 'partners', 'capital', 'ventures']
        if word in generic_words:
            # Require company name appears as whole or with other identifying words
            if word not in combined_text:
                return 0.0
            # Check if it appears with company-specific context
            if company_lower not in combined_text:
                # Very low score for generic word matches without full name
                return 10.0  # Very low relevance
        else:
            # Non-generic word - check if it appears
            if word not in combined_text:
                return 0.0
            # If full name doesn't appear, give low score
            if company_lower not in combined_text:
                return 15.0  # Low relevance but still include
    
    # Finance/administrative keywords that boost relevance
    finance_keywords = [
        'earnings', 'revenue', 'profit', 'financial', 'quarterly', 'annual',
        'sec', 'filing', '10-k', '10-q', '8-k', 'regulatory', 'compliance',
        'antitrust', 'lawsuit', 'legal', 'settlement', 'fine', 'penalty',
        'merger', 'acquisition', 'ipo', 'stock', 'share', 'dividend',
        'ceo', 'cfo', 'executive', 'board', 'governance', 'audit',
        'regulation', 'policy', 'government', 'agency', 'investigation'
    ]
    
    # Check for finance/administrative keywords
    finance_bonus = 0.0
    for keyword in finance_keywords:
        if keyword in combined_text:
            finance_bonus = 20.0
            break
    
    # Check if article is from preferred domain (priority boost)
    preferred_bonus = 0.0
    article_link = article.get('link', '')
    if article_link and is_preferred_domain(article_link):
        preferred_bonus = 15.0
    
    # Check for exact company name in title
    if company_lower in title:
        return min(100.0 + finance_bonus + preferred_bonus, 120.0)
    
    # Check for partial exact match (word boundaries)
    if len(company_words) > 1:
        # Check if all words appear in title
        all_words_present = all(word in title for word in company_words)
        if all_words_present:
            return min(95.0 + finance_bonus + preferred_bonus, 120.0)
    
    # Fuzzy match on title (only if we passed context checks above)
    title_score = fuzz.partial_ratio(company_lower, title)
    
    # Check if company name appears in summary
    summary_bonus = 30.0 if company_lower in summary else 0.0
    
    # Combine scores (title is more important)
    final_score = max(title_score, summary_bonus) + finance_bonus + preferred_bonus
    
    return min(final_score, 120.0)  # Cap at 120 (with bonuses)


def are_headlines_similar(headline1: str, headline2: str, threshold: float = 0.60) -> bool:
    """
    Checks if two headlines are about the same event.
    
    Uses multiple strategies:
    1. Key entity/topic matching (e.g., "Italy", "Tim Cook", "Nike stock")
    2. Key phrase matching (e.g., "Italy antitrust", "fines Apple")
    3. Fuzzy similarity matching
    
    Args:
        headline1: First headline
        headline2: Second headline
        threshold: Similarity threshold (0-1), default 0.60
    
    Returns:
        bool: True if headlines are similar (same event)
    """
    if not headline1 or not headline2:
        return False
    
    h1_lower = headline1.lower()
    h2_lower = headline2.lower()
    
    # Extract key entities and topics that indicate same story
    # Common patterns: country names, person names, company + topic combinations
    key_entities = [
        'italy', 'tim cook', 'nike', 'apple', 'microsoft', 'google', 'amazon',
        'tesla', 'meta', 'nvidia', 'jpmorgan', 'bank of america', 'goldman sachs'
    ]
    
    # Check if both headlines mention the same key entity
    h1_entities = [e for e in key_entities if e in h1_lower]
    h2_entities = [e for e in key_entities if e in h2_lower]
    shared_entities = set(h1_entities) & set(h2_entities)
    
    # If they share a key entity, check for topic overlap
    if shared_entities:
        # Key topics that indicate same story
        key_topics = [
            'antitrust', 'fine', 'fines', 'lawsuit', 'settlement', 'regulator',
            'stock', 'shares', 'earnings', 'revenue', 'profit', 'quarterly',
            'ceo', 'executive', 'resign', 'hire', 'acquisition', 'merger'
        ]
        h1_topics = [t for t in key_topics if t in h1_lower]
        h2_topics = [t for t in key_topics if t in h2_lower]
        shared_topics = set(h1_topics) & set(h2_topics)
        
        # If same entity + same topic, definitely same story
        if shared_topics:
            return True
        
        # If same entity and high phrase overlap, likely same story
        h1_words = set(h1_lower.split())
        h2_words = set(h2_lower.split())
        # Remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
        h1_keywords = h1_words - common_words
        h2_keywords = h2_words - common_words
        keyword_overlap = len(h1_keywords & h2_keywords) / max(len(h1_keywords), len(h2_keywords), 1)
        if keyword_overlap > 0.4:  # 40% keyword overlap with same entity
            return True
    
    # Extract key phrases (2-word combinations) that indicate same story
    h1_words = h1_lower.split()
    h2_words = h2_lower.split()
    
    h1_phrases = set()
    h2_phrases = set()
    
    for i in range(len(h1_words) - 1):
        phrase = f"{h1_words[i]} {h1_words[i+1]}"
        if len(phrase) > 5:  # Only meaningful phrases
            h1_phrases.add(phrase)
    
    for i in range(len(h2_words) - 1):
        phrase = f"{h2_words[i]} {h2_words[i+1]}"
        if len(phrase) > 5:
            h2_phrases.add(phrase)
    
    # If they share 2+ key phrases, likely same story
    shared_phrases = h1_phrases.intersection(h2_phrases)
    if len(shared_phrases) >= 2:
        return True
    
    # Also check full similarity ratio
    similarity = fuzz.ratio(h1_lower, h2_lower) / 100.0
    
    # Use partial ratio for better detection
    partial_similarity = fuzz.partial_ratio(h1_lower, h2_lower) / 100.0
    
    return similarity >= threshold or partial_similarity >= 0.65


def has_exact_company_match(article: Dict[str, str], company_name: str) -> bool:
    """
    Refined relevance check: Accepts full name OR shorthand, rejects generic words.
    
    Acceptable: "Palo Alto Networks" OR "Palo Alto"
    Rejected: Generic "Networks" or "Technologies" without the unique identifier.
    
    Args:
        article: Article dictionary with 'title' and 'summary'
        company_name: The company name to match (e.g., "Palo Alto Networks")
    
    Returns:
        bool: True if acceptable match found (case-insensitive)
    """
    title = article.get('title', '')
    summary = article.get('summary', '')
    combined_text = (title + ' ' + summary).lower()
    company_lower = company_name.lower()
    
    # Extract shorthand (first 2 words) if company name has multiple words
    company_words = company_name.split()
    if len(company_words) >= 2:
        shorthand = ' '.join(company_words[:2]).lower()  # e.g., "palo alto"
    else:
        shorthand = company_lower
    
    # Check if full name appears
    if company_lower in combined_text:
        return True
    
    # Check if shorthand appears (e.g., "Palo Alto")
    if shorthand in combined_text and len(shorthand.split()) >= 2:
        return True
    
    # Reject if only generic words appear (like "Networks" or "Technologies" without the unique identifier)
    # Common generic words that need context
    generic_words = ['networks', 'technologies', 'systems', 'solutions', 'services', 'group', 'holdings']
    company_words_lower = [w.lower() for w in company_words]
    
    # If company name contains generic words, require the unique identifier (shorthand) to be present
    has_generic = any(word in generic_words for word in company_words_lower)
    if has_generic:
        # Must have the unique identifier (shorthand), not just the generic word
        if len(company_words) >= 2:
            # Check if shorthand is present
            if shorthand not in combined_text:
                return False
    
    return False


def get_company_intelligence(company_name: str) -> List[Dict[str, str]]:
    """
    Main function to get company intelligence from news articles.
    
    Process:
    1. Fetch articles from Google News RSS (all domains, preferred get priority)
    2. Score and rank articles by relevance (preferred domains get +15 boost)
    3. Filter for topic diversity (max 1 article per similar event, prefer credible sources)
    4. Use article headlines as snippets (fast, no deep scraping)
    5. Return list of dictionaries with sentence, date, and link
    
    Args:
        company_name: The company name to search for
    
    Returns:
        List[Dict]: List of dictionaries with keys:
            - 'title': Article headline
            - 'url': Article URL
            - 'published_at': Publication date (YYYY-MM-DD format)
    """
    if not company_name or not company_name.strip():
        return []
    
    company_name_clean = company_name.strip()
    
    print(f"Fetching news articles for: {company_name_clean}")
    
    # Step 1: Try strict query first (optimized: fetch 25 articles for better latency)
    print("Trying strict query with exact phrase matching...")
    articles = fetch_google_news_rss(company_name_clean, num_results=25, use_strict_query=True)
    
    # Step 2: Apply strict relevance filtering with early exit optimization
    if articles:
        print(f"Found {len(articles)} articles from RSS")
        print("Applying refined relevance filter (full name OR shorthand required)...")
        relevant_articles = []
        # Process articles and stop once we have enough candidates (early exit optimization)
        for article in articles:
            if has_exact_company_match(article, company_name_clean):
                relevant_articles.append(article)
                # Early exit: If we have 20+ relevant articles, we likely have enough for 10 after filtering
                if len(relevant_articles) >= 20:
                    print(f"Early exit: Found {len(relevant_articles)} relevant articles, stopping processing")
                    break
        
        articles = relevant_articles
        print(f"After refined filtering: {len(articles)} relevant articles")
    
    # Step 3: Fallback if strict query returned 0 results
    if not articles:
        print("Strict query returned 0 results. Trying fallback query...")
        articles = fetch_google_news_rss(company_name_clean, num_results=25, use_strict_query=False)
        
        if articles:
            print(f"Found {len(articles)} articles from fallback query")
            # Still apply strict relevance filter
            relevant_articles = []
            for article in articles:
                if has_exact_company_match(article, company_name_clean):
                    relevant_articles.append(article)
            articles = relevant_articles
            print(f"After strict filtering: {len(articles)} relevant articles")
    
    if not articles:
        print("No relevant articles found after filtering")
        return []
    
    # Step 4: Filter for date (last 30 days) and sort by date (most recent first)
    # Start with 30 days, but extend if we don't have enough articles
    date_ranges = [30, 60, 90]  # Try 30, then 60, then 90 days
    dated_articles = []
    date_range_used = 30
    
    for days_back in date_ranges:
        cutoff_date = datetime.now() - timedelta(days=days_back)
        dated_articles = []
        
        for article in articles:
            published_date = article.get('published', '')
            if published_date:
                try:
                    parsed_date = date_parser.parse(published_date)
                    # Check if article is within date range
                    if parsed_date >= cutoff_date:
                        dated_articles.append((article, parsed_date))
                except:
                    # If date parsing fails, include it anyway (better to have it than not)
                    dated_articles.append((article, datetime.now()))
            else:
                # If no date, include it (assume recent)
                dated_articles.append((article, datetime.now()))
        
        # Sort by date (most recent first)
        dated_articles.sort(key=lambda x: x[1], reverse=True)
        
        print(f"After date filtering (last {days_back} days): {len(dated_articles)} articles")
        
        # If we have at least 15 articles, we should be able to get 10 after diversity filtering
        if len(dated_articles) >= 15:
            date_range_used = days_back
            break
    
    if not dated_articles:
        print("No articles found within date range")
        return []
    
    # Step 5: Filter for topic diversity with early exit (stop once we have 10)
    max_per_event = 1
    filtered_articles = []
    headline_groups = {}
    
    for article, article_date in dated_articles:
        title = article.get('title', '')
        if not title:
            continue
        
        # Check if this headline is similar to any existing group
        added_to_group = False
        for group_key, group_articles in headline_groups.items():
            if are_headlines_similar(title, group_key):
                # Allow max_per_event articles per similar event
                if len(group_articles) >= max_per_event:
                    existing_article, existing_date = group_articles[0]
                    # Prefer preferred domain sources, then more recent date
                    article_is_preferred = is_preferred_domain(article.get('link', ''))
                    existing_is_preferred = is_preferred_domain(existing_article.get('link', ''))
                    
                    # Replace if: new is preferred and old isn't, OR both same preference but new is more recent
                    if (article_is_preferred and not existing_is_preferred) or \
                       (article_is_preferred == existing_is_preferred and article_date > existing_date):
                        group_articles[0] = (article, article_date)
                        for i, (fa, fd) in enumerate(filtered_articles):
                            if fa == existing_article:
                                filtered_articles[i] = (article, article_date)
                                break
                else:
                    group_articles.append((article, article_date))
                    filtered_articles.append((article, article_date))
                added_to_group = True
                break
        
        if not added_to_group:
            headline_groups[title] = [(article, article_date)]
            filtered_articles.append((article, article_date))
        
        # Early exit: Once we have 10 valid articles, stop processing
        if len(filtered_articles) >= 10:
            print(f"Early exit: Found 10 valid articles, stopping processing")
            break
    
    # If we still don't have 10, allow 2 articles per similar event and continue
    if len(filtered_articles) < 10:
        print(f"Only {len(filtered_articles)} articles after diversity filtering. Allowing 2 articles per similar event...")
        max_per_event = 2
        
        # Continue from where we left off
        processed_indices = set()
        for fa, _ in filtered_articles:
            for idx, (art, _) in enumerate(dated_articles):
                if art == fa:
                    processed_indices.add(idx)
                    break
        
        for idx, (article, article_date) in enumerate(dated_articles):
            if idx in processed_indices:
                continue
                
            title = article.get('title', '')
            if not title:
                continue
            
            added_to_group = False
            for group_key, group_articles in headline_groups.items():
                if are_headlines_similar(title, group_key):
                    if len(group_articles) < max_per_event:
                        group_articles.append((article, article_date))
                        filtered_articles.append((article, article_date))
                        added_to_group = True
                    break
            
            if not added_to_group:
                headline_groups[title] = [(article, article_date)]
                filtered_articles.append((article, article_date))
            
            # Early exit: Once we have 10 valid articles, stop processing
            if len(filtered_articles) >= 10:
                print(f"Early exit: Found 10 valid articles, stopping processing")
                break
    
    # Step 6: Get top 10 most recent articles
    # Sort by date again (most recent first)
    filtered_articles.sort(key=lambda x: x[1], reverse=True)
    top_articles = filtered_articles[:10]
    
    print(f"Selected top {len(top_articles)} most recent articles after diversity filtering (date range: {date_range_used} days)")
    
    # Step 7: Format results with required fields
    results = []
    for article, article_date in top_articles:
        title = article.get('title', '')
        link = article.get('link', '')
        
        if not title or not link:
            continue
        
        # Parse publication date to YYYY-MM-DD format
        published_at = article_date.strftime('%Y-%m-%d') if isinstance(article_date, datetime) else article.get('published', '')
        if published_at and not isinstance(article_date, datetime):
            try:
                parsed_date = date_parser.parse(published_at)
                published_at = parsed_date.strftime('%Y-%m-%d')
            except:
                published_at = ''
        
        results.append({
            'title': title.strip(),
            'url': link,
            'published_at': published_at
        })
    
    print(f"\n✓ Successfully processed {len(results)} articles")
    return results


def print_intelligence_results(results: List[Dict[str, str]]):
    """
    Pretty-prints the intelligence results.
    
    Format: [Number]) [Title] Date: [Date] Link: [URL]
    
    Args:
        results: List of result dictionaries with keys: title, url, published_at
    """
    if not results:
        print("\nNo results found.")
        return
    
    print(f"\n{'='*80}")
    print(f"Company Intelligence - {len(results)} Articles")
    print(f"{'='*80}\n")
    
    for i, result in enumerate(results, 1):
        title = result.get('title', 'No content available')
        url = result.get('url', 'N/A')
        published_at = result.get('published_at', 'N/A')
        
        print(f"{i}) {title} Date: {published_at} Link: {url}\n")


def get_verified_news(query_name: str) -> List[Dict[str, str]]:
    """
    Public API: Get verified news articles for a company.
    
    This is the main entry point for external callers (e.g., master_controller.py).
    It encapsulates the working news logic and provides type safety.
    
    Args:
        query_name: Company name to search for (e.g., "Palo Alto Networks")
    
    Returns:
        List[Dict[str, str]]: List of article dictionaries with keys:
            - 'title': Article headline
            - 'url': Article URL
            - 'published_at': Publication date (YYYY-MM-DD format)
    
    Note:
        This function wraps get_company_intelligence() and does not modify
        any internal logic or filtering rules. All search, filtering, and
        relevance logic remains unchanged.
    """
    if not isinstance(query_name, str):
        raise TypeError(f"query_name must be a string, got {type(query_name).__name__}")
    
    if not query_name or not query_name.strip():
        return []
    
    # Call the internal function (all logic remains unchanged)
    return get_company_intelligence(query_name.strip())


if __name__ == "__main__":
    """
    Terminal interface for testing the news service.
    """
    print("=" * 80)
    print("News Service - Intelligence News Agent")
    print("=" * 80)
    print("\nCommands:")
    print("  - Type a company name to fetch intelligence")
    print("  - Type 'quit' or 'exit' to exit")
    print("=" * 80)
    
    while True:
        try:
            user_input = input("\nEnter company name: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            # Get company intelligence
            results = get_company_intelligence(user_input)
            
            # Print results
            print_intelligence_results(results)
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()





