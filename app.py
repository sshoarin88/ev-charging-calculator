import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, time

st.set_page_config(page_title="The Royal EV Charging Calculator")
st.title("The Royal EV Charging Calculator")

st.write(
    """
    Upload your CSV charging history, select a date range, and view costs per QR Code Name.
    Idle time fees are only applied if a vehicle remains idle past midnight. The fee is calculated for each full hour of idle time between the end of the charge and midnight.
    """
)

def billable_idle_hours_before_midnight(charge_end, idle_time_s):
    """
    Calculates billable idle hours based on specific rules.

    A session is only billable for idle time if the idle period crosses midnight.
    The billable portion is the duration from the end of the charge until midnight.
    This duration is rounded down to the nearest whole hour.

    Args:
        charge_end (datetime): The timestamp when the vehicle finished charging.
        idle_time_s (int): The total idle time in seconds for the session.

    Returns:
        int: The number of billable, whole hours of idle time.
    """
    # If there's no idle time, there can be no billable hours.
    if idle_time_s <= 0:
        return 0

    idle_start = charge_end
    actual_idle_end = idle_start + timedelta(seconds=idle_time_s)

    # Determine the midnight that immediately follows the charge completion time.
    # This is effectively 00:00:00 of the next calendar day.
    midnight = (idle_start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # The core business rule: idle time is only billable if the vehicle is still
    # idle when midnight strikes. This means the idle period must start before
    # midnight and end after it.
    if idle_start < midnight and actual_idle_end > midnight:
        # If the condition is met, the billable duration is the time from
        # when idling began (charge_end) up until midnight.
        billable_seconds = (midnight - idle_start).total_seconds()
        
        # We only charge for full hours, so we round down using integer division.
        billable_hours = int(billable_seconds // 3600)
        
        return billable_hours
    
    # If the idle period does not cross the midnight threshold, it is not billable.
    return 0

# Allow user to upload a CSV file
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    # Read the uploaded CSV into a pandas DataFrame
    df = pd.read_csv(uploaded_file)
    # Clean up column names by stripping leading/trailing whitespace
    df.columns = df.columns.str.strip()

    # --- Data Processing and Calculation ---

    # Convert date/time columns to datetime objects for calculations
    # The 'errors='coerce'' argument will turn any unparseable dates into NaT (Not a Time)
    df['Session Start'] = pd.to_datetime(df['Date (console local time)'], errors='coerce')

    # Drop any rows where the date could not be parsed
    df.dropna(subset=['Session Start'], inplace=True)

    # Calculate the end of the charging period
    df['Charge End'] = df.apply(
        lambda row: row['Session Start'] + pd.to_timedelta(row['Charge Time (s)'], unit='s'),
        axis=1
    )

    # --- UI for Date Filtering ---

    # Create a date picker for filtering sessions
    min_date = df['Session Start'].dt.date.min()
    max_date = df['Session Start'].dt.date.max()

    start_date, end_date = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        help="Select the start and end dates for the report."
    )

    # Apply the date range filter to the DataFrame
    mask = (df['Session Start'].dt.date >= start_date) & (df['Session Start'].dt.date <= end_date)
    filtered_df = df[mask].copy()

    # --- Cost Calculation ---

    results = []
    # Group the data by each unique QR Code Name to aggregate costs
    for name, group in filtered_df.groupby('QR Code Name'):
        total_power = group['Power Usage (kWh)'].sum()
        power_cost = total_power * 0.22  # Power cost at $0.22 per kWh

        total_idle_cost = 0
        total_idle_hours_billed = 0
        
        # Iterate through each charging session for the user
        for idx, row in group.iterrows():
            # Calculate billable hours using the corrected logic
            billable_hours = billable_idle_hours_before_midnight(row['Charge End'], row['Idle Time (s)'])
            
            # Add to the totals for this user
            total_idle_hours_billed += billable_hours
            total_idle_cost += billable_hours * 5.0  # Idle cost at $5.00 per hour

        # Calculate the final total amount
        total_amount = power_cost + total_idle_cost

        # Append the aggregated results for this user to our list
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

        # Prepare the dataframe for CSV download
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
