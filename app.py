import gradio as gr
import sqlite3
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
import os
import re
import math
from datetime import datetime

# Configuration - Files expected in HF Space
DATABASE_NAME = 'scopus_database.db'
FAISS_INDEX_FILE = "scopus_combined_metadata_index.faiss"
ARTICLE_IDS_MAP_FILE = "scopus_article_ids_for_index.json"

# Enhanced: Multiple specialized indexes
SPECIALIZED_INDEXES = {
    'content': {
        'faiss_file': 'scopus_content_index.faiss',
        'ids_file': 'scopus_content_ids.json',
        'description': 'Title + Abstract (primary semantic search)'
    },
    'metadata': {
        'faiss_file': 'scopus_metadata_index.faiss', 
        'ids_file': 'scopus_metadata_ids.json',
        'description': 'Title + Abstract + Keywords + Authors'
    },
    'institution': {
        'faiss_file': 'scopus_institution_index.faiss',
        'ids_file': 'scopus_institution_ids.json', 
        'description': 'Institution names and countries'
    },
    'full': {
        'faiss_file': 'scopus_full_index.faiss',
        'ids_file': 'scopus_full_ids.json',
        'description': 'All available text fields combined'
    }
}

# Pagination settings
RESULTS_PER_PAGE = 5

# Global variables for caching
model = None
index = None
article_ids = None
specialized_indexes = {}  # Cache for specialized indexes

# Cache for database entities (loaded once)
_db_cache = {
    'countries': None,
    'institutions': None,
    'authors': None,
    'loaded': False
}

def load_database_entities():
    """Load countries, institutions, and authors from the actual database."""
    global _db_cache
    
    if _db_cache['loaded']:
        return _db_cache
    
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Get actual countries from database
        cursor.execute('''
            SELECT DISTINCT LOWER(TRIM(country)) as country 
            FROM affiliations 
            WHERE country IS NOT NULL AND country != '' 
            ORDER BY country
        ''')
        countries = [row[0] for row in cursor.fetchall() if row[0]]
        
        # Get actual institutions from database  
        cursor.execute('''
            SELECT DISTINCT LOWER(TRIM(institution_name)) as institution 
            FROM affiliations 
            WHERE institution_name IS NOT NULL AND institution_name != '' 
            ORDER BY institution
        ''')
        institutions = [row[0] for row in cursor.fetchall() if row[0]]
        
        # Get actual author names from database
        cursor.execute('''
            SELECT DISTINCT TRIM(full_name) as author_name
            FROM authors 
            WHERE full_name IS NOT NULL AND full_name != '' 
            ORDER BY full_name
        ''')
        authors = [row[0] for row in cursor.fetchall() if row[0]]
        
        conn.close()
        
        _db_cache['countries'] = countries
        _db_cache['institutions'] = institutions
        _db_cache['authors'] = authors
        _db_cache['loaded'] = True
        
        print(f"✅ Loaded from database: {len(countries)} countries, {len(institutions)} institutions, {len(authors)} authors")
        
        return _db_cache
        
    except Exception as e:
        print(f"⚠️ Error loading database entities: {e}")
        # Fallback to empty lists
        _db_cache = {
            'countries': [],
            'institutions': [],
            'authors': [],
            'loaded': True
        }
        return _db_cache

