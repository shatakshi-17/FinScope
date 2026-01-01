# FinScope - AI-Powered Financial Intelligence

**Unified Investor Intelligence Platform**

*Transform financial documents into actionable insights with AI-powered analysis*

[![React](https://img.shields.io/badge/React-18.2.0-61DAFB?logo=react)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.6+-47A248?logo=mongodb)](https://www.mongodb.com/)

</div>

---

## Overview

FinScope is a comprehensive financial intelligence platform that leverages Google's Gemini AI and Retrieval-Augmented Generation (RAG) to provide instant, context-aware insights from SEC filings and uploaded financial documents. By combining document analysis with real-time market news and persistent chat history, FinScope empowers investors and analysts to make informed decisions faster.

### How It Works

**Document Processing & Analysis:**
- **SEC Filings**: Automatically retrieves and processes filings from the SEC EDGAR database (10-K, 10-Q, 8-K, etc.)
- **Document Upload**: Supports local PDF and TXT file uploads with intelligent text extraction and processing

**AI-Powered Insights:**
- **Executive Summaries**: Automatically generates 150-word executive summaries of financial documents
- **Interactive Chatbot**: Engage with documents through an intelligent RAG-powered chatbot that answers questions with precise citations

**Market Context:**
- **Real-Time News Integration**: Web-scraped financial news articles from Google News provide broader market context


**Persistent Chat History:**
- **Secure Storage**: All conversations are securely stored in MongoDB for future reference
- **Session Management**: Resume previous analyses or browse through past conversations
- **Multi-Workflow Support**: Separate storage for SEC filing analyses and uploaded document sessions
- **Search & Filter**: Quickly find past analyses by company name, date, or document type

---

## Tech Stack

### Frontend
- **React 18.2** - Modern UI library
- **React Router 6** - Client-side routing
- **Vite 5** - Fast build tool and dev server
- **TailwindCSS 3.3** - Utility-first CSS framework
- **Lucide React** - Beautiful icon library

### Backend
- **FastAPI 0.104+** - Modern, fast Python web framework (REST API)
- **Flask 3.0** - Additional API endpoints (Master Controller)
- **Uvicorn** - ASGI server for production
- **Python 3.x** - Core backend language

### AI & ML
- **Google Gemini API** - Advanced AI model for document analysis and chat
  - `gemini-2.5-flash-lite` - High-throughput model for document processing
  - RAG (Retrieval-Augmented Generation) for accurate, cited responses
- **ChromaDB 0.4** - Vector database for RAG implementation

### Database
- **MongoDB** - Document database for conversations, metadata, and chat history
- **PyMongo 4.6** - MongoDB Python driver

### Data Processing
- **SEC EDGAR Integration** - `edgartools` library for SEC filing retrieval
- **PDF Processing** - `pymupdf4llm` for PDF to Markdown conversion
- **Text Processing** - `rapidfuzz` and `thefuzz` for fuzzy matching
- **News Scraping** - `feedparser` for RSS/Atom feed parsing (Google News)
- **Pandas** - Data manipulation for company lists

### Additional Tools
- **Tenacity** - Retry logic with exponential backoff for API calls
- **python-dotenv** - Environment variable management

---

## Key Features

### 🔍 **SEC Filing Analysis**
- Search and browse SEC EDGAR filings by company name or ticker
- Automatic download and processing of 10-K, 10-Q, 8-K, and other filing types
- Real-time analysis with instant executive summaries

### 📄 **Document Upload & Processing**
- Upload local PDF or TXT documents for analysis
- Intelligent text extraction with table preservation
- Support for custom metadata (company name, document type, year)

### 🤖 **RAG-Powered Chatbot**
- Interactive Q&A with document content
- Accurate citations with line references
- Context-aware responses using Retrieval-Augmented Generation
- Conversation history maintained during active sessions

### 📰 **Market Context Integration**
- Real-time financial news from Google News
- Top 6 relevant headlines per analysis
- Enhanced insights with market sentiment

### 💾 **Persistent Chat History**
- Secure MongoDB storage of all conversations
- Resume previous analyses seamlessly
- Search and filter by company, date, or document type
- Delete or archive old sessions
- Separate workflows for SEC and Upload analyses

### ⚡ **Performance & Reliability**
- Fast document processing with optimized AI models
- Automatic retry logic for API calls
- Session management with TTL (Time-To-Live) for temporary files
- Error handling and graceful degradation

---

## Installation

### Prerequisites
- **Python 3.8+** (recommended: Python 3.10+)
- **Node.js 18+** and npm
- **MongoDB** database (local or cloud instance like MongoDB Atlas)
- **Google Gemini API Key** 

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd FinScope
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   # Google Gemini API Key
   GOOGLE_API_KEY=your_gemini_api_key_here
   
   # MongoDB Connection String
   MONGODB_URI=mongodb://localhost:27017/finscope
   # Or for MongoDB Atlas:
   # MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/finscope
   ```

### Frontend Setup

1. **Navigate to the frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Create production build** (optional, for production)
   ```bash
   npm run build
   ```

### Running the Application

1. **Start the backend server**
   ```bash
   # From the root directory
   python app.py
   ```
   
   The API server will start on `http://localhost:5000`

2. **Start the frontend development server** (in a new terminal)
   ```bash
   # From the frontend directory
   cd frontend
   npm run dev
   ```
   
   The frontend will be available at `http://localhost:5173` (or the port Vite assigns)

3. **Access the application**
   - Open your browser and navigate to `http://localhost:5173`
   - The frontend will automatically connect to the backend API

### Production Deployment

For production deployment:

1. **Build the frontend**
   ```bash
   cd frontend
   npm run build
   ```

2. **Serve the frontend build** (configure your web server to serve `frontend/dist/`)

3. **Run the backend** using a production ASGI server:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 5000
   ```

4. **Configure CORS** in `app.py` to allow your production frontend URL

---

## Usage

### Analyzing SEC Filings

1. Click **"Analyse Companies (SEC)"** on the landing page
2. Search for a company by name or ticker symbol
3. Select a filing from the available list (10-K, 10-Q, etc.)
4. Click **"Start Analysis"** to begin processing
5. Once complete, interact with the document via the chatbot

### Uploading Documents

1. Click **"Analyse Uploads (Local)"** on the landing page
2. Drag and drop or browse for a PDF or TXT file
3. Fill in the metadata (company name, document type, year)
4. Click **"Start Analysis"** to process the document
5. Ask questions about the document using the chatbot

### Viewing Chat History

- Access past conversations from the landing page
- Filter by company name or document type
- Sort by date (newest or oldest)
- Click on any conversation to view full details
- Delete conversations as needed

---

## Project Structure

```
FinScope/
├── app.py                      # FastAPI main application
├── master_controller.py        # Flask API endpoints (orchestration)
├── requirements.txt            # Python dependencies
│
├── Backend Services/
│   ├── db_service.py          # MongoDB operations
│   ├── gemini_service.py      # Google Gemini AI integration
│   ├── sec_service.py         # SEC EDGAR API integration
│   ├── news_service.py        # News scraping & processing
│   ├── company_service.py     # Company data & suggestions
│   ├── upload_service.py      # File upload & processing
│   └── history_manager.py     # Chat history management
│
└── frontend/
    ├── src/
    │   ├── App.jsx            # Main React app
    │   ├── LandingPage.jsx    # Homepage
    │   ├── SECSearchPage.jsx  # SEC filing search
    │   ├── UploadPage.jsx     # Document upload
    │   ├── AnalysisPage.jsx   # Analysis dashboard
    │   ├── ChatDetailPage.jsx # Chat history detail
    │   └── WorkflowContext.jsx # State management
    ├── package.json           # Frontend dependencies
    └── vite.config.js         # Vite configuration

---

<div align="center">
</div>
