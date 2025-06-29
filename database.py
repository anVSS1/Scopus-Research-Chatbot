import sqlite3

def create_database_schema(db_name='scopus_database.db'):
    """
    Creates the SQLite database and defines its tables:
    articles, authors, affiliations, article_authors, and author_affiliations.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        print(f"Connected to database: {db_name}")

        # Enable foreign key constraint enforcement
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Drop tables in reverse order of foreign key dependencies for clean re-runs during development
        # This is useful for resetting the database during development, but be cautious in production.
        cursor.execute("DROP TABLE IF EXISTS article_authors")
        cursor.execute("DROP TABLE IF EXISTS author_affiliations")
        cursor.execute("DROP TABLE IF EXISTS authors")
        cursor.execute("DROP TABLE IF EXISTS affiliations")
        cursor.execute("DROP TABLE IF EXISTS articles")
        print("Dropped existing tables (if any) for a fresh start.")

        # Create Articles Table based on project requirements (title, abstract, year, publication, DOI, Scopus ID, keywords, subject area)
        cursor.execute('''
        CREATE TABLE articles (
            scopus_id TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            cover_date TEXT,
            publication_name TEXT,
            doi TEXT,
            keywords TEXT,
            subject_area TEXT
        )
        ''')
        print("Table 'articles' created.")

        # Create Authors Table based on project requirements (full name, Scopus Author ID, ORCID)
        cursor.execute('''
        CREATE TABLE authors (
            author_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scopus_author_id TEXT UNIQUE, -- @auid (can be NULL if not available from API)
            full_name TEXT,              -- preferred-name
            orcid TEXT                   -- ORCID (si disponible)
        )
        ''')
        print("Table 'authors' created.")

        # Create Affiliations Table based on project requirements (institution name, country, Scopus Affiliation ID)
        cursor.execute('''
        CREATE TABLE affiliations (
            affiliation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scopus_affiliation_id TEXT UNIQUE, -- Identifiant Affiliation Scopus (can be NULL)
            institution_name TEXT,             -- Nom de l'institution
            country TEXT                       -- Pays
        )
        ''')
        print("Table 'affiliations' created.")

        # Create Article-Authors Relationship Table (Many-to-Many relationship)
        # Links articles to their authors
        cursor.execute('''
        CREATE TABLE article_authors (
            article_scopus_id TEXT,
            author_id INTEGER,
            PRIMARY KEY (article_scopus_id, author_id),
            FOREIGN KEY (article_scopus_id) REFERENCES articles(scopus_id) ON DELETE CASCADE,
            FOREIGN KEY (author_id) REFERENCES authors(author_id) ON DELETE CASCADE
        )
        ''')
        print("Table 'article_authors' created.")

        # Create Author-Affiliations Relationship Table (Many-to-Many relationship)
        # Links authors to their affiliations
        cursor.execute('''
        CREATE TABLE author_affiliations (
            author_id INTEGER,
            affiliation_id INTEGER,
            PRIMARY KEY (author_id, affiliation_id),
            FOREIGN KEY (author_id) REFERENCES authors(author_id) ON DELETE CASCADE,
            FOREIGN KEY (affiliation_id) REFERENCES affiliations(affiliation_id) ON DELETE CASCADE
        )
        ''')
        print("Table 'author_affiliations' created.")

        conn.commit()
        print("Database schema created successfully.")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    create_database_schema()