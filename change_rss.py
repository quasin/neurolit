# At 00:00 save daily feeds *.csv to global feeds

import csv
import os
from datetime import datetime

def save_daily_feeds_to_global():
    daily_feeds_dir = 'data/feeds'
    global_feeds_dir = 'data/global_feeds'

    if not os.path.exists(global_feeds_dir):
        os.makedirs(global_feeds_dir)

    date_str = datetime.now().strftime("%Y-%m-%d")
    for filename in os.listdir(daily_feeds_dir):
        if filename.endswith('.csv'):
            daily_path = os.path.join(daily_feeds_dir, filename)
            with open(daily_path, 'r') as daily_file:
                reader = csv.reader(daily_file)
                # Skip the first row (URL)
                try:
                    next(reader)
                except StopIteration:
                    pass # Empty file or only one row
                
                base_name = os.path.splitext(filename)[0]
                output_filename = f"{base_name}_{date_str}.csv"
                output_path = os.path.join(global_feeds_dir, output_filename)
                
                existing_rows = set()
                if os.path.exists(output_path):
                    with open(output_path, 'r', newline='') as global_file:
                        existing_reader = csv.reader(global_file)
                        for row in existing_reader:
                            existing_rows.add(tuple(row))

                with open(output_path, 'a', newline='') as global_file:
                    writer = csv.writer(global_file)
                    for row in reader:
                        if tuple(row) not in existing_rows:
                            writer.writerow(row)
                            existing_rows.add(tuple(row))
            
            os.remove(daily_path)

# Call the function to save daily feeds to global feeds
save_daily_feeds_to_global()
