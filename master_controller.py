"""
Master Controller - Central Orchestration for FinScope

This is the central brain of the application.
It orchestrates SEC filing analysis and document upload workflows.
"""

import os
import time
import threading
import tempfile
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

# Import all services
try:
    import company_service
    import sec_service
    import gemini_service
    import news_service
    import upload_service
    import db_service
except ImportError as e:
    print(f"✗ Fatal error: Failed to import required service: {e}")
    print("Please ensure all service files are present in the project directory.")
    exit(1)

# Constants
INACTIVITY_TIMEOUT = 3600  # 1 hour in seconds


def print_step(step_num: int, message: str, status: str = "info"):
    """Print a formatted step message"""
    status_symbols = {
        "info": "→",
        "success": "✓",
        "error": "✗",
        "warning": "⚠"
    }
    symbol = status_symbols.get(status, "→")
    print(f"[{step_num:02d}] {symbol} {message}")


def format_news_for_gemini(news_articles: List[Dict[str, str]]) -> str:
    """
    Formats news articles into a context string for Gemini.
    
    Args:
        news_articles: List of news article dictionaries with keys: 'title', 'url', 'published_at'
    
    Returns:
        str: Formatted news context string
    """
    if not news_articles:
        return "No recent news articles found."
    
    formatted = "Recent News Articles:\n\n"
    for i, article in enumerate(news_articles[:10], 1):
        # news_service.get_company_intelligence() returns: 'title', 'url', 'published_at'
        title = article.get('title', 'No headline')
        date = article.get('published_at', 'N/A')
        link = article.get('url', 'N/A')
        formatted += f"{i}. {title}\n   Date: {date}\n   Link: {link}\n\n"
    
    return formatted


def check_session_lock() -> bool:
    """Check if there's an active session"""
    try:
        return db_service.is_session_active()
    except Exception as e:
        print(f"✗ Error checking session lock: {e}")
        return False


def get_active_session_info() -> Optional[Dict]:
    """Get active session information (chat_id and temp_file_paths)"""
    try:
        db = db_service.get_database()
        collection = db[db_service.ACTIVE_SESSIONS_COLLECTION]
        
        session = collection.find_one({})
        if session:
            return {
                'chat_id': session.get('chat_id'),
                'temp_file_paths': session.get('temp_file_paths', [])
            }
        return None
    except Exception as e:
        print(f"✗ Error getting active session info: {e}")
        return None


def cleanup_session(chat_id: str, temp_file_paths: List[str]) -> None:
    """
    Performs complete cleanup: deletes files, archives conversation, removes session.
    
    Args:
        chat_id: The conversation ID
        temp_file_paths: List of temporary file paths to delete
    """
    print("\n" + "="*80)
    print("CLEANUP: Ending chat session")
    print("="*80)
    
    # Step 1: Delete all temporary files
    deleted_count = 0
    failed_count = 0
    for file_path in temp_file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✓ Deleted file: {file_path}")
                deleted_count += 1
        except Exception as e:
            print(f"✗ Failed to delete {file_path}: {e}")
            failed_count += 1
    
    print(f"✓ Cleanup complete: {deleted_count} deleted, {failed_count} failed")
    
    # Step 2 & 3: End chat session (this handles archiving conversation and removing session)
    try:
        db_service.end_chat_session(chat_id)
    except Exception as e:
        print(f"✗ Failed to end chat session: {e}")
    
    print("✓ Cleanup complete")