def parse_intelligent_query(query_text):
    """
    Intelligently parse queries to detect search intent and extract filters.
    Uses ACTUAL data from the database instead of hardcoded lists.
    """
    import re
    
    search_params = {
        'semantic_query': query_text,  # fallback to full query
        'year_filter': None,
        'author_filter': None,
        'country_filter': None,
        'institution_filter': None,
        'search_type': 'semantic'  # semantic, author, geographic, institutional, temporal
    }
    
    query_lower = query_text.lower().strip()
    
    # Load actual database entities
    db_entities = load_database_entities()
    
    # 1. YEAR/TEMPORAL DETECTION
    year_patterns = [
        r'\b(?:from|in|during|year|published)\s+(\d{4})\b',
        r'\b(\d{4})\s+(?:articles|papers|publications|research|studies)\b',
        r'\b(?:since|after)\s+(\d{4})\b',
        r'\b(\d{4})\s*[-–]\s*(\d{4})\b',  # year range
        r'\b(\d{4})\b(?=\s*(?:$|[^\d]))'  # standalone year
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, query_lower)
        if match:
            search_params['year_filter'] = match.group(1)
            search_params['search_type'] = 'temporal'
            # Remove year from semantic query
            search_params['semantic_query'] = re.sub(pattern, '', query_lower, flags=re.IGNORECASE).strip()
            break
    
    # 2. AUTHOR DETECTION (using actual database authors)
    # First try pattern-based detection
    author_patterns = [
        r'\b(?:by|author|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:et\s+al\.?|and\s+colleagues)\b',
        r'\b(?:authored by|written by|research by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
        r'\b([A-Z][a-z]+)\s+(?:papers|articles|publications|research)\b'
    ]
    
    for pattern in author_patterns:
        match = re.search(pattern, query_text)  # Case sensitive for names
        if match:
            potential_author = match.group(1)
            # Check if this author actually exists in our database
            author_matches = [author for author in db_entities['authors'] 
                            if potential_author.lower() in author.lower()]
            if author_matches:
                search_params['author_filter'] = potential_author
                search_params['search_type'] = 'author'
                # Remove author from semantic query
                search_params['semantic_query'] = re.sub(pattern, '', query_text, flags=re.IGNORECASE).strip()
                break
    
    # 3. GEOGRAPHIC/COUNTRY DETECTION (using actual database countries)
    if db_entities['countries']:
        # Create pattern from actual countries in database
        countries_pattern = '|'.join(re.escape(country) for country in db_entities['countries'])
        country_patterns = [
            r'\b(?:from|in)\s+(' + countries_pattern + r')\b',
            r'\b(' + countries_pattern + r')\s+(?:papers|articles|research|publications|studies)\b',
            r'\b(?:research from|studies from|papers from)\s+(' + countries_pattern + r')\b'
        ]
        
        for pattern in country_patterns:
            match = re.search(pattern, query_lower)
            if match:
                search_params['country_filter'] = match.group(1)
                search_params['search_type'] = 'geographic'
                # Remove country from semantic query
                search_params['semantic_query'] = re.sub(pattern, '', query_lower, flags=re.IGNORECASE).strip()
                break
    
    # 4. INSTITUTION DETECTION (using actual database institutions)
    if db_entities['institutions']:
        # Look for institution names in the query
        query_words = query_lower.split()
        for institution in db_entities['institutions']:
            # Check for partial matches (e.g., "harvard" matches "Harvard University")
            institution_words = institution.split()
            for inst_word in institution_words:
                if len(inst_word) > 3:  # Skip short words like "of", "the"
                    for query_word in query_words:
                        if inst_word in query_word or query_word in inst_word:
                            # Found a potential institution match
                            institution_patterns = [
                                r'\b(?:from|at)\s+.*?' + re.escape(inst_word) + r'.*?\b',
                                r'\b.*?' + re.escape(inst_word) + r'.*?\s+(?:papers|research|publications|studies)\b',
                                r'\b(?:research from|studies from|papers from)\s+.*?' + re.escape(inst_word) + r'.*?\b'
                            ]
                            
                            for pattern in institution_patterns:
                                if re.search(pattern, query_lower):
                                    search_params['institution_filter'] = inst_word
                                    search_params['search_type'] = 'institutional'
                                    # Remove institution reference from semantic query
                                    search_params['semantic_query'] = re.sub(
                                        re.escape(inst_word), '', query_lower, flags=re.IGNORECASE
                                    ).strip()
                                    break
                            
                            if search_params['institution_filter']:
                                break
                    
                    if search_params['institution_filter']:
                        break
                
                if search_params['institution_filter']:
                    break
            
            if search_params['institution_filter']:
                break
    
    # Clean up the semantic query
    search_params['semantic_query'] = re.sub(r'\s+', ' ', search_params['semantic_query']).strip()
    
    # If semantic query is too short, fall back to database search
    if len(search_params['semantic_query'].split()) < 2:
        search_params['search_type'] = search_params['search_type'] if search_params['search_type'] != 'semantic' else 'database'
    
    return search_params

