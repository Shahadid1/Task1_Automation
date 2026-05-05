"""
========================================================
Daily Report Generator (Automation Script)
========================================================

📌 Description:
This script reads transaction data from a Google Sheet,
filters it by a specific date, processes key metrics,
generates charts, and builds a PDF report.

📊 Outputs:
- Volume per asset analysis
- Failed transactions count
- Top wallets by volume
- Daily PDF report


--------------------------------------------------------
⚙️ How to run:

1. Install dependencies:
   pip install -r requirements.txt

2. Set environment variables:
   export GOOGLE_SHEET_ID="1qbk6lH2fjMaiXdRaEQB8U7JiX4Z-TyWeuRxrW0IAGgU"

3. Activate virtual environment:
   source .venv/bin/activate

4. Run the script:
   python report.py --date YYYY-MM-DD

   Example:
   python report.py --date 2026-04-28

"""


import os
import pandas as pd
import requests
import datetime
import matplotlib.pyplot as plt
import argparse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import glob


# Global report date (for idempotency)
REPORT_DATE = None


def read_public_google_sheet():
    try:
        # Get Google Sheet ID from environment variables
        sheet_id = os.getenv("GOOGLE_SHEET_ID")

        # Check if sheet ID exists
        if not sheet_id:
            print("❌ GOOGLE_SHEET_ID environment variable is not set")
            return

        # Build CSV export URL for Google Sheet
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

        # Send request to fetch the sheet data
        response = requests.get(url, timeout=10)

        # Handle authorization errors
        if response.status_code == 401:
            print("🔐 Unauthorized Access: The Google Sheet is RESTRICTED.")
            return

        if response.status_code == 403:
            print("🔒 Forbidden: You don't have permission to access this Google Sheet.")
            return

        # Handle invalid or missing sheet
        if response.status_code == 404:
            print("❌ Not Found: The Google Sheet ID is incorrect or the sheet does not exist.")
            return

        # Handle unexpected HTTP errors
        if response.status_code != 200:
            print(f"❌ Unexpected error while accessing sheet. HTTP Status: {response.status_code}")
            return

        # Read CSV data into a DataFrame
        df = pd.read_csv(url)

        # Check if data is empty
        if df.empty:
            print("⚠️ The Google Sheet is empty.")
            return

        # FILTER DATA BY SELECTED REPORT DATE
        if REPORT_DATE:

            # Ensure the "date" column exists
            if "date" not in df.columns:
                print(f"❌ 'date' column not found. Available columns: {list(df.columns)}")
                return

            # Convert column to datetime format
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

            # Filter only rows matching the selected date
            df = df[df["date"].dt.date == REPORT_DATE]

            # If no data found for that date
            if df.empty:
                print(f"⚠️ No data found for date: {REPORT_DATE}")
                return

        # Improve pandas display settings for full output
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", None)

        # Print success message and full dataset
        print("✅ Data successfully loaded:\n")
        print(df.to_string(index=False))

        # Return final filtered dataframe
        return df

    except Exception as e:
        # Catch any unexpected errors
        print(f"❌ Unexpected error: {e}")
        
        
        
def get_volume_per_asset(df: pd.DataFrame) -> pd.DataFrame:
    # Check if dataframe is empty or None to avoid errors
    if df is None or df.empty:
        raise ValueError("DataFrame is empty")

    # Group data by asset and sum all transaction amounts
    # Then reset index and sort from highest to lowest volume
    return (
        df.groupby("asset")["amount_sar"]
        .sum()
        .reset_index()
        .sort_values(by="amount_sar", ascending=False)
    )


def get_failed_transactions_count(df: pd.DataFrame) -> int:
    # Validate that dataframe is not empty
    if df is None or df.empty:
        raise ValueError("DataFrame is empty")

    # Filter rows where status is 'failed' (case-insensitive)
    # Then count how many failed transactions exist
    return df[df["status"].str.lower() == "failed"].shape[0]


