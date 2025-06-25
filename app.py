import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(page_title="The Royal EV Charging Calculator")
st.title("The Royal EV Charging Calculator")

st.write(
    """
    Upload your CSV charging history, select a date range, and view costs per QR Code Name.
    Idle time fees are calculated based on specific time windows.
    """
)

def calculate_billable_idle_hours(row):
    """
    Calculates the billable idle hours based on a complex set of rules.

    Args:
        row (pd.Series): A row from the DataFrame containing charging session data.
                         It must include 'Session Start', 'Charge Time (s)', and 'Idle Time (s)'.

    Returns:
        int: The total number of billable idle hours, rounded down.
    """
    # Extract start time and durations from the row
    session_start = row['Session Start']
    charge_time_seconds = row['Charge Time (s)']
    idle_time_seconds = row['Idle Time (s)']
    
    # Calculate the end of charging and the end of the total session (charge + idle)
    charge_end = session_start + timedelta(seconds=charge_time_seconds)
    session_end = charge_end + timedelta(seconds=idle_time_seconds)

    # Define key time points for the calculation logic based on the session start day
    midnight_start_of_day = session_start.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_24_from_start_of_day = midnight_start_of_day + timedelta(hours=24) # Midnight at the end of the start day
    hour_31_from_start_of_day = midnight_start_of_day + timedelta(hours=31) # 7 AM the next day
    
    billable_hours = 0
    
    # --- Scenario 1 & 2: Session ends before the first midnight (24h mark) ---
    # If the entire session (charging + idling) is over before the first midnight,
    # the idle time is simply the total idle duration in hours, rounded down.
    if session_end <= hour_24_from_start_of_day:
        billable_hours = int(idle_time_seconds // 3600)
        return billable_hours

    # --- Scenario 3 & 4: Session crosses the first midnight (24h mark) ---
    # This handles cases where idling occurs both before and potentially after midnight.
    if charge_end < hour_24_from_start_of_day:
        # Calculate idle time that occurs before the first midnight.
        # This is the time from when charging ends to midnight.
        idle_before_midnight_seconds = (hour_24_from_start_of_day - charge_end).total_seconds()
        billable_hours += int(max(0, idle_before_midnight_seconds) // 3600)

    # --- Scenario 5: Session crosses the 31-hour mark ---
    # This handles the rule where there is no charge for idling between 24h and 31h,
    # but charges resume for any idling that occurs after the 31h mark.
    if session_end > hour_31_from_start_of_day:
        # The start of this billable idle period is the later of two times:
        # 1. The 31-hour mark.
        # 2. The actual time the car finished charging.
        # This ensures we don't bill for charging time that happens after the 31h mark.
        idle_after_31h_starts = max(charge_end, hour_31_from_start_of_day)
        
        # Calculate the duration of the billable idle time after the 31h mark.
        idle_after_31h_seconds = (session_end - idle_after_31h_starts).total_seconds()
        billable_hours += int(max(0, idle_after_31h_seconds) // 3600)
        
    return billable_hours

# Allow user to upload a CSV file
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    # Read the uploaded CSV into a pandas DataFrame
    df = pd.read_csv(uploaded_file)
    # Clean up column names by stripping leading/trailing whitespace
    df.columns = df.columns.str.strip()

    # --- Data Processing and Calculation ---

    # Convert date/time columns to datetime objects for calculations
    df['Session Start'] = pd.to_datetime(df['Date (console local time)'], errors='coerce')
    df.dropna(subset=['Session Start'], inplace=True)

    # --- UI for Date Filtering ---
    min_date = df['Session Start'].dt.date.min()
    max_date = df['Session Start'].dt.date.max()

    start_date, end_date = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        help="Select the start and end dates for the report."
    )

    mask = (df['Session Start'].dt.date >= start_date) & (df['Session Start'].dt.date <= end_date)
    filtered_df = df[mask].copy()

    # --- Cost Calculation ---
    results = []
    for name, group in filtered_df.groupby('QR Code Name'):
        total_power = group['Power Usage (kWh)'].sum()
        power_cost = total_power * 0.22  # Power cost at $0.22 per kWh

        total_idle_cost = 0
        total_idle_hours_billed = 0
        
        for idx, row in group.iterrows():
            # Use the new detailed calculation function for each session
            billable_hours = calculate_billable_idle_hours(row)
            
            total_idle_hours_billed += billable_hours
            total_idle_cost += billable_hours * 5.0  # Idle cost at $5.00 per hour

        total_amount = power_cost + total_idle_cost

        results.append({
            "QR Code Name": name,
            "Total Power Usage (kWh)": round(total_power, 2),
            "Total Power Cost": f"${power_cost:.2f}",
            "Billed Idle Hours": total_idle_hours_billed,
            "Total Idle Time Cost": f"${total_idle_cost:.2f}",
            "Total Amount": f"${total_amount:.2f}"
        })

    # --- Display Results ---
    if results:
        results_df = pd.DataFrame(results)
        st.dataframe(results_df)

        csv_data = results_df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="Download Results as CSV",
            data=csv_data,
            file_name="Royal_EV_Cost_Report.csv",
            mime="text/csv"
        )
    else:
        st.warning("No data available for the selected date range.")

else:
    st.info("Please upload a CSV file to begin.")