def check_required_files():
    """Check if all required files are present."""
    required_files = [DATABASE_NAME, FAISS_INDEX_FILE, ARTICLE_IDS_MAP_FILE]
    missing_files = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"⚠️ Missing required files: {missing_files}")
        return False
    
    print("✅ All required files found")
    return True

def load_resources():
    """Loads the SPECTER model, FAISS index, and article ID mapping."""
    global model, index, article_ids
    
    if model is not None:  # Already loaded
        return True
    
    # Check required files first
    if not check_required_files():
        return False
    
    try:
        print("🔄 Loading scientific text model...")
        # Try SPECTER first, fallback to MiniLM
        try:
            model = SentenceTransformer('allenai/specter')
            print("✅ Loaded SPECTER model")
        except Exception as e:
            print(f"SPECTER not available: {e}")
            try:
                model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                print("✅ Loaded all-MiniLM-L6-v2 model (fallback)")
            except Exception as e2:
                print(f"❌ Could not load any model: {e2}")
                return False

        # Load main index
        print("🔄 Loading main FAISS index...")
        index = faiss.read_index(FAISS_INDEX_FILE)
        with open(ARTICLE_IDS_MAP_FILE, "r", encoding="utf-8") as f:
            article_ids = json.load(f)
        print(f"✅ Loaded main FAISS index with {index.ntotal:,} vectors and {len(article_ids):,} article IDs")

        # Load specialized indexes (optional)
        print("🔄 Loading specialized FAISS indexes...")
        for key, spec in SPECIALIZED_INDEXES.items():
            try:
                if os.path.exists(spec['faiss_file']) and os.path.exists(spec['ids_file']):
                    # Load the FAISS index
                    faiss_index = faiss.read_index(spec['faiss_file'])
                    
                    # Load the article IDs
                    with open(spec['ids_file'], "r", encoding="utf-8") as f:
                        article_ids_list = json.load(f)
                    
                    # Store in specialized_indexes cache
                    specialized_indexes[key] = {
                        'index': faiss_index,
                        'article_ids': article_ids_list
                    }
                    
                    print(f"✅ Loaded specialized FAISS index '{key}' with {faiss_index.ntotal:,} vectors")
                else:
                    print(f"⚠️ Specialized index '{key}' files not found, will use main index as fallback")
                
            except Exception as e:
                print(f"⚠️ Could not load specialized index '{key}': {e}")
                continue

        return True
        
    except Exception as e:
        print(f"❌ Error loading resources: {e}")
        return False

def semantic_search(query, top_k=50, index_key='content'):
    """Perform semantic search using FAISS."""
    if not load_resources():
        return []
    
    try:
        # Encode the query
        query_embedding = model.encode([query])
        query_embedding = query_embedding.astype('float32')
        
        # Search in FAISS index
        index = specialized_indexes[index_key]['index']
        distances, indices = index.search(query_embedding, top_k)
        
        # Convert results
        results = []
        article_ids = specialized_indexes[index_key]['article_ids']
        for distance, idx in zip(distances[0], indices[0]):
            if idx < len(article_ids):
                results.append({
                    'article_id': article_ids[idx],
                    'similarity_score': float(1 - distance)  # Convert distance to similarity
                })
        
        return results
        
    except Exception as e:
        print(f"❌ Semantic search error: {e}")
        return []

