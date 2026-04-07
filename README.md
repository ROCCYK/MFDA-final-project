# Waffle Industries FX Hedge Analyzer

This project is a Streamlit app for the MFDA 5300 Winter 2026 group project. It compares four foreign-exchange risk management strategies for Waffle Industries:

- Unhedged
- Forward hedge
- Futures hedge
- Options hedge

## PowerShell setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

## What the app includes

- Embedded assignment data from the project PDF
- Three forecast methods for May 20 and July 20 spot rates
- Low, base, and high scenario comparisons
- Strategy-level USD cash flow tables and charts
- A recommendation based on projected total USD proceeds
