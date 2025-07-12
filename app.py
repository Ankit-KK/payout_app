import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pytz
import pandas as pd
from io import StringIO

# ===== Supabase Config from Streamlit Secrets =====
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# List of donation tables (add all relevant ones here)
donation_tables = [
    "chiaa_gaming_donations"  # Replace with your actual table names
    # "another_donations_table"
]

# ===== Get IST Friday–Friday Range =====
def get_ist_week_range():
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    days_since_friday = (now_ist.weekday() - 4) % 7 + 7
    last_friday = now_ist - timedelta(days=days_since_friday)
    last_friday = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)
    this_friday = last_friday + timedelta(days=7)
    return last_friday, this_friday

# ===== Fetch & Calculate Payouts =====
def fetch_payout_data():
    ist = pytz.timezone("Asia/Kolkata")
    last_friday, this_friday = get_ist_week_range()
    summary_rows = []

    for table in donation_tables:
        response = supabase.table(table).select("*").execute()

        try:
            data = response.data
        except Exception as e:
            st.error(f"Failed to load table {table}: {e}")
            continue

        valid_donations = []
        for row in data:
            try:
                created_at_utc = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                created_at_ist = created_at_utc.astimezone(ist)

                if (
                    row.get("payment_status") == "success"
                    and row.get("review_status") == "approved"
                    and last_friday <= created_at_ist < this_friday
                ):
                    valid_donations.append(row)
            except:
                continue

        amounts = [row["amount"] for row in valid_donations if isinstance(row.get("amount"), (int, float))]
        table_total = sum(amounts)
        platform_fee = table_total * 0.05
        net_payout = table_total - platform_fee

        summary_rows.append({
            "table": table,
            "from": last_friday.strftime("%Y-%m-%d"),
            "to": this_friday.strftime("%Y-%m-%d"),
            "total_donations": round(table_total, 2),
            "platform_fee": round(platform_fee, 2),
            "net_payout": round(net_payout, 2)
        })

    return summary_rows, last_friday, this_friday

# ===== Streamlit App UI =====
st.set_page_config(page_title="HyperChat Weekly Payout", layout="wide")
st.title("💸 HyperChat Weekly Payout Report")

data, last_friday, this_friday = fetch_payout_data()

if not data:
    st.warning("No valid donations found for this week.")
else:
    df = pd.DataFrame(data)
    st.subheader(f"Payout Summary (IST): {last_friday.strftime('%d %b %Y')} – {this_friday.strftime('%d %b %Y')}")
    st.dataframe(df, use_container_width=True)

    # Totals
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("🎯 Total Donations", f"₹{df['total_donations'].sum():,.2f}")
    col2.metric("💼 Platform Fee (5%)", f"₹{df['platform_fee'].sum():,.2f}")
    col3.metric("💰 Net Payout", f"₹{df['net_payout'].sum():,.2f}")
    st.markdown("---")

    # CSV Download
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")
    filename = f"hyperchat_payout_{last_friday.strftime('%Y%m%d')}_to_{this_friday.strftime('%Y%m%d')}.csv"

    st.download_button(
        label="📥 Download CSV Report",
        data=csv_bytes,
        file_name=filename,
        mime="text/csv"
    )