def load_specialized_index(index_type):
    """Load a specialized FAISS index on demand."""
    global specialized_indexes
    
    # Check if already loaded from load_resources()
    if index_type in specialized_indexes:
        return specialized_indexes[index_type]
    
    config = SPECIALIZED_INDEXES.get(index_type)
    if not config:
        print(f"⚠️ Unknown index type: {index_type}")
        return None
    
    try:
        # Check if files exist
        if not os.path.exists(config['faiss_file']) or not os.path.exists(config['ids_file']):
            print(f"⚠️ Specialized index '{index_type}' files not found")
            return None
        
        # Load specialized index
        specialized_index = faiss.read_index(config['faiss_file'])
        with open(config['ids_file'], 'r') as f:
            specialized_ids = json.load(f)
        
        specialized_indexes[index_type] = {
            'index': specialized_index,
            'article_ids': specialized_ids
        }
        
        print(f"✅ Loaded specialized '{index_type}' index: {specialized_index.ntotal:,} vectors")
        return specialized_indexes[index_type]
        
    except Exception as e:
        print(f"❌ Error loading specialized index '{index_type}': {e}")
        return None

def enhanced_semantic_search(query, search_type='semantic', top_k=50):
    """Enhanced semantic search using the most appropriate specialized index."""
    if not load_resources():
        return []
    
    # Determine which index to use based on search type
    index_to_use = None
    ids_to_use = None
    
    # Try to use specialized index first
    if search_type == 'institutional' or search_type == 'geographic':
        specialized = load_specialized_index('institution')
        if specialized:
            index_to_use = specialized['index']
            ids_to_use = specialized['article_ids']
            print(f"🏢 Using institution index for {search_type} search")
    
    elif search_type == 'author' or 'keyword' in query.lower():
        specialized = load_specialized_index('metadata')
        if specialized:
            index_to_use = specialized['index']
            ids_to_use = specialized['article_ids']
            print(f"📊 Using metadata index for {search_type} search")
    
    elif search_type == 'semantic' and len(query.split()) <= 5:  # Simple content queries
        specialized = load_specialized_index('content')
        if specialized:
            index_to_use = specialized['index']
            ids_to_use = specialized['article_ids']
            print(f"📄 Using content index for pure semantic search")
    
    else:  # Complex queries or fallback
        specialized = load_specialized_index('full')
        if specialized:
            index_to_use = specialized['index']
            ids_to_use = specialized['article_ids']
            print(f"🔍 Using full index for complex search")
    
    # Fallback to main index if no specialized index available
    if index_to_use is None:
        index_to_use = index
        ids_to_use = article_ids
        print(f"📋 Using main index as fallback")
    
    try:
        # Encode the query
        query_embedding = model.encode([query])
        query_embedding = query_embedding.astype('float32')
        
        # Normalize for cosine similarity (if using Inner Product index)
        faiss.normalize_L2(query_embedding)
        
        # Search in selected index
        distances, indices = index_to_use.search(query_embedding, top_k)
        
        # Convert results
        results = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx < len(ids_to_use):
                similarity = float(distance)  # Already normalized similarity for IP
                results.append({
                    'article_id': ids_to_use[idx],
                    'similarity_score': similarity
                })
        
        return results
        
    except Exception as e:
        print(f"❌ Enhanced semantic search error: {e}")
        return []

