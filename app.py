import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, time
import pytz

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

    # Parse start time and calculate end time
    df['Session Start'] = pd.to_datetime(df['Date (console local time)'])
    df['Session End'] = df['Session Start'] + pd.to_timedelta(df['Total Time (s)'], unit='s')

    # Set up date picker using start dates
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

    # Processing per QR Code Name
    results = []
    for name, group in df.groupby('QR Code Name'):
        total_power = group['Power Usage'].sum()
        power_cost = total_power * 0.22

        total_idle_cost = 0
        total_idle_hours = 0
        for idx, row in group.iterrows():
            # Calculate idle hours (round down)
            idle_seconds = row['Idle Time']
            idle_hours = int(idle_seconds // 3600)

            if idle_hours == 0:
                continue

            session_end = row['Session End']
            idle_start = session_end
            idle_end = idle_start + timedelta(seconds=idle_seconds)

            paid_idle_hours = 0
            current = idle_start
            for h in range(idle_hours):
                hour_start = current + timedelta(hours=h)
                # Only charge if NOT between 12am and 7am (Calgary time)
                if not (time(0, 0) <= hour_start.time() < time(7, 0)):
                    paid_idle_hours += 1

            total_idle_hours += paid_idle_hours
            total_idle_cost += paid_idle_hours * 5.0

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
