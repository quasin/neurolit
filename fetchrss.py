import csv
import os
import requests
import cloudscraper
import xml.etree.ElementTree as ET
import re
from urllib.parse import urlparse
from datetime import datetime

def get_simplified_name(url):
    parsed = urlparse(url)
    name = parsed.netloc + parsed.path
    name = name.replace('/', '_').replace(':', '_').replace('.', '_')
    if not name:
        name = "feed"
    return name[:50]

def parse_and_save_to_csv(xml_content, base_filename):
    try:
        if isinstance(xml_content, bytes):
            # Try to detect encoding from XML declaration
            match = re.search(b'encoding=["\']([a-zA-Z0-9-]+)["\']', xml_content)
            encoding = match.group(1).decode('utf-8') if match else 'utf-8'
            try:
                xml_content = xml_content.decode(encoding)
            except (LookupError, UnicodeDecodeError, ValueError):
                # Fallback strategies
                try:
                    xml_content = xml_content.decode('cp1251')
                except UnicodeDecodeError:
                    xml_content = xml_content.decode('utf-8', errors='replace')
        
        clean_xml = re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]+', '', xml_content)
        
        clean_xml = re.sub(r'&(?!(?:[a-zA-Z0-9]+|#[0-9]+|#x[0-9a-fA-F]+);)', '&amp;', clean_xml)
        
        root = ET.fromstring(clean_xml)
        new_items = []
        save_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Handle RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "")
            pub_date = item.findtext("pubDate", "")
            
            new_items.append({
                "title": title,
                "link": link,
                "description": description,
                "pub_date": pub_date,
                "save_date": save_date
            })

        # Handle Atom
        if not new_items:
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title", "")
                link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_elem.get("href", "") if link_elem is not None else ""
                description = entry.findtext("{http://www.w3.org/2005/Atom}summary", "")
                pub_date = entry.findtext("{http://www.w3.org/2005/Atom}published", "") or entry.findtext("{http://www.w3.org/2005/Atom}updated", "")
                
                new_items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "pub_date": pub_date,
                    "save_date": save_date
                })

        if not new_items:
            return

        csv_file = base_filename + ".csv"
        existing_links = set()
        fieldnames = ["title", "link", "description", "pub_date", "save_date"]

        # Read existing links if file exists
        if os.path.exists(csv_file):
            with open(csv_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    existing_links.add(row.get('link'))

        # Filter out items that already exist
        items_to_add = [item for item in new_items if item['link'] not in existing_links]

        if items_to_add:
            file_exists = os.path.exists(csv_file)
            with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
                if not file_exists:
                    writer.writeheader()
                for item in items_to_add:
                    writer.writerow(item)
            print(f"Added {len(items_to_add)} new items to: {csv_file}")
        else:
            print(f"No new items for: {csv_file}")

    except Exception as e:
        print(f"Error parsing XML: {e}")

def fetch_feeds():
    csv_path = "data/feeds.csv"
    output_dir = "data/feeds"
    
    try:
        scraper = cloudscraper.create_scraper(
            browser={'custom': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/124.0.0.0 Chrome/124.0.0.0 Safari/537.36'},
            delay=10,
            interpreter='js2py',
            allow_brotli=False
        )
    except Exception as e:
        print(f"Warning: Could not initialize advanced scraper features: {e}")
        print("Falling back to basic scraper...")
        scraper = cloudscraper.create_scraper()

    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return

    os.makedirs(output_dir, exist_ok=True)

    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            url = row.get('url')
            proxy = row.get('proxy')
            
            if not url:
                continue
                
            print(f"Fetching: {url}")
            proxies = {}
            if proxy:
                proxies = {
                    "http": proxy,
                    "https": proxy
                }

            try:
                response = scraper.get(url, proxies=proxies, timeout=60)
                response.raise_for_status()
                
                simplified_name = get_simplified_name(url)
                xml_file_path = os.path.join(output_dir, simplified_name + ".xml")
                
                with open(xml_file_path, 'wb') as out_f:
                    out_f.write(response.content)
                print(f"Saved XML to: {xml_file_path}")
                
                parse_and_save_to_csv(response.content, os.path.join(output_dir, simplified_name))

            except Exception as e:
                print(f"Failed to fetch {url}: {e}")

if __name__ == "__main__":
    fetch_feeds()