def get_top_wallets_by_volume(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    # Validate input dataframe
    if df is None or df.empty:
        raise ValueError("DataFrame is empty")

    # Group by wallet address and calculate total transaction volume
    # Sort wallets by highest volume and return top N results
    return (
        df.groupby("wallet_address")["amount_sar"]
        .sum()
        .reset_index()
        .sort_values(by="amount_sar", ascending=False)
        .head(top_n)
    )
    
    

def calculate_summary_metrics(df: pd.DataFrame, failed_count: int):
    # Count total number of transactions in the dataframe
    total_transactions = len(df)

    # Calculate total transaction volume in SAR
    total_volume = df["amount_sar"].sum()

    # Calculate failure rate percentage safely (avoid division by zero)
    failure_rate = (failed_count / total_transactions) * 100 if total_transactions > 0 else 0

    # Get report date from global variable or use today's date if not set
    report_date = REPORT_DATE.strftime("%Y-%m-%d") if REPORT_DATE else datetime.date.today().strftime("%Y-%m-%d")

    # Return all calculated metrics in a dictionary
    return {
        "total_transactions": total_transactions,
        "total_volume": total_volume,
        "failure_rate": failure_rate,
        "report_date": report_date
    }


def create_volume_chart(volume_per_asset: pd.DataFrame, output_dir=".", base_name="volume_per_asset_chart"):
    try:
        # Check if dataframe is valid and not empty
        if volume_per_asset is None or volume_per_asset.empty:
            print("⚠️ No data available to generate chart.")
            return None

        # Generate date string for file naming (use report date if available)
        today = REPORT_DATE.strftime("%Y-%m-%d") if REPORT_DATE else datetime.date.today().strftime("%Y-%m-%d")

        # Create full output file path with date-based filename
        output_file = os.path.join(output_dir, f"{base_name}_{today}.png")

        # Remove ALL previous charts (regardless of date)
        for file in glob.glob(f"{base_name}_*.png"):
            os.remove(file)

        # Create bar chart for volume per asset
        plt.figure(figsize=(8, 5))
        plt.bar(volume_per_asset["asset"], volume_per_asset["amount_sar"])

        # Add chart title and format labels
        plt.title(f"Volume per Asset - {today}")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        # Save chart to file
        plt.savefig(output_file)
        plt.close()

        print(f"✅ Chart created successfully: {output_file}")

        # Return file path of generated chart
        return output_file

    except Exception as e:
        # Handle any unexpected errors during chart generation
        print(f"❌ Unexpected error while creating chart: {e}")
        return None
    

def build_pdf_report(summary: dict, chart_file: str, top_wallets, filename="daily_report"):
    try:
        # Check if summary data exists
        if not summary:
            print("❌ Summary data is missing.")
            return None

        # Check if chart file exists and is valid
        if not chart_file or not os.path.exists(chart_file):
            print("❌ Chart file not found.")
            return None

        # Convert values safely to float to avoid type errors
        def safe_float(value):
            try:
                return float(value)
            except:
                return 0.0

        # Extract numeric values from summary
        total_volume = safe_float(summary.get('total_volume'))
        failure_rate = safe_float(summary.get('failure_rate'))

        # Generate report date for file naming
        today = REPORT_DATE.strftime("%Y-%m-%d") if REPORT_DATE else datetime.date.today().strftime("%Y-%m-%d")

        # Create final PDF filename with date
        final_filename = f"{filename}_{today}.pdf"
        

        # Remove ALL previous reports (regardless of date)
        for file in glob.glob(f"{filename}_*.pdf"):
            os.remove(file)

        # Initialize PDF document
        doc = SimpleDocTemplate(final_filename)
        styles = getSampleStyleSheet()
        elements = []
        # Create title section with report date
        title = Paragraph(
            f"<b>Daily Report</b><br/>{summary.get('report_date', '')}",
            styles["Title"]
        )

        # Add styled title box
        title_table = Table([[title]], colWidths=[500])
        title_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 2, colors.black),
            ("BACKGROUND", (0, 0), (-1, -1), colors.lightgrey),
            ("PADDING", (0, 0), (-1, -1), 12),
        ]))

        elements.append(title_table)
        elements.append(Spacer(1, 25))

        # Create summary text section
        summary_text = f"""
        <b>Total Transactions:</b> {summary.get('total_transactions', 0)}<br/><br/>
        <b>Total Volume (SAR):</b> {total_volume:,.2f}<br/><br/>
        <b>Failure Rate:</b> {failure_rate:.2f}%<br/>
        """

        elements.append(Paragraph(summary_text, styles["Normal"]))
        elements.append(Spacer(1, 25))

        # Add volume chart image to PDF
        elements.append(Image(chart_file, width=450, height=220))
        elements.append(Spacer(1, 25))

        # Create top wallets table if data exists
        if top_wallets is not None and not top_wallets.empty:
            table_data = [["Wallet Address", "Total Volume"]] + top_wallets.values.tolist()

            table = Table(table_data, colWidths=[300, 200])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ]))

            elements.append(table)

        # Build final PDF file
        doc.build(elements)

        print(f"✅ PDF generated successfully: {final_filename}")
        return final_filename

    except Exception as e:
        # Handle any unexpected errors during PDF generation
        print(f"❌ Error generating PDF: {e}")
        return None