def enhanced_search_articles(query_text, top_k=50):
    """
    Enhanced search that intelligently parses queries and searches accordingly.
    """
    if not load_resources():
        return []
    
    # Parse the query intelligently
    search_params = parse_intelligent_query(query_text)
    
    print(f"🔍 Search Type: {search_params['search_type']}")
    print(f"📝 Semantic Query: '{search_params['semantic_query']}'")
    print(f"🗓️ Year: {search_params['year_filter']}")
    print(f"👤 Author: {search_params['author_filter']}")
    print(f"🌍 Country: {search_params['country_filter']}")
    print(f"🏢 Institution: {search_params['institution_filter']}")
    
    # Connect to database
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return []
    
    # Build SQL query based on search type
    sql_conditions = []
    sql_params = []
    
    # Fixed base query - removed DISTINCT from GROUP_CONCAT functions
    base_query = '''
        SELECT 
            A.scopus_id, A.title, A.abstract, A.cover_date, 
            A.publication_name, A.doi, A.keywords,
            GROUP_CONCAT(Auth.full_name, '; ') AS authors_list,
            GROUP_CONCAT(Aff.country, '; ') AS countries_list,
            GROUP_CONCAT(Aff.institution_name, '; ') AS institutions_list
        FROM articles AS A
        LEFT JOIN article_authors AS AA ON A.scopus_id = AA.article_scopus_id
        LEFT JOIN authors AS Auth ON AA.author_id = Auth.author_id
        LEFT JOIN author_affiliations AS AuthAff ON Auth.author_id = AuthAff.author_id
        LEFT JOIN affiliations AS Aff ON AuthAff.affiliation_id = Aff.affiliation_id
    '''
    
    # Add conditions based on search parameters
    if search_params['year_filter']:
        sql_conditions.append("A.cover_date LIKE ?")
        sql_params.append(f"%{search_params['year_filter']}%")
    
    if search_params['author_filter']:
        sql_conditions.append("Auth.full_name LIKE ?")
        sql_params.append(f"%{search_params['author_filter']}%")
    
    if search_params['country_filter']:
        sql_conditions.append("Aff.country LIKE ?")
        sql_params.append(f"%{search_params['country_filter']}%")
    
    if search_params['institution_filter']:
        sql_conditions.append("Aff.institution_name LIKE ?")
        sql_params.append(f"%{search_params['institution_filter']}%")
    
    # For semantic search, get FAISS results first using enhanced search
    semantic_results = []
    if search_params['semantic_query'] and len(search_params['semantic_query'].split()) >= 2:
        semantic_results = enhanced_semantic_search(
            search_params['semantic_query'], 
            search_params['search_type'], 
            top_k
        )
        
        if semantic_results:
            # Add FAISS results to query
            article_ids_list = [r['article_id'] for r in semantic_results]
            placeholders = ','.join(['?' for _ in article_ids_list])
            sql_conditions.append(f"A.scopus_id IN ({placeholders})")
            sql_params.extend(article_ids_list)
    
    # If no semantic results or non-semantic search, add text search
    if not semantic_results and search_params['semantic_query']:
        text_conditions = []
        query_term = search_params['semantic_query']
        
        # Search in multiple text fields
        text_conditions.append("A.title LIKE ?")
        sql_params.append(f"%{query_term}%")
        
        text_conditions.append("A.abstract LIKE ?")
        sql_params.append(f"%{query_term}%")
        
        text_conditions.append("A.keywords LIKE ?")
        sql_params.append(f"%{query_term}%")
        
        # Combine text conditions with OR
        if text_conditions:
            sql_conditions.append(f"({' OR '.join(text_conditions)})")
    
    # Build final query
    if sql_conditions:
        final_query = base_query + " WHERE " + " AND ".join(sql_conditions)
    else:
        final_query = base_query
    
    final_query += '''
        GROUP BY A.scopus_id, A.title, A.abstract, A.cover_date, A.publication_name, A.doi, A.keywords
        ORDER BY A.cover_date DESC
        LIMIT ?
    '''
    sql_params.append(top_k)
    
    # Execute query
    try:
        cursor.execute(final_query, sql_params)
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"❌ SQL execution error: {e}")
        conn.close()
        return []
    
    # Process results
    results = []
    semantic_scores = {r['article_id']: r['similarity_score'] for r in semantic_results}
    
    for row in rows:
        # Calculate relevance score
        relevance_score = semantic_scores.get(row['scopus_id'], 0.0)
        
        if relevance_score == 0.0:  # Database match, calculate text relevance
            text_relevance = 0.0
            query_lower = query_text.lower()
            
            # Score based on where the match was found
            if query_lower in (row['title'] or '').lower():
                text_relevance += 0.8
            if query_lower in (row['abstract'] or '').lower()[:200]:
                text_relevance += 0.6
            if query_lower in (row['keywords'] or '').lower():
                text_relevance += 0.7
            if query_lower in (row['countries_list'] or '').lower():
                text_relevance += 0.9  # High score for geographic matches
            if query_lower in (row['institutions_list'] or '').lower():
                text_relevance += 0.85  # High score for institution matches
            if query_lower in (row['authors_list'] or '').lower():
                text_relevance += 0.9  # High score for author matches
            
            relevance_score = min(text_relevance, 0.95)  # Cap at 0.95 for database matches
        
        results.append({
            'scopus_id': row['scopus_id'],
            'title': row['title'],
            'abstract': row['abstract'],
            'cover_date': row['cover_date'],
            'publication_name': row['publication_name'],
            'doi': row['doi'],
            'keywords': row['keywords'],
            'authors_list': row['authors_list'] or '',
            'countries_list': row['countries_list'] or '',
            'institutions_list': row['institutions_list'] or '',
            'similarity_score': relevance_score,
            'search_type': search_params['search_type']
        })
    
    # Sort by relevance score
    results.sort(key=lambda x: x['similarity_score'], reverse=True)
    
    return results

