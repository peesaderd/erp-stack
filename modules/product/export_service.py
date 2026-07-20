"""Google Sheets export service for scraped product data.
Push product data from PostgreSQL → Google Sheets via Service Account.

Usage:
  1. Create Google Cloud Service Account + enable Sheets API
  2. Download JSON key → save as sheets_credentials.json
  3. Share target Sheet with service account email
  4. Call API to export
"""
import os, json, logging
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger("sheets_export")

# ─── Config ──────────────────────────────────────────────────────────────

CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "sheets_credentials.json",
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ═══════════════════════════════════════════════════════════════════════════
# Google Sheets Export
# ═══════════════════════════════════════════════════════════════════════════

def is_ready() -> bool:
    """Check if Google Sheets credentials are configured."""
    return os.path.exists(CREDENTIALS_PATH)


async def export_products_to_sheet(
    spreadsheet_id: str,
    products: List[Dict],
    sheet_name: str = "Products",
    append: bool = False,
) -> dict:
    """Push scraped products to a Google Sheet.
    
    Args:
        spreadsheet_id: The ID from the Sheet URL ( .../d/{ID}/edit )
        products: List of product dicts with name, price, images, etc.
        sheet_name: Tab name in the Sheet
        append: If True, append below existing data instead of replace
    
    Returns:
        dict with success/error/updated_range
    """
    if not is_ready():
        return {
            "success": False,
            "error": "Google Sheets credentials not configured. "
                     "Place sheets_credentials.json in the product module directory.",
        }

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        return {
            "success": False,
            "error": "gspread not installed. Run: pip install gspread google-auth",
        }

    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(spreadsheet_id)

        # Ensure sheet_name exists
        try:
            worksheet = sheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

        # Build rows
        headers = [
            "Date", "Source", "Name", "Price", "Currency",
            "Description", "SKU", "Brand", "Image URL", "Source URL",
        ]
        rows = [headers]

        for p in products:
            # Truncate long text for Sheets
            images = p.get("images", [])
            if isinstance(images, list):
                img_url = images[0] if images else ""
            else:
                img_url = str(images)

            rows.append([
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                p.get("source_site", ""),
                p.get("name", "")[:200],
                p.get("price", ""),
                p.get("currency", "THB"),
                p.get("description", "")[:500] if p.get("description") else "",
                p.get("sku", ""),
                p.get("brand", ""),
                img_url,
                p.get("source_url", ""),
            ])

        # Write
        start_cell = "A1"
        if append:
            existing = worksheet.get_all_values()
            start_row = len(existing) + 1 if existing else 1
            start_cell = f"A{start_row}"

        worksheet.update(start_cell, rows, value_input_option="USER_ENTERED")

        row_count = len(rows) - 1  # minus header
        return {
            "success": True,
            "sheet_name": sheet_name,
            "rows_written": row_count,
            "updated_range": f"{start_cell}:J{start_row + row_count}",
        }

    except Exception as e:
        logger.error(f"Sheets export failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def get_setup_instructions() -> dict:
    """Return instructions for setting up Google Sheets integration."""
    return {
        "steps": [
            "1. Go to https://console.cloud.google.com/apis/credentials",
            "2. Create Service Account → Download JSON key",
            "3. Save the JSON as: " + CREDENTIALS_PATH,
            "4. Enable Google Sheets API in your GCP project",
            "5. Create a Google Sheet → Share with the service account email",
            "6. Get the spreadsheet ID from the Sheet URL: "
            "https://docs.google.com/spreadsheets/d/{ID}/edit",
        ],
        "credentials_path": CREDENTIALS_PATH,
        "env_required": [],
        "pip_packages": ["gspread", "google-auth"],
    }
