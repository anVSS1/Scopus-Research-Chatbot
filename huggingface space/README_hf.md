---
title: Scopus Scientific Literature Chatbot
emoji: 🔬
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

# Scopus Scientific Literature Chatbot 🔬

An intelligent chatbot for querying scientific literature from Scopus database using advanced semantic search and natural language processing.

## Features

- **🤖 Intelligent Query Parsing**: Automatically detects authors, years, countries, institutions from natural language
- **🔍 Advanced Semantic Search**: Uses SPECTER model optimized for scientific papers
- **⚡ Multiple Search Strategies**: Content, metadata, institution, and full-text search indexes
- **🌍 Geographic & Institutional Filtering**: Smart detection of countries and universities
- **📊 Fast Performance**: FAISS indexing for sub-100ms response times
- **🎯 High Relevance**: Specialized embeddings for scientific literature

## How to Use

Simply type your question in natural language! The system intelligently parses your query and searches accordingly.

### Query Examples

#### **Year-based Searches**

- "machine learning papers from 2023"
- "COVID-19 research published in 2022"
- "recent studies on climate change from 2024"

#### **Author-based Searches**

- "research by Smith on artificial intelligence"
- "papers authored by Johnson et al"
- "publications from Zhang"

#### **Geographic Searches**

- "articles from China about renewable energy"
- "research from USA on quantum computing"
- "European studies on healthcare"

#### **Institution-based Searches**

- "Harvard research on machine learning"
- "papers from Stanford University"
- "MIT publications on robotics"

#### **Topic-based Searches**

- "deep learning applications in healthcare"
- "sustainability research"
- "artificial intelligence ethics"

## Technology Stack

- **🧠 NLP Model**: SPECTER (Scientific Paper Embeddings using Citation-informed TransformERs)
- **🔍 Search Engine**: FAISS (Facebook AI Similarity Search)
- **💾 Database**: SQLite with scientific paper metadata
- **🖥️ Frontend**: Gradio
- **📊 Data Source**: Scopus API
- **🎯 Specialization**: Multiple specialized indexes for different search types

## Dataset

- **Size**: 4,000+ scientific articles
- **Time Range**: 2018-2025
- **Sources**: Scopus database via official API
- **Fields**: Title, Abstract, Authors, Affiliations, Keywords, DOI, Publication details

## Performance

- **Search Speed**: ~100ms average response time
- **Accuracy**: Optimized for scientific literature with SPECTER embeddings
- **Coverage**: Multiple specialized indexes for comprehensive search
- **Relevance**: Intelligent scoring combining semantic similarity and metadata matching

## Architecture

### Intelligent Query Processing

1. **Pattern Detection**: Identifies years, authors, institutions, countries
2. **Entity Extraction**: Matches against actual database entities
3. **Search Strategy Selection**: Chooses optimal index based on query type
4. **Result Ranking**: Combines semantic similarity with metadata relevance

### Specialized FAISS Indexes

- **Content Index**: Title + Abstract (pure semantic search)
- **Metadata Index**: Includes authors, keywords, affiliations
- **Institution Index**: Optimized for geographic and institutional queries
- **Full Index**: All available text fields combined

### Smart Fallbacks

- SPECTER model with MiniLM fallback
- Specialized indexes with main index fallback
- Semantic search with SQL text search fallback

## Use Cases

- **📚 Literature Review**: Find relevant papers for research topics
- **🔎 Author Discovery**: Explore works by specific researchers
- **🌍 Geographic Analysis**: Compare research output by country/institution
- **📈 Trend Analysis**: Track research developments over time
- **🎯 Targeted Search**: Find papers matching specific criteria

## Example Interactions

**User**: _"Show me machine learning papers from Harvard in 2023"_  
**System**: _Detects: Topic=machine learning, Institution=Harvard, Year=2023_  
**Result**: _Ranked papers matching all criteria with relevance scores_

**User**: _"What research has been done on climate change by Chinese universities?"_  
**System**: _Detects: Topic=climate change, Country=China, Type=institutional_  
**Result**: _Papers from Chinese institutions about climate change_

---

Built with ❤️ for the scientific research community. Helping researchers discover relevant literature faster and more efficiently.
