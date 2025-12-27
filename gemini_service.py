"""
Gemini Service - Direct-Feed Chatbot for SEC Filing Analysis

This script provides:
- Reading up to 5 local text files and sending their content to Gemini 2.0 Flash
- Terminal chat loop for interactive querying
- Secure API key management using python-dotenv
"""

import os
import re
import time
from typing import List, Optional
from dotenv import load_dotenv
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY not found in environment variables. "
        "Please create a .env file with GOOGLE_API_KEY=your_key_here"
    )

genai.configure(api_key=GOOGLE_API_KEY)

# Default model - stable models with higher free tier quotas
DEFAULT_MODEL = 'gemini-2.5-flash-lite'  # High TPM limit, optimized for free tier
# Alternative: 'gemini-2.0-flash' (also stable, good for free tier)

# Current model (can be changed via set_model function)
_current_model_name = DEFAULT_MODEL


def set_model(model_name: str) -> None:
    """
    Sets the Gemini model to use for API calls.
    
    Recommended models for free tier:
    - 'gemini-2.5-flash-lite': Highest TPM limit, best for high-volume processing
    - 'gemini-2.0-flash': Stable, good TPM limit
    - 'gemini-2.5-flash': Higher quality but lower TPM limit
    
    Args:
        model_name: Name of the Gemini model (e.g., 'gemini-2.5-flash-lite')
    
    Raises:
        ValueError: If model_name is empty or invalid
    """
    global _current_model_name
    if not model_name or not model_name.strip():
        raise ValueError("Model name cannot be empty")
    _current_model_name = model_name.strip()
    print(f"[SYSTEM] Model set to: {_current_model_name}")


def get_current_model() -> str:
    """
    Returns the currently configured model name.
    
    Returns:
        str: Current model name
    """
    return _current_model_name


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of token count (1 token ≈ 4 characters for English text).
    This is a simple heuristic - actual tokenization may vary.
    
    Args:
        text: The text to estimate tokens for
    
    Returns:
        int: Estimated token count
    """
    return len(text) // 4


def read_files(file_paths: List[str]) -> str:
    """
    Reads multiple text files and combines them into a single context block.
    Line number stamps are added every 10 lines (at lines 1, 11, 21, 31, etc.)
    to enable approximate source citations while keeping the context clean.
    
    Args:
        file_paths: List of file paths to read (up to 5 files)
    
    Returns:
        str: Combined text content from all files with periodic line number stamps
    
    Raises:
        FileNotFoundError: If any file doesn't exist
        ValueError: If more than 5 files are provided
    """
    if len(file_paths) > 5:
        raise ValueError("Maximum of 5 files allowed")
    
    combined_text = []
    
    for file_path in file_paths:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_name = os.path.basename(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Add line number stamps every 10 lines (at lines 1, 11, 21, 31, etc.)
            # This keeps the context clean while still allowing approximate line references
            numbered_lines = []
            for line_num, line in enumerate(lines, start=1):
                # Add stamp at line 1, and then every 10 lines (11, 21, 31, etc.)
                if line_num == 1 or (line_num - 1) % 10 == 0:
                    numbered_lines.append(f"[Line {line_num}] {line.rstrip()}")
                else:
                    numbered_lines.append(line.rstrip())
            
            # Combine with file header
            # Note: Line numbers in stamps refer to the original file line numbers
            file_content = "\n".join(numbered_lines)
            combined_text.append(f"=== File: {file_name} (Total lines: {len(lines)}) ===\n{file_content}\n")
    
    return "\n".join(combined_text)


def parse_response(response_text: str) -> tuple[str, str]:
    """
    Parses Gemini response into answer and references using defensive splitting.
    
    Expected format:
    [CHAT_RESPONSE]
    (answer text)
    ---
    [REFERENCES]
    a. "quoted text" [Line X]
    
    Args:
        response_text: The full response text from Gemini
    
    Returns:
        tuple: (answer_part, reference_part) - If separator is missing, returns (full_response, "")
    """
    if not response_text:
        return "", ""
    
    # Defensive parsing: Look for the --- separator
    if '---' in response_text:
        # Split by '---' separator
        parts = response_text.split('---', 1)
        answer_part = parts[0].strip()
        reference_part = parts[1].strip() if len(parts) > 1 else ""
        
        # Clean tags from answer part
        answer_part = answer_part.replace('[CHAT_RESPONSE]', '').strip()
        
        # Clean tags from reference part
        reference_part = reference_part.replace('[REFERENCES]', '').strip()
        
        return answer_part, reference_part
    else:
        # Defensive: If separator is missing, return entire response as answer
        # Clean any tags that might be present
        answer_part = response_text.replace('[CHAT_RESPONSE]', '').replace('[REFERENCES]', '').strip()
        return answer_part, ""


def get_gemini_response(user_query: str, file_paths: List[str], chat_history: Optional[List] = None) -> tuple[str, str, List]:
    """
    Sends user query and file contents to Gemini for analysis.
    Automatically selects optimal model based on token count and implements
    smart retry logic with 10-second pause on 429 errors.
    
    This function:
    1. Reads all files from file_paths
    2. Estimates token count
    3. Auto-switches to flash-lite if > 200k tokens
    4. Constructs a prompt with the context and user query
    5. Sends to Gemini model with exponential backoff retry
    6. Parses response into answer and references
    7. Returns (answer, references, updated_history)
    
    Args:
        user_query: The question or query from the user
        file_paths: List of file paths to include in the context (up to 5)
        chat_history: Optional list of previous chat messages for context
    
    Returns:
        tuple: (answer_part, reference_part, updated_history)
        - answer_part: The chat response/answer text
        - reference_part: The references section with citations
        - updated_history: Updated chat history (empty list if no history)
    
    Raises:
        FileNotFoundError: If any file doesn't exist
        ValueError: If more than 5 files are provided
        Exception: If Gemini API call fails after retries
    """
    # Read and combine files
    context_block = read_files(file_paths)
    
    # Estimate token count
    estimated_tokens = estimate_tokens(context_block)
    
    # Token Budgeting: Auto-switch to flash-lite if document > 200k tokens
    model_to_use = get_current_model()
    if estimated_tokens > 200000:
        if 'lite' not in model_to_use.lower():
            print(f"⚠ Token count ({estimated_tokens:,}) exceeds 200k. Auto-switching to flash-lite for quota preservation...")
            model_to_use = 'gemini-2.5-flash-lite'
        else:
            print(f"ℹ Token count: {estimated_tokens:,} (using flash-lite for high-throughput processing)")
    else:
        print(f"ℹ Token count: {estimated_tokens:,}")
    
    # Count number of files
    num_files = len(file_paths)
    
    # Construct the prompt according to requirements
    prompt = f"""You are a precise auditor. When answering, use the provided document context. If line numbers are available in the context, you MUST cite them.