def format_search_results(results):
    """Format search results for display in Gradio."""
    if not results:
        return "No articles found matching your query. Try different keywords or broaden your search."
    
    formatted_results = []
    formatted_results.append(f"## 🔍 Found {len(results)} relevant articles\n")
    
    for i, article in enumerate(results, 1):
        title = article.get('title', 'No title available')
        authors = article.get('authors_list', 'Authors not available')
        if authors and authors != 'None':
            authors = authors.replace('; ', ', ')
        else:
            authors = 'Authors not available'
        
        publication = article.get('publication_name', 'Publication not available')
        year = article.get('cover_date', 'Year not available')
        if year and len(year) >= 4:
            year = year[:4]
        
        abstract = article.get('abstract', 'Abstract not available')
        if len(abstract) > 500:
            abstract = abstract[:500] + "..."
        
        doi = article.get('doi', '')
        keywords = article.get('keywords', '')
        similarity = article.get('similarity_score', 0.0)
        
        # Enhanced information from intelligent search
        countries = article.get('countries_list', '')
        institutions = article.get('institutions_list', '')
        search_type = article.get('search_type', 'semantic')
        
        # Format individual result
        result_text = f"""
### {i}. {title}

**Authors:** {authors}  
**Publication:** {publication} ({year})  
**Similarity Score:** {similarity:.3f}

**Abstract:** {abstract}

"""
        
        if keywords:
            result_text += f"**Keywords:** {keywords}\n\n"
        
        if countries and countries.strip():
            result_text += f"**Countries:** {countries}\n\n"
        
        if institutions and institutions.strip():
            result_text += f"**Institutions:** {institutions}\n\n"
        
        if doi:
            result_text += f"**DOI:** {doi}\n\n"
        
        # Add search type indicator
        if search_type != 'semantic':
            result_text += f"**Search Type:** {search_type.title()}\n\n"
        
        result_text += "---\n\n"
        formatted_results.append(result_text)
    
    return "".join(formatted_results)

def chatbot_interface(query, num_results):
    """Main chatbot interface function."""
    if not query.strip():
        return "Please enter a search query to find relevant scientific articles."
    
    # Load resources if not already loaded
    if not load_resources():
        return "❌ Error: Could not load required resources. Please check if all required files are present in the space."
    
    try:
        # Perform enhanced search with intelligent query parsing
        results = enhanced_search_articles(
            query_text=query,
            top_k=int(num_results)
        )
        
        # Format and return results
        return format_search_results(results)
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        return f"❌ An error occurred during search: {str(e)}"