def workflow_a_sec():
    """Workflow A: SEC Filing Analysis"""
    print("\n" + "="*80)
    print("WORKFLOW A: SEC FILING ANALYSIS")
    print("="*80)
    
    temp_file_paths = []
    chat_id = None
    inactivity_timer = None
    
    try:
        # Step 1: Pre-load company list (fetch from Wikipedia)
        print_step(1, "Loading company database (S&P 500 & NASDAQ)")
        try:
            if hasattr(company_service, 'fetch_company_lists'):
                company_service.fetch_company_lists()
                print_step(1, "Company database loaded", "success")
        except (AttributeError, Exception) as e:
            # Company service not available, continue without it
            print_step(1, f"Warning: Could not load company database: {e}", "warning")
        
        # Step 2: Get company name/ticker with suggestions
        print_step(2, "Searching for company")
        company_input = input("\nEnter company name or ticker: ").strip()
        
        if not company_input:
            print("✗ No company name provided")
            return
        
        # Get suggestions (if available)
        suggestions = None
        try:
            if hasattr(company_service, 'get_suggestions'):
                suggestions = company_service.get_suggestions(company_input)
        except (AttributeError, Exception) as e:
            # Suggestions service not available, continue without it
            pass
        
        company_name = company_input
        ticker = None
        
        if suggestions:
            print(f"\n  Found {len(suggestions)} suggestion(s):")
            for i, (comp, tick) in enumerate(suggestions, 1):
                print(f"    {i}. {comp} ({tick})")
            print("\n    0. Use original input as-is (no match)")
            print("    Or type a new company name to search again")
            
            while True:
                try:
                    choice = input(f"\n  Select a company (1-{len(suggestions)}, 0, or type new name): ").strip()
                    
                    if not choice:
                        # Empty input, use original
                        print(f"  Using original input: {company_input}")
                        break
                    
                    # Check if it's a number (selection)
                    try:
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(suggestions):
                            company_name, ticker = suggestions[choice_num - 1]
                            print(f"  ✓ Selected: {company_name} ({ticker})")
                            break
                        elif choice_num == 0:
                            print(f"  Using original input: {company_input}")
                            break
                        else:
                            print(f"  ✗ Invalid selection. Please enter 1-{len(suggestions)}, 0, or a new company name.")
                    except ValueError:
                        # Not a number, treat as new company name
                        print(f"  Searching for new company: {choice}")
                        new_suggestions = company_service.get_suggestions(choice)
                        
                        if new_suggestions:
                            print(f"\n  Found {len(new_suggestions)} suggestion(s):")
                            for i, (comp, tick) in enumerate(new_suggestions, 1):
                                print(f"    {i}. {comp} ({tick})")
                            print("\n    0. Use input as-is (no match)")
                            print("    Or type a new company name to search again")
                            
                            # Update suggestions and continue loop
                            suggestions = new_suggestions
                            company_input = choice
                        else:
                            print(f"  No suggestions found. Using '{choice}' as-is.")
                            company_name = choice
                            ticker = None
                            break
                except KeyboardInterrupt:
                    print("\n  Cancelled. Using original input.")
                    company_name = company_input
                    ticker = None
                    break
        
        print_step(2, f"Selected: {company_name}", "success")
        
        # Step 3: Get CIK
        print_step(3, f"Looking up CIK for: {company_name}")
        cik = sec_service.get_company_cik(company_name)
        if not cik:
            print_step(3, "Failed to find CIK", "error")
            return
        print_step(3, f"Found CIK: {cik}", "success")
        
        # Step 4: Get filings list
        print_step(4, "Fetching filings list (last 3 years)")
        filings = sec_service.get_filings_list(cik, years=3)
        if not filings:
            print_step(4, "No filings found", "error")
            return
        print_step(4, f"Found {len(filings)} filing(s)", "success")
        
        # Display filings
        sec_service.print_filings_list(filings)
        
        # Step 5: Select filing to download
        print_step(5, "Select filing to download")
        print("\nEnter the number of the filing to download (e.g., 1)")
        print("Or press Enter to download the first (most recent) filing")
        print("\n⚠ Note: Only 1 file can be processed at a time to avoid API rate limits")
        
        selection_input = input("\nYour selection: ").strip()
        
        selected_indices = []
        if not selection_input:
            selected_indices = [0]
            print(f"  Using default: first filing (most recent)")
        else:
            try:
                selected_num = int(selection_input.strip())
                if 1 <= selected_num <= len(filings):
                    selected_indices = [selected_num - 1]
                    print(f"  Selected filing #{selected_num}")
                else:
                    print(f"  ✗ Invalid selection (must be 1-{len(filings)}), using first filing")
                    selected_indices = [0]
            except ValueError:
                print("  ✗ Invalid input, using first filing")
                selected_indices = [0]
        
        # Step 6: Download selected filing
        print_step(6, f"Downloading {len(selected_indices)} selected filing(s)")
        downloaded_files = []
        for i, idx in enumerate(selected_indices, 1):
            filing = filings[idx]
            accession = filing.get('accession_number')
            form_type = filing.get('form_type', 'UNKNOWN')
            filing_date = filing.get('filing_date', 'UNKNOWN')
            
            print(f"  [{6}.{i}] Downloading {form_type} from {filing_date}...")
            file_path = sec_service.download_filing_as_text(accession, cik=cik)
            if file_path:
                downloaded_files.append(file_path)
                temp_file_paths.append(file_path)
                print(f"  [{6}.{i}] ✓ Downloaded: {os.path.basename(file_path)}")
            else:
                print(f"  [{6}.{i}] ✗ Failed to download {accession}")
        
        if not downloaded_files:
            print_step(6, "No files downloaded", "error")
            return
        print_step(6, f"Downloaded {len(downloaded_files)} file(s)", "success")
        
        # Step 7: Create conversation and active session
        print_step(7, "Creating conversation record")
        selected_filing = filings[selected_indices[0]]
        metadata = {
            'company': company_name,
            'cik': cik,
            'doc_type': selected_filing.get('form_type', 'UNKNOWN'),  # Required: doc_type (not filing_type)
            'filing_date': selected_filing.get('filing_date', 'UNKNOWN')
        }
        # Add ticker if available (optional field)
        if ticker:
            metadata['ticker'] = ticker
        chat_id = db_service.create_conversation('SEC', metadata)
        db_service.create_active_session(chat_id, temp_file_paths)
        print_step(7, f"Created conversation: {chat_id}", "success")
        
        # Step 8: Generate summaries for each file
        print_step(8, f"Generating summaries for {len(downloaded_files)} file(s)")
        for i, file_path in enumerate(downloaded_files, 1):
            file_name = os.path.basename(file_path)
            print(f"  [{8}.{i}] Generating summary for: {file_name}...")
            
            # Find filing metadata
            filing_info = None
            for filing in filings:
                filing_date_short = filing.get('filing_date', '').replace('-', '')
                form_type = filing.get('form_type', '')
                if filing_date_short in file_name and form_type in file_name:
                    filing_info = filing
                    break
            
            doc_type = filing_info.get('form_type', 'UNKNOWN') if filing_info else 'UNKNOWN'
            
            try:
                summary = gemini_service.generate_file_summary(
                    file_path,
                    company_name=company_name,
                    doc_type=doc_type
                )
                # Note: add_summary_to_conversation doesn't exist, so we just display it
                print(f"  [{8}.{i}] ✓ Summary generated ({len(summary.split())} words)")
                
                # Display the summary
                print(f"\n  Summary for {file_name}:")
                print("  " + "-"*76)
                for line in summary.split('\n'):
                    print(f"  {line}")
                print("  " + "-"*76 + "\n")
            except Exception as e:
                print(f"  [{8}.{i}] ✗ Failed to generate summary: {e}")
        
        print_step(8, f"Completed summaries for {len(downloaded_files)} file(s)", "success")
        
        # Step 9: Fetch news articles
        print_step(9, f"Fetching news articles for: {company_name}")
        news_articles = news_service.get_company_intelligence(company_name)
        news_context = format_news_for_gemini(news_articles)
        print_step(9, f"Found {len(news_articles)} news article(s)", "success")
        
        # Display news articles (using correct keys from news_service)
        if news_articles:
            print("\n" + "="*80)
            print("NEWS ARTICLES")
            print("="*80)
            for i, article in enumerate(news_articles, 1):
                # news_service.get_company_intelligence() returns: 'title', 'url', 'published_at'
                headline = article.get('title', 'No headline')
                date = article.get('published_at', 'N/A')
                link = article.get('url', 'N/A')
                # Extract source from URL if available
                source = 'Unknown'
                if link and link != 'N/A':
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(link)
                        domain = parsed.netloc.lower()
                        if domain and '.' in domain:
                            if domain.startswith('www.'):
                                domain = domain[4:]
                            # Get main domain (last two parts, e.g., example.com)
                            parts = domain.split('.')
                            if len(parts) >= 2:
                                source = '.'.join(parts[-2:])
                    except:
                        source = 'Unknown'
                print(f"\n{i}. {headline}")
                print(f"   Source: {source} | Date: {date}")
                print(f"   Link: {link}")
            print("="*80 + "\n")
        
        # Step 10: Start Gemini chat
        print_step(10, "Starting Gemini chat session")
        print("\n" + "="*80)
        print("GEMINI CHAT SESSION")
        print("="*80)
        print("\nFiles loaded:")
        for i, file_path in enumerate(downloaded_files, 1):
            print(f"  {i}. {os.path.basename(file_path)}")
        print(f"\nNews context: {len(news_articles)} articles")
        print("\nType 'quit' or 'exit' to end the session")
        print("="*80 + "\n")
        
        # Initialize chat history
        chat_history = None
        last_activity_time = time.time()
        
        # Chat loop
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nEnding chat session...")
                    break
                
                # Update activity time
                last_activity_time = time.time()
                if inactivity_timer:
                    inactivity_timer.cancel()
                inactivity_timer = threading.Timer(INACTIVITY_TIMEOUT, lambda: cleanup_session(chat_id, temp_file_paths))
                inactivity_timer.start()
                
                # Save user message
                db_service.add_message_to_conversation(chat_id, 'user', user_input)
                
                # Get response
                print("\n🤔 Thinking...")
                answer, references, chat_history = gemini_service.get_gemini_response(
                    user_input,
                    downloaded_files,
                    chat_history=chat_history
                )
                
                # Save assistant message (combine answer and references into content)
                # db_service.add_message_to_conversation only accepts: (chat_id, role, content)
                if references:
                    combined_content = f"{answer}\n\n--- References ---\n{references}"
                else:
                    combined_content = answer
                db_service.add_message_to_conversation(chat_id, 'assistant', combined_content)
                
                print("\n" + "="*80)
                print("ASSISTANT:")
                print("="*80)
                print(answer)
                if references:
                    print("\n--- References (See below for details) ---")
                print("="*80)
                if references:
                    print("\nREFERENCES:")
                    print("-" * 80)
                    print(references)
                    print("="*80)
                print()
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user")
                break
            except Exception as e:
                print(f"\n[99] ✗ Error in workflow: {e}")
                break
        
    except Exception as e:
        print(f"\n[99] ✗ Fatal error in workflow: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if inactivity_timer:
            inactivity_timer.cancel()
        if chat_id:
            cleanup_session(chat_id, temp_file_paths)


def workflow_b_upload():
    """Workflow B: Document Upload Analysis"""
    print("\n" + "="*80)
    print("WORKFLOW B: DOCUMENT UPLOAD ANALYSIS")
    print("="*80)
    
    temp_file_paths = []
    chat_id = None
    inactivity_timer = None
    document_id = None
    
    try:
        # Step 1: Get file path and metadata
        print_step(1, "Uploading document")
        file_path_input = input("\nEnter path to file (.pdf or .txt): ").strip()
        
        # Normalize path (handle quotes and slashes)
        file_path = upload_service.normalize_file_path(file_path_input)
        
        if not file_path or not os.path.exists(file_path):
            print("✗ File not found")
            return
        
        company_name = input("Enter company name: ").strip()
        if not company_name:
            print("✗ Company name is required")
            return
        
        year_input = input("Enter year (optional, press Enter to skip): ").strip()
        if year_input:
            try:
                year = int(year_input)
            except ValueError:
                print("✗ Year must be a number, using current year")
                year = datetime.now().year
        else:
            year = datetime.now().year  # Default to current year
        
        doc_type = input("Enter document type (optional, press Enter to skip): ").strip() or "upload"
        
        # Upload and process (saves to MongoDB)
        print_step(1, "Uploading and processing file...")
        try:
            upload_result = upload_service.upload_file(
                file_path,
                company_name=company_name,
                year=year,
                doc_type=doc_type
            )
        except Exception as e:
            print_step(1, f"Upload failed: {e}", "error")
            return
        
        if not upload_result:
            print_step(1, "Upload failed", "error")
            return
        
        document_id = upload_result['document_id']
        original_filename = os.path.basename(file_path)
        
        print_step(1, "Uploaded and processed successfully", "success")
        print(f"  Document ID: {document_id}")
        print(f"  Saved to MongoDB")
        
        # Retrieve processed content from MongoDB and create temporary file for Gemini
        print_step(1, "Retrieving processed content from MongoDB...")
        try:
            collection = upload_service.get_uploads_collection()
            from bson import ObjectId
            document = collection.find_one({"_id": ObjectId(document_id)})
            
            if not document:
                print_step(1, "Failed to retrieve document from MongoDB", "error")
                return
            
            processed_content = document.get('processed_content', '')
            if not processed_content:
                print_step(1, "No processed content found in document", "error")
                return
            
            # Create temporary file with processed content for Gemini
            file_ext = Path(file_path).suffix.lower()
            if file_ext == '.pdf':
                # PDFs are converted to Markdown, so use .md extension
                temp_suffix = '.md'
            else:
                # TXT files keep their extension
                temp_suffix = file_ext
            
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=temp_suffix, delete=False, encoding='utf-8')
            temp_file.write(processed_content)
            temp_file.close()
            processed_path = temp_file.name
            temp_file_paths.append(processed_path)
            
            print_step(1, f"Created temporary file: {os.path.basename(processed_path)}", "success")
        except Exception as e:
            print_step(1, f"Failed to retrieve processed content: {e}", "error")
            import traceback
            traceback.print_exc()
            return
        
        # Step 2: Create conversation and active session
        print_step(2, "Creating conversation record")
        metadata = {
            'company': company_name,
            'year': year,
            'doc_type': doc_type,
            'original_filename': original_filename,
            'document_id': document_id  # MongoDB document ID
        }
        chat_id = db_service.create_conversation('UPLOAD', metadata)
        db_service.create_active_session(chat_id, temp_file_paths)
        print_step(2, f"Created conversation: {chat_id}", "success")
        
        # Step 3: Generate summary
        print_step(3, "Generating summary for uploaded file")
        print(f"  [3.1] Generating summary for: {os.path.basename(processed_path)}...")
        try:
            summary = gemini_service.generate_file_summary(
                processed_path,
                company_name=company_name,
                doc_type=doc_type
            )
            # Note: add_summary_to_conversation doesn't exist, so we just display it
            print(f"  [3.1] ✓ Summary generated ({len(summary.split())} words)")
            
            # Display the summary
            print(f"\n  Summary for {os.path.basename(processed_path)}:")
            print("  " + "-"*76)
            for line in summary.split('\n'):
                print(f"  {line}")
            print("  " + "-"*76 + "\n")
        except Exception as e:
            print(f"  [3.1] ✗ Failed to generate summary: {e}")
        
        print_step(3, "Summary generation complete", "success")
        
        # Step 4: Fetch news articles
        print_step(4, f"Fetching news articles for: {company_name}")
        news_articles = news_service.get_company_intelligence(company_name)
        news_context = format_news_for_gemini(news_articles)
        print_step(4, f"Found {len(news_articles)} news article(s)", "success")
        
        # Display news articles (using correct keys from news_service)
        if news_articles:
            print("\n" + "="*80)
            print("NEWS ARTICLES")
            print("="*80)
            for i, article in enumerate(news_articles, 1):
                # news_service.get_company_intelligence() returns: 'title', 'url', 'published_at'
                headline = article.get('title', 'No headline')
                date = article.get('published_at', 'N/A')
                link = article.get('url', 'N/A')
                # Extract source from URL if available
                source = 'Unknown'
                if link and link != 'N/A':
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(link)
                        domain = parsed.netloc.lower()
                        if domain and '.' in domain:
                            if domain.startswith('www.'):
                                domain = domain[4:]
                            # Get main domain (last two parts, e.g., example.com)
                            parts = domain.split('.')
                            if len(parts) >= 2:
                                source = '.'.join(parts[-2:])
                    except:
                        source = 'Unknown'
                print(f"\n{i}. {headline}")
                print(f"   Source: {source} | Date: {date}")
                print(f"   Link: {link}")
            print("="*80 + "\n")
        
        # Step 5: Start Gemini chat
        print_step(5, "Starting Gemini chat session")
        print("\n" + "="*80)
        print("GEMINI CHAT SESSION")
        print("="*80)
        print(f"\nFile loaded: {os.path.basename(processed_path)}")
        print(f"News context: {len(news_articles)} articles")
        print("\nType 'quit' or 'exit' to end the session")
        print("="*80 + "\n")
        
        # Initialize chat history
        chat_history = None
        last_activity_time = time.time()
        
        # Chat loop
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nEnding chat session...")
                    break
                
                # Update activity time
                last_activity_time = time.time()
                if inactivity_timer:
                    inactivity_timer.cancel()
                inactivity_timer = threading.Timer(INACTIVITY_TIMEOUT, lambda: cleanup_session(chat_id, temp_file_paths))
                inactivity_timer.start()
                
                # Save user message
                db_service.add_message_to_conversation(chat_id, 'user', user_input)
                
                # Get response
                print("\n🤔 Thinking...")
                answer, references, chat_history = gemini_service.get_gemini_response(
                    user_input,
                    [processed_path],
                    chat_history=chat_history
                )
                
                # Save assistant message (combine answer and references into content)
                # db_service.add_message_to_conversation only accepts: (chat_id, role, content)
                if references:
                    combined_content = f"{answer}\n\n--- References ---\n{references}"
                else:
                    combined_content = answer
                db_service.add_message_to_conversation(chat_id, 'assistant', combined_content)
                
                print("\n" + "="*80)
                print("ASSISTANT:")
                print("="*80)
                print(answer)
                if references:
                    print("\n--- References (See below for details) ---")
                print("="*80)
                if references:
                    print("\nREFERENCES:")
                    print("-" * 80)
                    print(references)
                    print("="*80)
                print()
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user")
                break
            except Exception as e:
                print(f"\n[99] ✗ Error in workflow: {e}")
                break
        
    except Exception as e:
        print(f"\n[99] ✗ Fatal error in workflow: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if inactivity_timer:
            inactivity_timer.cancel()
        if chat_id:
            cleanup_session(chat_id, temp_file_paths)


def main():
    """Main entry point"""
    print("="*80)
    print("FinScope Master Controller")
    print("="*80)
    print("\nThis is the central brain of the application.")
    print("It orchestrates SEC filing analysis and document upload workflows.")
    
    # Check session lock
    if check_session_lock():
        print("\n⚠ Warning: An active session was found.")
        print("\nOptions:")
        print("  y) Continue anyway (multiple sessions allowed)")
        print("  t) Terminate the active session and start fresh")
        print("  n) Exit")
        
        response = input("\nYour choice (y/t/n): ").strip().lower()
        
        if response == 't':
            # Terminate the active session
            session_info = get_active_session_info()
            if session_info:
                chat_id = session_info.get('chat_id')
                temp_file_paths = session_info.get('temp_file_paths', [])
                print("\nTerminating active session...")
                cleanup_session(chat_id, temp_file_paths)
                print("✓ Active session terminated. You can now start a new session.\n")
            else:
                print("⚠ Could not retrieve session information, but proceeding anyway...\n")
        elif response != 'y':
            print("Exiting...")
            return
    
    print("\n\nAvailable Workflows:")
    print("  A) SEC Filing Analysis")
    print("  B) Document Upload Analysis")
    print("  Q) Quit")
    
    while True:
        choice = input("\nSelect workflow (A/B/Q): ").strip().upper()
        
        if choice == 'A':
            workflow_a_sec()
            break
        elif choice == 'B':
            workflow_b_upload()
            break
        elif choice == 'Q':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter A, B, or Q.")


if __name__ == "__main__":
    main()