Format Rule: Your entire response MUST follow this exact structure:

[CHAT_RESPONSE]
(Your concise summary/answer here)

---
[REFERENCES]
a. "Actual quoted text" [Line X]
b. "Actual quoted text" [Line Y]

CRITICAL FORMATTING REQUIREMENTS:
- Start with [CHAT_RESPONSE] followed by your answer on the next line
- After your answer, include exactly three dashes: ---
- Then include [REFERENCES] followed by your citations
- Each reference must be on a new line with format: letter. "quoted text" [Line X]
- Use lowercase letters (a, b, c, etc.) for reference numbering
- The quoted text must be EXACT from the document, not paraphrased
- Line numbers must match the [Line X] stamps in the context

CITATION REQUIREMENTS:
- The line numbers in the stamps (e.g., [Line 1], [Line 11], [Line 21], [Line 1061]) refer to the ORIGINAL FILE line numbers where that content actually appears.
- Line number stamps appear every 10 lines (at lines 1, 11, 21, 31, 41, 51, etc.). 
- CRITICAL: You must cite the EXACT line number where the content appears. If you see "[Line 1061] Net income $112,010", cite Line 1061, NOT a nearby line number.
- PRIORITY RULE: When the same information appears multiple times in the document, ALWAYS cite the instance that has a line number stamp (e.g., [Line 1061]) rather than an instance without a stamp.
- If content appears between stamps, calculate the exact line number by counting from the nearest stamp, or cite the range (e.g., "Lines 15-17").
- NEVER cite a line number that doesn't match the actual content you're referencing.

Context:
{context_block}

User Query: {user_query}

