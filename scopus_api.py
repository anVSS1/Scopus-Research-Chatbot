import requests
import json
import os
import time

# --- Configuration ---
API_KEY = "YOUR_SCOPUS_API_KEY_HERE"  # Replace with your actual Scopus API Key
INST_TOKEN = "YOUR_SCOPUS_INST_TOKEN_HERE" # Replace with your actual Scopus Instatoken

SEARCH_ENDPOINT = "https://api.elsevier.com/content/search/scopus"
ABSTRACT_ENDPOINT = "https://api.elsevier.com/content/abstract/scopus_id/{scopus_id}"

headers = {
    "X-ELS-APIKey": API_KEY,
    "X-ELS-Insttoken": INST_TOKEN,
    "Accept": "application/json"
}

# --- Search Query Parameters ---
domains = [
    "COMP",  # Computer Science
    "MEDI",  # Medicine
    "ENGI",  # Engineering
    "MATH",  # Mathematics
    "PHYS",  # Physics and Astronomy
    "CHEM",  # Chemistry
    "BIOC",  # Biochemistry, Genetics and Molecular Biology
    "EART",  # Earth and Planetary Sciences
    "ENVI",  # Environmental Science
    "MATE",  # Materials Science
    "ENER",  # Energy
    "AGRI",  # Agricultural and Biological Sciences
    "NEUR",  # Neuroscience
    "PHAR",  # Pharmacology, Toxicology and Pharmaceutics
    "SOCI"   # Social Sciences
]

subj_area_query_part = " OR ".join([f"SUBJAREA({domain})" for domain in domains])

# Target years and articles per year
TARGET_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
ARTICLES_PER_YEAR = 4500 // len(TARGET_YEARS)  # Distribute articles evenly across years
ARTICLES_PER_SEARCH_REQUEST = 25  # Scopus API limit per request

print(f"🎯 Target distribution: {ARTICLES_PER_YEAR} articles per year from {TARGET_YEARS}")
print(f"📊 Total target: {ARTICLES_PER_YEAR * len(TARGET_YEARS)} articles")
print(f"🔍 Subject areas: {len(domains)} domains")  

def extract_data_from_scopus_by_year(api_key, inst_token, search_endpoint, abstract_endpoint,
                                   domains, target_years, articles_per_year, articles_per_request):
    """Extract articles year by year to ensure proper distribution across all target years."""
    all_extracted_data = []
    year_stats = {}
    
    print(f"🚀 Starting year-by-year data extraction")
    print(f"🎯 Target: {articles_per_year} articles per year from {target_years}")
    print(f"📊 Total target: {len(target_years) * articles_per_year} articles")
    print(f"🔍 Subject areas: {len(domains)} domains")
    print("-" * 60)

    for year in target_years:
        print(f"\n📅 === EXTRACTING ARTICLES FROM {year} ===")
        
        # Create year-specific query
        subj_area_query = " OR ".join([f"SUBJAREA({domain})" for domain in domains])
        year_query = f"({subj_area_query}) AND (PUBYEAR = {year})"
        
        print(f"🔍 Query for {year}: PUBYEAR = {year}")
        
        year_articles = extract_articles_for_specific_query(
            api_key, inst_token, search_endpoint, abstract_endpoint,
            year_query, articles_per_request, articles_per_year, year
        )
        
        all_extracted_data.extend(year_articles)
        year_stats[year] = len(year_articles)
        
        print(f"✅ {year}: Collected {len(year_articles)} articles")
        
        # Small delay between years
        if year != target_years[-1]:  # Don't delay after the last year
            print(f"⏱️  Brief pause before next year...")
            time.sleep(2)
    
    # Final statistics
    print(f"\n🎉 === YEAR-BY-YEAR EXTRACTION COMPLETE ===")
    print(f"📊 Total articles collected: {len(all_extracted_data)}")
    print(f"📅 Year distribution:")
    for year in target_years:
        count = year_stats.get(year, 0)
        percentage = (count / len(all_extracted_data)) * 100 if all_extracted_data else 0
        print(f"   {year}: {count:,} articles ({percentage:.1f}%)")
    
    return all_extracted_data

