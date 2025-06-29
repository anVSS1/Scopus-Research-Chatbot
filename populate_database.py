import pandas as pd
import sqlite3
import json

DATABASE_NAME = 'scopus_database.db'
RAW_DATA_FILENAME = "scopus_raw_data.json"

# Optional: Add progress tracking for large datasets
def populate_database(db_name=DATABASE_NAME, raw_data_filename=RAW_DATA_FILENAME):
    """
    Cleans the extracted data from JSON and inserts it into the SQLite database.
    """
    # Load the raw data extracted from Scopus
    try:
        print(f"Loading data from {raw_data_filename}...")
        with open(raw_data_filename, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        print(f"✅ Loaded {len(raw_data)} articles from JSON file")
    except FileNotFoundError:
        print(f"❌ Error: '{raw_data_filename}' not found. Please ensure it's in the same directory and run your data extraction script first.")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from '{raw_data_filename}'. Check file content for valid JSON.")
        return

    if not raw_data:
        print("❌ No data found in the JSON file to populate the database. Exiting.")
        return

    print(f"📊 Processing {len(raw_data)} articles...")
    df = pd.DataFrame(raw_data)

    # --- Data Cleaning with Pandas ---
    print("\n--- Starting Data Cleaning and Structuring for DB Insertion ---")

    # Handle Duplicates based on scopus_id (assuming scopus_id is truly unique)
    initial_rows = len(df)
    df.drop_duplicates(subset=['scopus_id'], inplace=True)
    print(f"Removed {initial_rows - len(df)} duplicate articles. Remaining: {len(df)}")

    # Fill Missing Values with empty strings to avoid SQLite `None` issues with TEXT columns
    df = df.fillna({
        'abstract': '',
        'doi': '',
        'keywords': '',
        'subject_area': '',
        'publication_name': '',
        'cover_date': ''
    })

    # --- Normalize Authors and Affiliations for Relational Tables ---
    # These dictionaries store unique authors/affiliations with a temporary internal ID
    all_unique_authors = {}
    all_unique_affiliations = {}

    # These lists store the relationships (will use temporary IDs first, then map to real DB IDs)
    article_authors_relations_temp = []
    author_affiliations_relations_temp = []

    current_db_author_temp_id = 1
    current_db_affiliation_temp_id = 1

    print("Processing authors and affiliations for database normalization...")

    for _, row in df.iterrows():
        article_scopus_id = row['scopus_id']

        # Process Authors for the 'authors' table and 'article_authors' relation
        for author_entry in row['authors']:
            scopus_author_id = author_entry.get("author_id") # @auid
            full_name = author_entry.get("preferred_name")    # preferred-name
            # Fallback for full name if preferred_name is missing (combining initials and surname)
            if not full_name:
                 full_name = f"{author_entry.get('initials', '')} {author_entry.get('surname', '')}".strip()
            orcid = author_entry.get("orcid")                 # ORCID

            # Create a unique key for lookup, prioritizing Scopus ID. This is used internally for mapping.
            # Handles cases where Scopus ID might be missing for an author.
            author_unique_key = scopus_author_id if scopus_author_id else f"{full_name}_{orcid or 'no_orcid'}"

            if author_unique_key not in all_unique_authors:
                all_unique_authors[author_unique_key] = {
                    'db_author_id_temp': current_db_author_temp_id, # Temporary internal ID for relations
                    'scopus_author_id': scopus_author_id,
                    'full_name': full_name,
                    'orcid': orcid
                }
                current_db_author_temp_id += 1
            
            # Store article-author relation using temporary author ID
            article_authors_relations_temp.append({
                'article_scopus_id': article_scopus_id,
                'db_author_id_temp': all_unique_authors[author_unique_key]['db_author_id_temp']
            })

            # Process Author's Affiliations (using affiliation_ids from author_entry)
            author_affiliation_ids_scopus = author_entry.get("affiliation_ids", []) # List of Scopus Affiliation IDs from author object
            if not isinstance(author_affiliation_ids_scopus, list): # Ensure it's a list for iteration
                author_affiliation_ids_scopus = [author_affiliation_ids_scopus] if author_affiliation_ids_scopus else []

            for afid_scopus in author_affiliation_ids_scopus:
                if afid_scopus: # Only process if affiliation ID exists
                    # Find the detailed affiliation object from the article's 'affiliations' list
                    matched_affil_detail = next((a for a in row['affiliations'] if a.get('affiliation_id') == afid_scopus), None)
                    
                    if matched_affil_detail:
                        institution_name = matched_affil_detail.get('institution_name') # Nom de l'institution
                        country = matched_affil_detail.get('country')                   # Pays

                        affil_unique_key = afid_scopus if afid_scopus else f"{institution_name}_{country}"
                        
                        if affil_unique_key not in all_unique_affiliations:
                            all_unique_affiliations[affil_unique_key] = {
                                'db_affiliation_id_temp': current_db_affiliation_temp_id, # Temporary internal ID
                                'scopus_affiliation_id': afid_scopus,                   # Identifiant Affiliation Scopus
                                'institution_name': institution_name,
                                'country': country
                            }
                            current_db_affiliation_temp_id += 1
                        
                        # Store author-affiliation relation using temporary IDs
                        author_affiliations_relations_temp.append({
                            'db_author_id_temp': all_unique_authors[author_unique_key]['db_author_id_temp'],
                            'db_affiliation_id_temp': all_unique_affiliations[affil_unique_key]['db_affiliation_id_temp']
                        })

    # Convert unique authors and affiliations to DataFrames for batch insertion
    # We drop the temporary internal IDs as they are not part of the final DB schema
    print(f"📊 Found {len(all_unique_authors)} unique authors and {len(all_unique_affiliations)} unique affiliations")
    
    if all_unique_authors:
        authors_to_insert_df = pd.DataFrame(list(all_unique_authors.values())).drop(columns=['db_author_id_temp'])
    else:
        authors_to_insert_df = pd.DataFrame(columns=['scopus_author_id', 'full_name', 'orcid'])
    
    if all_unique_affiliations:
        affiliations_to_insert_df = pd.DataFrame(list(all_unique_affiliations.values())).drop(columns=['db_affiliation_id_temp'])
    else:
        affiliations_to_insert_df = pd.DataFrame(columns=['scopus_affiliation_id', 'institution_name', 'country'])

    # --- Insert into SQLite ---
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        print(f"Connected to database: {db_name} for data population.")

        # Ensure foreign keys are enabled (important for integrity)
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Helper function for batch insertion to avoid SQLite variable limits
        def insert_in_batches(df, table_name, batch_size=1000):
            total_rows = len(df)
            for i in range(0, total_rows, batch_size):
                batch = df.iloc[i:i+batch_size]
                batch.to_sql(table_name, conn, if_exists='append', index=False, method='multi')
                print(f"  Inserted batch {i//batch_size + 1}: {len(batch)} rows (Progress: {min(i+batch_size, total_rows)}/{total_rows})")

        # Insert main article data in batches
        articles_df_to_insert = df[['scopus_id', 'title', 'abstract', 'cover_date', 'publication_name', 'doi', 'keywords', 'subject_area']].copy()
        print(f"Inserting {len(articles_df_to_insert)} articles into 'articles' table...")
        insert_in_batches(articles_df_to_insert, 'articles')
        print(f"✅ Completed: Inserted {len(articles_df_to_insert)} articles into 'articles' table.")

        # Insert unique authors in batches
        print(f"Inserting {len(authors_to_insert_df)} unique authors into 'authors' table...")
        insert_in_batches(authors_to_insert_df, 'authors')
        print(f"✅ Completed: Inserted {len(authors_to_insert_df)} unique authors into 'authors' table.")

        # Insert unique affiliations in batches
        print(f"Inserting {len(affiliations_to_insert_df)} unique affiliations into 'affiliations' table...")
        insert_in_batches(affiliations_to_insert_df, 'affiliations')
        print(f"✅ Completed: Inserted {len(affiliations_to_insert_df)} unique affiliations into 'affiliations' table.")

        # --- Populate Relationship Tables ---
        print("Populating relationship tables (article_authors, author_affiliations)...")

        # Create lookup maps from our temporary unique keys to actual SQLite AUTOINCREMENT IDs
        # This is needed because SQLite assigns IDs automatically upon insertion.
        actual_author_id_map = {}
        cursor.execute("SELECT author_id, scopus_author_id, full_name, orcid FROM authors")
        for row_id, scopus_id, full_name, orcid in cursor.fetchall():
            if scopus_id: # Prioritize Scopus ID if available for lookup
                actual_author_id_map[scopus_id] = row_id
            else: # Fallback key if Scopus ID is null (matches how `author_unique_key` was created)
                actual_author_id_map[f"{full_name}_{orcid or 'no_orcid'}"] = row_id

        actual_affiliation_id_map = {}
        cursor.execute("SELECT affiliation_id, scopus_affiliation_id, institution_name, country FROM affiliations")
        for row_id, scopus_id, inst_name, country in cursor.fetchall():
            if scopus_id: # Prioritize Scopus ID if available for lookup
                actual_affiliation_id_map[scopus_id] = row_id
            else: # Fallback key if Scopus ID is null
                actual_affiliation_id_map[f"{inst_name}_{country}"] = row_id

        # Prepare and insert article_authors relations in batches
        final_article_authors_relations = []
        for rel in article_authors_relations_temp:
            # Find the original unique key (Scopus ID or generated composite key) for this temporary author ID
            original_author_key = next((k for k, v in all_unique_authors.items() if v['db_author_id_temp'] == rel['db_author_id_temp']), None)
            if original_author_key and original_author_key in actual_author_id_map:
                actual_author_id = actual_author_id_map[original_author_key]
                final_article_authors_relations.append({
                    'article_scopus_id': rel['article_scopus_id'],
                    'author_id': actual_author_id
                })
        
        if final_article_authors_relations:
            article_authors_df = pd.DataFrame(final_article_authors_relations).drop_duplicates()
            print(f"Inserting {len(article_authors_df)} article-author relations...")
            insert_in_batches(article_authors_df, 'article_authors')
            print(f"✅ Completed: Inserted {len(article_authors_df)} article-author relations.")

        # Prepare and insert author_affiliations relations in batches
        final_author_affiliations_relations = []
        for rel in author_affiliations_relations_temp:
            original_author_key = next((k for k, v in all_unique_authors.items() if v['db_author_id_temp'] == rel['db_author_id_temp']), None)
            original_affil_key = next((k for k, v in all_unique_affiliations.items() if v['db_affiliation_id_temp'] == rel['db_affiliation_id_temp']), None)

            if original_author_key and original_affil_key and \
               original_author_key in actual_author_id_map and \
               original_affil_key in actual_affiliation_id_map:
                
                actual_author_id = actual_author_id_map[original_author_key]
                actual_affiliation_id = actual_affiliation_id_map[original_affil_key]
                final_author_affiliations_relations.append({
                    'author_id': actual_author_id,
                    'affiliation_id': actual_affiliation_id
                })
        
        if final_author_affiliations_relations:
            author_affiliations_df = pd.DataFrame(final_author_affiliations_relations).drop_duplicates()
            print(f"Inserting {len(author_affiliations_df)} author-affiliation relations...")
            insert_in_batches(author_affiliations_df, 'author_affiliations')
            print(f"✅ Completed: Inserted {len(author_affiliations_df)} author-affiliation relations.")

        conn.commit()
        print("\n🎉 === DATABASE POPULATION COMPLETE ===")
        print(f"📊 Successfully populated database with:")
        print(f"   • {len(articles_df_to_insert):,} articles")
        print(f"   • {len(authors_to_insert_df):,} unique authors") 
        print(f"   • {len(affiliations_to_insert_df):,} unique affiliations")
        print(f"   • {len(final_article_authors_relations) if 'final_article_authors_relations' in locals() else 0:,} article-author relations")
        print(f"   • {len(final_author_affiliations_relations) if 'final_author_affiliations_relations' in locals() else 0:,} author-affiliation relations")
        print("🚀 Database is ready for semantic indexing and chatbot deployment!")
        print("-" * 60)

    except sqlite3.Error as e:
        print(f"SQLite error during population: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during population: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    populate_database()