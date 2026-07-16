# Dataset Metadata

## Primary dataset (loaded by default)

- Dataset: Wikiliq — Alcohol dataset (May 2022), beer subset
- Source URL: https://www.kaggle.com/datasets/limtis/wikiliq-dataset
- License: CC0 1.0 (Public Domain)
- Snapshot date in this repository: 2026-07-16
- Data file: beer_data.csv
- Notes: The CSV is committed as plain text (not a Git LFS pointer file).
- Loader mapping: `Name→beer_name`, `Brand→brewery`, `Categories→style`,
  `ABV ("8%")→abv`, `IBU→min_ibu/max_ibu`, `Rating→review_overall`,
  `Rate Count→number_of_reviews`. `Description`, `Tasting Notes`,
  `Food Pairing`, and `Country` are folded into the composed `info` text.
  Keg/barrel shop SKUs (e.g. "… 1/6 Barrel") are skipped at load time.
  The numeric taste-profile columns of the legacy dataset remain NULL.

## Legacy dataset (kept for reference)

- Dataset: Beer Profile and Ratings Data Set
- Source URL: https://www.kaggle.com/datasets/ruthgn/beer-profile-and-ratings-data-set
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Snapshot date in this repository: 2026-07-06
- Data file: beer_profile_and_ratings.csv
- Notes: No longer loaded by default; the loader now targets beer_data.csv.
- Header detail: The first column contains a UTF-8 BOM marker (`\ufeffName`) in this snapshot; loader code should normalize header names before strict validation.
