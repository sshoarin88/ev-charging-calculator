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

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()  # Remove any leading/trailing spaces

    # Parse start time and calculate charge end and session end
    df['Session Start'] = pd.to_datetime(df['Date (console local time)'])
    df['Charge End'] = df['Session Start'] + pd.to_timedelta(df['Charge Time (s)'], unit='s')
    df['Idle Time (s)'] = df['Idle Time (s)'].fillna(0)
    df['Idle End'] = df['Charge End'] + pd.to_timedelta(df['Idle Time (s)'], unit='s')

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
            charge_end = row['Charge End']
            idle_seconds = row['Idle Time (s)']
            if idle_seconds == 0:
                continue

            # Only charge idle if charge ended before midnight (same calendar day as session started)
            if charge_end.date() != row['Session Start'].date():
                continue  # Charge ended after midnight, no idle charge

            # Billable idle time only after 7 AM
            idle_start = charge_end
            idle_end = idle_start + timedelta(seconds=idle_seconds)
            billable_start = max(idle_start, idle_start.replace(hour=7, minute=0, second=0, microsecond=0))
            if idle_end <= billable_start:
                continue  # All idle before 7 AM

            billable_seconds = (idle_end - billable_start).total_seconds()
            billable_hours = int(billable_seconds // 3600) if billable_seconds >= 3600 else 0

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
