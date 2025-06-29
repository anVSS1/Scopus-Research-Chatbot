# 📚 Scopus Research Chatbot

An intelligent AI-powered search engine for scientific literature, built with **SPECTER embeddings** and **multi-index FAISS** for semantic similarity search across 4,000+ research articles from Scopus.

## 🎯 Features

- **🧠 Semantic Search**: Natural language queries like "machine learning in healthcare"
- **👥 Author Search**: Find research by specific authors or research groups
- **🏢 Institution Search**: Discover research from specific universities or countries
- **📊 Multi-Index System**: 5 specialized FAISS indexes for different search strategies
- **🔍 Intelligent Query Processing**: Automatically detects search intent (author, institution, semantic)
- **📱 Modern UI**: Clean Gradio interface with pagination and detailed results

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Scopus API    │───▶│  Data Pipeline   │───▶│   SQLite DB     │
│   (Raw Data)    │    │  (Clean & Store) │    │ (Structured)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Multi-Index    │◀───│ SPECTER Embeddings│◀───│  Text Content   │
│  FAISS Search   │    │ (Semantic Vectors)│    │ (Title+Abstract)│
└─────────────────┘                                     │
         │                                               ▼
         ▼                                    ┌─────────────────┐
┌─────────────────────────────────────────────────────────────────┐
│                    Gradio Chat Interface                        │
│         (Intelligent Query Processing + Results Display)        │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Index FAISS System

The system uses 5 specialized FAISS indexes for different search scenarios:

1. **Content Index**: Title + Abstract semantic search
2. **Metadata Index**: Authors + Keywords + Institutions
3. **Full Index**: Complete article text (title + abstract + metadata)
4. **Institution Index**: Institutional affiliations and locations
5. **Combined Index**: Unified search across all content types

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/anVSS1/Scientific-Article-Recommender.git
cd Scientific-Article-Recommender
pip install -r requirements.txt
```

### 2. Setup Scopus API (Required for data collection)

1. Get your Scopus API key from [Elsevier Developer Portal](https://dev.elsevier.com/)
2. Create a `config.py` file:

```python
# config.py
API_KEY = "your_scopus_api_key_here"
INST_TOKEN = "your_scopus_inst_token_here"
```

3. Update `scopus_api.py` to use the config:

```python
from config import API_KEY, INST_TOKEN
```

### 3. Build the Database (Optional - for new data)

```bash
# Collect data from Scopus API
python scopus_api.py

# Populate the database
python populate_database.py
```

### 4. Create Semantic Indexes

```bash
# Generate FAISS indexes for semantic search
python enhanced_semantic_indexing.py
```

### 5. Run the Application

```bash
# Local development
python app.py

# For Hugging Face Spaces deployment
python huggingface\ space/app_hf.py
```

## 🔧 Configuration

### Required Files for Full Functionality

- `scopus_database.db` - SQLite database with articles (created by data pipeline)
- `scopus_combined_metadata_index.faiss` - Main FAISS index
- `scopus_article_ids_for_index.json` - Article ID mappings

### Optional Enhanced Files

- `scopus_content_index.faiss` - Content-only search
- `scopus_metadata_index.faiss` - Metadata-focused search
- `scopus_institution_index.faiss` - Institution-based search
- `scopus_full_index.faiss` - Comprehensive search

## 📊 Dataset

- **Source**: Scopus API (2018-2025)
- **Articles**: 4,000+ scientific papers
- **Domains**: 15 scientific fields (Computer Science, Medicine, Engineering, etc.)
- **Languages**: English
- **Content**: Title, Abstract, Authors, Keywords, Institutions, Countries

## 🛠️ Technology Stack

- **Backend**: Python, SQLite, FAISS
- **ML/AI**: SPECTER embeddings (scientific papers), sentence-transformers
- **Frontend**: Gradio
- **Deployment**: Hugging Face Spaces ready

## 📁 Project Structure

```
Scientific-Article-Recommender/
├── app.py                           # Main Gradio application
├── scopus_api.py                    # Scopus API data collection
├── database.py                      # Database schema and operations
├── populate_database.py             # Data processing pipeline
├── enhanced_semantic_indexing.py    # FAISS index creation
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
└── kaggle_semantic_indexing.ipynb  # Jupyter notebook for indexing
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Important Notes

- **API Limits**: Scopus API has rate limits and requires institutional access
- **Data Size**: Full database and indexes can be several GB
- **Performance**: Semantic search requires substantial computational resources
- **Privacy**: This project handles academic data responsibly per Scopus terms

## 🆘 Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure your Scopus API credentials are properly configured
2. **Large File Sizes**: Database and FAISS indexes are excluded from Git (see `.gitignore`)
3. **Memory Issues**: Reduce batch sizes in indexing scripts for lower-memory systems
4. **Model Loading**: SPECTER model download requires stable internet connection

### Getting Help

- Check the [Issues](https://github.com/anVSS1/Scientific-Article-Recommender/issues) page
- Review the documentation in `livrables/` folder
- Ensure all dependencies are correctly installed

---

**Note**: This repository contains the code and scripts but excludes large data files (database, indexes) and sensitive API credentials. See setup instructions above for complete deployment.