# Sample queries for examples
sample_queries = [
    "machine learning papers from 2023",
    "research by Smith",
    "articles from USA",
    "Harvard researches",
    "COVID-19",
    "papers from Stanford University",
    "research on AI",
    "quantum computing research from India"
]

# Create Gradio interface
def create_interface():
    with gr.Blocks(
        title="Scopus Research Chatbot - Intelligent Search",
        theme=gr.themes.Soft(),
        css="""
        .main-header {
            text-align: center;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        .examples-box {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
        }
        """
    ) as demo:
        
        # Header
        gr.HTML("""
        <div class="main-header">
            <h1>🔬 Scopus Research Chatbot</h1>
            <h2>Intelligent Query-Based Search</h2>
            <p>Ask questions in natural language - no need for manual filters!</p>
        </div>
        """)
        
        # Instructions
        gr.Markdown("""
        ## 🎯 How to Use Intelligent Search

        **Just type your query naturally! The system will automatically detect:**
        - **Year searches**: "papers from 2023", "research in 2024"
        - **Author searches**: "research by Smith", "papers by Zhang"
        - **Country searches**: "articles from China", "research from USA"
        - **Institution searches**: "Harvard research", "papers from MIT"
        - **Topic searches**: "machine learning", "COVID-19 treatment"

        **Examples:**
        - "Show me machine learning papers from 2023"
        - "Find research by Johnson on climate change"
        - "Articles from China about renewable energy"
        - "Stanford University research on quantum computing"
        """)
        
        with gr.Row():
            with gr.Column(scale=3):
                query_input = gr.Textbox(
                    label="🔍 Enter your search query",
                    placeholder="e.g., 'machine learning papers from 2023' or 'research by Smith'",
                    lines=2
                )
                
                with gr.Row():
                    num_results = gr.Slider(
                        minimum=5,
                        maximum=50,
                        value=10,
                        step=5,
                        label="Number of results"
                    )
                    search_btn = gr.Button("🔍 Search", variant="primary")
        
        # Examples section
        gr.HTML('<div class="examples-box">')
        gr.Markdown("### 💡 Try these intelligent queries:")
        example_buttons = []
        with gr.Row():
            for i, query in enumerate(sample_queries[:4]):
                btn = gr.Button(query, size="sm")
                example_buttons.append(btn)
        with gr.Row():
            for i, query in enumerate(sample_queries[4:]):
                btn = gr.Button(query, size="sm")
                example_buttons.append(btn)
        gr.HTML('</div>')
        
        # Results
        results_output = gr.Markdown(
            label="Search Results",
            value="Enter a query above to search through scientific articles..."
        )
        
        # Event handlers
        def search_handler(query, num_results):
            return chatbot_interface(query, num_results)
        
        search_btn.click(
            fn=search_handler,
            inputs=[query_input, num_results],
            outputs=results_output
        )
        
        # Example button handlers
        for btn, query in zip(example_buttons, sample_queries):
            btn.click(
                fn=lambda q=query: q,
                outputs=query_input
            )
        
        # Enter key support
        query_input.submit(
            fn=search_handler,
            inputs=[query_input, num_results],
            outputs=results_output
        )
        
        # Footer
        gr.Markdown("""
        ---
        **Dataset:** Scientific articles from Scopus database  
        **Technology:** FAISS + SPECTER embeddings + Intelligent Query Parsing  
        **Features:** Semantic search, Author detection, Geographic filtering, Institution search, Year filtering
        """)
        
        return demo

if __name__ == "__main__":
    # Check files on startup
    if not check_required_files():
        print("❌ Required files are missing. Please ensure all required files are uploaded to the space.")
    
    demo = create_interface()
    demo.launch()
