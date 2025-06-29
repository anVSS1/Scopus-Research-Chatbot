import sqlite3
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
import os

DATABASE_NAME = 'scopus_database.db'

# Multiple FAISS indexes for different search types
INDEXES = {
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

def get_article_data_with_affiliations():
    """Get articles with their affiliation information."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Extended query to include affiliations and countries
    cursor.execute('''
        SELECT 
            A.scopus_id, 
            A.title, 
            A.abstract, 
            A.cover_date, 
            A.keywords,
            GROUP_CONCAT(Auth.full_name, '; ') AS authors_list,
            GROUP_CONCAT(Aff.institution_name, '; ') AS affiliations_list,
            GROUP_CONCAT(Aff.country, '; ') AS countries_list
        FROM articles AS A
        LEFT JOIN article_authors AS AA ON A.scopus_id = AA.article_scopus_id
        LEFT JOIN authors AS Auth ON AA.author_id = Auth.author_id
        LEFT JOIN author_affiliations AS AuthAff ON Auth.author_id = AuthAff.author_id
        LEFT JOIN affiliations AS Aff ON AuthAff.affiliation_id = Aff.affiliation_id
        WHERE A.abstract IS NOT NULL AND A.abstract != '' 
        GROUP BY A.scopus_id, A.title, A.abstract, A.cover_date, A.keywords
        ORDER BY A.scopus_id
    ''')
    
    articles_data = cursor.fetchall()
    conn.close()
    return articles_data

def create_embeddings_for_index_type(articles_data, index_type):
    """Create embeddings based on index type."""
    texts_to_embed = []
    article_ids = []
    
    for row in articles_data:
        scopus_id, title, abstract, cover_date, keywords, authors_list, affiliations_list, countries_list = row
        
        # Build text based on index type
        if index_type == 'content':
            # Primary content search (title + abstract only)
            text = ""
            if title:
                text += f"{title}. "
            if abstract:
                text += f"{abstract}"
                
        elif index_type == 'metadata':
            # Content + metadata
            text = ""
            if title:
                text += f"{title}. "
            if abstract:
                text += f"{abstract}. "
            if keywords:
                text += f"Keywords: {keywords}. "
            if authors_list and authors_list != 'None':
                text += f"Authors: {authors_list}. "
                
        elif index_type == 'institution':
            # Institution and country focused
            text = ""
            if affiliations_list and affiliations_list != 'None':
                text += f"Institutions: {affiliations_list}. "
            if countries_list and countries_list != 'None':
                text += f"Countries: {countries_list}. "
            # Add title for context
            if title:
                text += f"Title: {title}"
                
        elif index_type == 'full':
            # Everything combined
            text = ""
            if title:
                text += f"{title}. "
            if abstract:
                text += f"{abstract}. "
            if keywords:
                text += f"Keywords: {keywords}. "
            if authors_list and authors_list != 'None':
                text += f"Authors: {authors_list}. "
            if affiliations_list and affiliations_list != 'None':
                text += f"Institutions: {affiliations_list}. "
            if countries_list and countries_list != 'None':
                text += f"Countries: {countries_list}. "
        
        text = text.strip()
        if text:  # Only add if we have text
            texts_to_embed.append(text)
            article_ids.append(scopus_id)
    
    return texts_to_embed, article_ids

def build_faiss_index(texts, model):
    """Build and return a FAISS index."""
    print(f"Generating embeddings for {len(texts)} texts...")
    embeddings = model.encode(texts, 
                             batch_size=8,
                             show_progress_bar=True,
                             convert_to_numpy=True)
    embeddings = embeddings.astype('float32')
    
    # Build FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner Product for cosine similarity
    faiss.normalize_L2(embeddings)  # Normalize for cosine similarity
    index.add(embeddings)
    
    return index, embeddings

def perform_enhanced_semantic_indexing():
    """Create multiple FAISS indexes for different search strategies."""
    
    print("🚀 Starting Enhanced Semantic Indexing...")
    print("📊 Fetching articles with affiliation data...")
    
    articles_data = get_article_data_with_affiliations()
    if not articles_data:
        print("❌ No articles found!")
        return
    
    print(f"✅ Found {len(articles_data)} articles to index")
    
    # Load SPECTER model
    print("🧬 Loading SPECTER model...")
    try:
        model = SentenceTransformer('allenai/specter')
        print("✅ SPECTER loaded successfully!")
    except Exception as e:
        print(f"⚠️ SPECTER loading failed: {e}")
        try:
            model = SentenceTransformer('allenai/scibert_scivocab_uncased')
            print("✅ Using SciBERT as fallback")
        except:
            model = SentenceTransformer('all-MiniLM-L6-v2')
            print("✅ Using MiniLM as last resort")
    
    # Create each index type
    for index_type, config in INDEXES.items():
        print(f"\n🔍 Creating {index_type} index: {config['description']}")
        
        # Prepare texts for this index type
        texts, article_ids = create_embeddings_for_index_type(articles_data, index_type)
        
        if not texts:
            print(f"⚠️ No texts found for {index_type} index")
            continue
            
        print(f"📄 Processing {len(texts)} texts for {index_type} index")
        
        # Build FAISS index
        index, embeddings = build_faiss_index(texts, model)
        
        # Save FAISS index
        faiss.write_index(index, config['faiss_file'])
        print(f"💾 Saved FAISS index: {config['faiss_file']}")
        
        # Save article IDs mapping
        with open(config['ids_file'], 'w') as f:
            json.dump(article_ids, f)
        print(f"💾 Saved article IDs: {config['ids_file']}")
        
        print(f"✅ {index_type} index complete: {len(article_ids)} articles, {embeddings.shape[1]} dimensions")
    
    print("\n🎉 Enhanced semantic indexing complete!")
    print("\nCreated indexes:")
    for index_type, config in INDEXES.items():
        if os.path.exists(config['faiss_file']):
            print(f"  ✅ {index_type}: {config['description']}")
        else:
            print(f"  ❌ {index_type}: Failed to create")

if __name__ == "__main__":
    perform_enhanced_semantic_indexing()
