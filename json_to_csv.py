import json
import csv

def json_to_csv(json_file, csv_file):
    """
    Converts a JSON file (with a list of dicts) into a CSV file.
    
    :param json_file: Path to the input JSON file
    :param csv_file: Path to the output CSV file
    """
    # Load JSON data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Make sure it's a list of dictionaries
    if not isinstance(data, list):
        raise ValueError("JSON file must contain a list of dictionaries.")

    # Write CSV file
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        if len(data) == 0:
            print("Warning: JSON file is empty, CSV file will also be empty.")
            return

        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    print(f"✅ Successfully converted '{json_file}' to '{csv_file}'.")

# Example usage:
# json_to_csv('input.json', 'output.csv')
json_to_csv('./raw_data/JSON/Amazon_full_data.json', './raw_data/CSV/amzon_data.csv')