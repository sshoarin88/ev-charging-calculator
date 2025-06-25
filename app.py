import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, time

st.set_page_config(page_title="The Royal EV Charging Calculator")
st.title("The Royal EV Charging Calculator")

st.write(
    """
    Upload your CSV charging history, select a date range, and view costs per QR Code Name.
    """
)

def calculate_billable_idle_hours(session_start, charge_time_s, idle_time_s):
    charge_end = session_start + timedelta(seconds=charge_time_s)
    idle_start = charge_end
    idle_end = idle_start + timedelta(seconds=idle_time_s)

    # 7 AM reference point
    seven_am = idle_start.replace(hour=7, minute=0, second=0, microsecond=0)
    # If idle_start is before 7 AM, but idle_end passes 7 AM (even if on next day)
    if idle_start.time() < time(7, 0):
        seven_am = (idle_start + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)

    billable_start = max(idle_start, seven_am)
    if idle_end <= billable_start:
        return 0

    billable_seconds = (idle_end - billable_start).total_seconds()
    billable_hours = int(billable_seconds // 3600)
    return billable_hours

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()  # Remove any leading/trailing spaces

    # Parse start time
    df['Session Start'] = pd.to_datetime(df['Date (console local time)'])

    # Date picker for session start
    min_date = df['Session Start'].dt.date.min()
    max_date = df['Session Start'].dt.date.max()
    start_date, end_date = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Filter by selected date range (inclusive)
    mask = (df['Session Start'].dt.date >= start_date) & (df['Session Start'].dt.date <= end_date)
    df = df[mask]

    results = []
    for name, group in df.groupby('QR Code Name'):
        total_power = group['Power Usage (kWh)'].sum()
        power_cost = total_power * 0.22

        total_idle_cost = 0
        total_idle_hours = 0
        for idx, row in group.iterrows():
            session_start = row['Session Start']
            charge_time_s = row['Charge Time (s)']
            idle_time_s = row['Idle Time (s)']
            if idle_time_s == 0:
                continue
            billable_hours = calculate_billable_idle_hours(session_start, charge_time_s, idle_time_s)
            total_idle_hours += billable_hours
            total_idle_cost += billable_hours * 5.0

        total_amount = power_cost + total_idle_cost
        results.append({
            "QR Code Name": name,
            "Total Power Usage (kWh)": round(total_power, 2),
            "Total Power Cost": f"${power_cost:.2f}",
            "Total Idle Time Cost": f"${total_idle_cost:.2f}",
            "Total Amount": f"${total_amount:.2f}"
        })

    results_df = pd.DataFrame(results)
    st.dataframe(results_df)

    st.download_button(
        label="Download Results as CSV",
        data=results_df.to_csv(index=False),
        file_name="Royal_EV_Cost_Report.csv",
        mime="text/csv"
    )
else:
    st.info("Please upload a CSV to get started.")