Remember: Your response MUST follow the exact format with [CHAT_RESPONSE], --- separator, and [REFERENCES] sections."""
    
    # Initialize the model with current selection
    model = genai.GenerativeModel(model_to_use)
    
    # Define retry decorator with exponential backoff and 10-second pause on 429
    @retry(
        stop=stop_after_attempt(5),  # Try up to 5 times
        wait=wait_exponential(multiplier=1, min=2, max=60),  # Exponential backoff: 2s, 4s, 8s, 16s, 32s
        retry=retry_if_exception_type((Exception,)),  # Retry on any exception
        reraise=True
    )
    def send_with_retry():
        """Send message with automatic retry on rate limits, with 10-second pause on 429"""
        try:
            if chat_history:
                # Continue existing chat session
                chat = model.start_chat(history=chat_history)
                response = chat.send_message(user_query)
                updated_history = chat.history
            else:
                # First message: include full context
                chat = model.start_chat(history=[])
                response = chat.send_message(prompt)
                updated_history = chat.history
            
            return response.text, updated_history
        except Exception as e:
            error_str = str(e).lower()
            # Smart Backoff: 10-second pause specifically for 429 errors
            if '429' in error_str or 'quota' in error_str or 'rate limit' in error_str:
                print(f"⏳ Rate limit detected (429). Waiting 10 seconds before retry...")
                time.sleep(10)  # 10-second pause for 429 errors
            raise  # Re-raise to trigger retry logic
    
    try:
        # Send with exponential backoff retry and smart 429 handling
        response_text, updated_history = send_with_retry()
        
        # Parse response into answer and references
        answer_part, reference_part = parse_response(response_text)
        
        return answer_part, reference_part, updated_history
    except Exception as e:
        # Check if it's a rate limit error after all retries
        error_str = str(e).lower()
        if '429' in error_str or 'quota' in error_str or 'rate limit' in error_str:
            raise Exception(
                f"Rate limit exceeded after retries. Please wait a few minutes and try again. "
                f"Consider using 'gemini-2.5-flash-lite' for higher TPM limits. "
                f"Original error: {e}"
            )
        raise Exception(f"Error calling Gemini API: {e}")


def generate_file_summary(file_path: str, company_name: Optional[str] = None, doc_type: Optional[str] = None) -> str:
    """
    Generates a concise, citation-free summary (100-150 words) for a single file.
    This is a separate feature from the chat functionality.
    
    Args:
        file_path: Path to the file to summarize
        company_name: Optional company name for context
        doc_type: Optional document type (e.g., '10-K', '10-Q', 'upload')
    
    Returns:
        str: Clean summary text (100-150 words, no citations)
    
    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If Gemini API call fails
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    file_name = os.path.basename(file_path)
    
    # Build context string
    context_info = f"Document: {file_name}"
    if company_name:
        context_info += f"\nCompany: {company_name}"
    if doc_type:
        context_info += f"\nDocument Type: {doc_type}"
    
    # Construct prompt for summary generation
    summary_prompt = f"""You are a financial analyst. Please provide a concise summary of this document.

{context_info}

Requirements:
- Write a summary between 100-150 words
- Focus on key financial highlights, risks, business operations, or notable changes
- Use clear, narrative prose
- DO NOT include any citations, line references, or [L###] markers
- DO NOT include file names or line numbers in the summary
- Write in plain text only

Document Content:
{content[:200000]}  # Limit to first 200k chars to avoid token limits

Please provide only the summary text, nothing else:"""
    
    # Initialize model
    model = genai.GenerativeModel(get_current_model())
    
    # Generate summary with retry
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def send_with_retry():
        """Send message with automatic retry"""
        response = model.generate_content(summary_prompt)
        return response.text
    
    try:
        summary = send_with_retry()
        # Clean up any potential citations that might have been included
        # Remove any [L###] or [File: ...] patterns
        summary = re.sub(r'\[L\d+\]', '', summary)
        summary = re.sub(r'\[Line \d+\]', '', summary)
        summary = re.sub(r'\[File:.*?\]', '', summary)
        summary = summary.strip()
        
        return summary
    except Exception as e:
        raise Exception(f"Error generating file summary: {e}")


if __name__ == "__main__":
    """
    Terminal chat loop for interactive querying.
    """
    print("=" * 60)
    print("Gemini Direct-Feed Chatbot - SEC Filing Analysis")
    print("=" * 60)
    print(f"[SYSTEM] Using Model: {get_current_model()} (Default: {DEFAULT_MODEL})")
    print("=" * 60)
    print("\nInstructions:")
    print("  1. Enter file paths (comma-separated, up to 5 files)")
    print("  2. Ask questions about the filings")
    print("  3. Type 'new' to load different files")
    print("  4. Type 'quit' or 'exit' to exit")
    print("\nModel Management:")
    print("  - Large documents (>200k tokens) auto-switch to flash-lite")
    print("  - Use set_model('gemini-2.5-flash-lite') for higher TPM limits")
    print("=" * 60)
    
    current_files: Optional[List[str]] = None
    
    while True:
        try:
            # Get file paths if not set
            if current_files is None:
                file_input = input("\nEnter file paths (comma-separated): ").strip()
                if not file_input:
                    print("Please provide at least one file path.")
                    continue
                
                # Parse file paths
                current_files = [f.strip() for f in file_input.split(',') if f.strip()]
                
                if not current_files:
                    print("No valid file paths provided.")
                    continue
                
                # Validate files exist
                try:
                    read_files(current_files)  # Test reading files
                    print(f"\n✓ Loaded {len(current_files)} file(s)")
                    for i, file_path in enumerate(current_files, 1):
                        print(f"  {i}. {file_path}")
                except Exception as e:
                    print(f"\n✗ Error loading files: {e}")
                    current_files = None
                    continue
            
            # Get user query
            user_query = input("\nEnter your question (or 'new' to load different files): ").strip()
            
            if not user_query:
                continue
            
            if user_query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if user_query.lower() == 'new':
                current_files = None
                continue
            
            # Get response from Gemini
            print("\n🤔 Thinking...")
            try:
                answer, refs, history = get_gemini_response(user_query, current_files)
                print("\n" + "=" * 60)
                print("Answer:")
                print("=" * 60)
                print(answer)
                if refs:
                    print("\n" + "-" * 60)
                    print("References:")
                    print("-" * 60)
                    print(refs)
                print("=" * 60)
            except Exception as e:
                print(f"\n✗ Error: {e}")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")