def extract_articles_for_specific_query(api_key, inst_token, search_endpoint, abstract_endpoint,
                                       query, articles_per_request, max_articles, year):
    """Extract articles for a specific query (usually year-specific)."""
    articles_for_query = []
    current_start = 0
    first_request = True
    
    request_headers = {
        "X-ELS-APIKey": api_key,
        "X-ELS-Insttoken": inst_token,
        "Accept": "application/json"
    }

    while len(articles_for_query) < max_articles:
        params = {
            "query": query,
            "count": articles_per_request,
            "view": "COMPLETE",
            "start": current_start
        }

        try:
            progress_pct = (len(articles_for_query) / max_articles) * 100
            print(f"   📥 {year} - Batch from start={current_start} | Progress: {len(articles_for_query)}/{max_articles} ({progress_pct:.1f}%)")
            
            response = requests.get(search_endpoint, headers=request_headers, params=params)
            response.raise_for_status()
            search_results = response.json()

            if first_request:
                total_results_str = search_results.get("search-results", {}).get("opensearch:totalResults", "0")
                total_available = int(total_results_str) if total_results_str.isdigit() else 0
                print(f"   🎉 {year}: {total_available:,} total articles available")
                first_request = False

            entries = search_results.get("search-results", {}).get("entry", [])
            if not entries:
                print(f"   🔚 {year}: No more entries found")
                break

            batch_count = 0
            for entry in entries:
                if len(articles_for_query) >= max_articles:
                    break

                scopus_id = entry.get("eid", "")
                if not scopus_id:
                    continue

                article_data = {
                    "scopus_id": scopus_id,
                    "title": entry.get("dc:title", ""),
                    "abstract": entry.get("dc:description", ""),
                    "cover_date": entry.get("prism:coverDate", ""),
                    "publication_year": str(year),  # Force the correct year
                    "publication_name": entry.get("prism:publicationName", ""),
                    "doi": entry.get("prism:doi", ""),
                    "keywords": entry.get("authkeywords", ""),
                    "subject_area": "",
                    "authors": [],
                    "affiliations": []
                }
                
                # Debug first few articles from each year
                if len(articles_for_query) < 3:
                    print(f"   🔍 {year} Sample {len(articles_for_query)+1}:")
                    print(f"      Title: {entry.get('dc:title', '')[:60]}...")
                    print(f"      Cover Date: {entry.get('prism:coverDate', '')}")
                    print(f"      Forced Year: {year}")
                
                # Get subject areas
                subject_areas_raw = entry.get("subject-areas", {}).get("subject-area", [])
                if subject_areas_raw:
                    if isinstance(subject_areas_raw, list):
                        abbrevs = set()
                        for subj in subject_areas_raw:
                            if isinstance(subj, dict) and subj.get("@abbrev"):
                                abbrevs.add(subj["@abbrev"])
                        article_data["subject_area"] = ", ".join(sorted(list(abbrevs)))
                    elif isinstance(subject_areas_raw, dict) and subject_areas_raw.get("@abbrev"):
                        article_data["subject_area"] = subject_areas_raw["@abbrev"]

                # Get full abstract and author info
                abstract_lookup_scopus_id = scopus_id.replace("2-s2.0-", "")
                abstract_url = abstract_endpoint.format(scopus_id=abstract_lookup_scopus_id)
                abstract_params = {"view": "FULL"}

                try:
                    time.sleep(0.05)
                    abstract_response = requests.get(abstract_url, headers=request_headers, params=abstract_params)
                    abstract_response.raise_for_status()
                    abstract_result = abstract_response.json()

                    # Get better abstract
                    abstract_coredata = abstract_result.get("abstracts-retrieval-response", {}).get("coredata", {})
                    article_data["abstract"] = abstract_coredata.get("dc:description", article_data["abstract"]) or article_data["abstract"]

                    # Get keywords
                    auth_keywords_from_abstract = abstract_coredata.get("authkeywords", {})
                    keywords_list = []
                    if isinstance(auth_keywords_from_abstract, dict) and 'author-keyword' in auth_keywords_from_abstract:
                        if isinstance(auth_keywords_from_abstract['author-keyword'], list):
                            for kw_entry in auth_keywords_from_abstract['author-keyword']:
                                if isinstance(kw_entry, dict) and '$' in kw_entry:
                                    keywords_list.append(kw_entry['$'])
                        elif isinstance(auth_keywords_from_abstract['author-keyword'], dict) and '$' in auth_keywords_from_abstract['author-keyword']:
                            keywords_list.append(auth_keywords_from_abstract['author-keyword']['$'])
                    elif isinstance(auth_keywords_from_abstract, str):
                        keywords_list.append(auth_keywords_from_abstract)

                    article_data["keywords"] = ", ".join(keywords_list) if keywords_list else article_data["keywords"]

                    # Get authors
                    authors_from_abstract = abstract_result.get("abstracts-retrieval-response", {}).get("authors", {}).get("author", [])
                    processed_authors = []
                    
                    if not isinstance(authors_from_abstract, list):
                        authors_from_abstract = [authors_from_abstract] if isinstance(authors_from_abstract, dict) else []

                    for auth in authors_from_abstract:
                        if isinstance(auth, dict):
                            author_affiliation_objects = auth.get('affiliation', [])
                            if not isinstance(author_affiliation_objects, list):
                                author_affiliation_objects = [author_affiliation_objects] if isinstance(author_affiliation_objects, dict) else []

                            author_affiliation_ids = [af_obj.get('@id') for af_obj in author_affiliation_objects if isinstance(af_obj, dict) and af_obj.get('@id')]
                            
                            processed_authors.append({
                                "author_id": auth.get("@auid", ""),
                                "preferred_name": auth.get("ce:indexed-name", ""),
                                "initials": auth.get("ce:initials", ""),
                                "surname": auth.get("ce:surname", ""),
                                "orcid": auth.get("orcid", ""),
                                "affiliation_ids": author_affiliation_ids
                            })
                    article_data["authors"] = processed_authors

                    # Get affiliations
                    affiliations_from_abstract = abstract_result.get("abstracts-retrieval-response", {}).get("affiliation", [])
                    processed_affiliations = []

                    if not isinstance(affiliations_from_abstract, list):
                        affiliations_from_abstract = [affiliations_from_abstract] if isinstance(affiliations_from_abstract, dict) else []

                    for affil in affiliations_from_abstract:
                        if isinstance(affil, dict):
                            country_val = affil.get("affiliation-country", "")
                            
                            processed_affiliations.append({
                                "affiliation_id": affil.get("@id", ""),
                                "institution_name": affil.get("affilname", ""),
                                "country": country_val
                            })
                    article_data["affiliations"] = processed_affiliations

                except requests.HTTPError as e:
                    if e.response.status_code != 404:  # Don't spam 404s
                        print(f"   Abstract HTTP error for {scopus_id}: {e.response.status_code}")
                except json.JSONDecodeError as e:
                    print(f"   Abstract JSON parsing error for {scopus_id}")
                except Exception as e:
                    print(f"   Abstract retrieval error for {scopus_id}: {e}")

                articles_for_query.append(article_data)
                batch_count += 1

            print(f"   ✅ {year}: Processed {batch_count} articles in this batch")
            current_start += articles_per_request

            # Check if we should continue
            if len(articles_for_query) >= max_articles:
                print(f"   🎯 {year}: Reached target ({max_articles} articles)")
                break

            time.sleep(1.5)  # Rate limiting

        except requests.HTTPError as e:
            print(f"   ❌ {year}: HTTP error {e.response.status_code}")
            if e.response.status_code == 429:
                print(f"   ⏱️  {year}: Rate limit hit. Waiting 60 seconds...")
                time.sleep(60)
            else:
                break
        except Exception as e:
            print(f"   ❌ {year}: Unexpected error: {e}")
            break

    return articles_for_query

if __name__ == "__main__":
    extracted_data = extract_data_from_scopus_by_year(
        API_KEY, INST_TOKEN, SEARCH_ENDPOINT, ABSTRACT_ENDPOINT,
        domains, TARGET_YEARS, ARTICLES_PER_YEAR, ARTICLES_PER_SEARCH_REQUEST
    )

    output_filename = "scopus_raw_data.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=2)

    print(f"\n💾 Saved {len(extracted_data)} articles to {output_filename}")
    
    # Final year distribution analysis
    print(f"\n📊 FINAL YEAR DISTRIBUTION ANALYSIS:")
    year_distribution = {}
    for article in extracted_data:
        year = article.get("publication_year", "Unknown")
        year_distribution[year] = year_distribution.get(year, 0) + 1
    
    for year in sorted(year_distribution.keys()):
        count = year_distribution[year]
        percentage = (count / len(extracted_data)) * 100 if extracted_data else 0
        print(f"   {year}: {count:,} articles ({percentage:.1f}%)")
    
    print(f"\n🎉 SUCCESS: Articles properly distributed across {len(TARGET_YEARS)} years!")
    print(f"✅ Ready for database population and semantic indexing!")