def generate_report(df, volume_per_asset, failed_count, top_wallets):
    try:
        # Generate summary metrics from processed data
        summary = calculate_summary_metrics(df, failed_count)

        # Create chart for volume per asset
        chart_file = create_volume_chart(volume_per_asset)

        # Stop pipeline if chart generation failed
        if not chart_file:
            print("❌ Chart generation failed. PDF will not be created.")
            return

        # Build final PDF report
        pdf_file = build_pdf_report(summary, chart_file, top_wallets)

        # Confirm successful pipeline execution
        if pdf_file:
            print("\n🎉 Report pipeline completed successfully!")

    except Exception as e:
        # Handle any unexpected errors in the full pipeline
        print(f"❌ Error in report pipeline: {e}")
        
    
        
def main():
    # Allow global variable to store selected report date
    global REPORT_DATE

    # Create CLI argument parser
    parser = argparse.ArgumentParser()

    # Define required --date argument from user input
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD")

    # Parse arguments from command line
    args = parser.parse_args()

    # Convert input string into Python date object
    try:
        REPORT_DATE = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD")
        return

    # Load data from Google Sheet
    df = read_public_google_sheet()

    # Stop pipeline if no data is returned
    if df is None:
        print("❌ Pipeline stopped: No data loaded")
        return

    try:
        # Calculate total volume per asset
        volume_per_asset = get_volume_per_asset(df)

        # Count failed transactions
        failed_count = get_failed_transactions_count(df)

        # Get top wallets by transaction volume
        top_wallets = get_top_wallets_by_volume(df)

        # Print volume per asset results
        print("\n==============================")
        print("📊 TOTAL VOLUME PER ASSET")
        print("==============================")
        print(volume_per_asset.to_string(index=False))

        # Print failed transactions count
        print("\n==============================")
        print("❌ FAILED TRANSACTIONS COUNT")
        print("==============================")
        print(failed_count)

        # Print top wallets
        print("\n==============================")
        print("🏆 TOP 5 WALLETS BY VOLUME")
        print("==============================")
        print(top_wallets.to_string(index=False))

        # Generate full report (chart + PDF)
        generate_report(
            df=df,
            volume_per_asset=volume_per_asset,
            failed_count=failed_count,
            top_wallets=top_wallets
        )

        # Success message
        print("\n✅ Pipeline completed successfully")

    except Exception as e:
        # Catch any unexpected runtime errors
        print(f"❌ Unexpected error in pipeline: {e}")

if __name__ == "__main__":
    main()
