# ABNB M3 - ADSP Transactional Activity UAT

Web-based variance analysis tool for comparing FastDB and Iron Mountain M3 Subledger datasets.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open browser to `http://localhost:5000`

## Usage

1. Upload FastDB dataset (Excel or CSV)
2. Upload Iron Mountain M3 Subledger dataset (Excel or CSV)
3. Click "Generate Variance Analysis"
4. Download the generated Excel workbook with:
   - Summary Analysis
   - Variance tabs (for categories with variance > |100|)
   - Transformed source data

## Features

- Automated categorization of 7 activity types
- Helper column generation (OFA Billing Type, campaign_ID Transformed)
- Variance calculation and analysis
- Multi-sheet Excel output
- Web-based interface for easy file upload
