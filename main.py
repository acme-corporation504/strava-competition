import requests
import datetime
import time
from dotenv import load_dotenv
import os
import json
import pandas as pd


# --- CONFIGURATION ---
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
# REFRESH_TOKEN = "3b999a2c25db6d10fe00328899d2ccde78e1394e"
# AUTHORIZATION_CODE = "c3715acee0c39a6c14725258791f616fc5bebe76"
TOKEN_FILE = "tokens.json"
CSV_FILE = "strava_segment_times.csv"
TOKEN_URL = "https://www.strava.com/oauth/token"

# Target configuration (Athletes must have authorized your app)
TARGET_SEGMENTS = [712653, 12512083, 13419662, 9488848]
TARGET_ATHLETES = [10611852, 4037596, 3179714]
athlete = {10611852:'Winston Chong', 4037596: 'Spagz', 3179714: 'Julian'}


def load_athlete_tokens():
    """Reads tokens securely from the local JSON file."""
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)
    

def save_athlete_tokens(tokens_dict):
    """Saves updated tokens back to the JSON file."""
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens_dict, f, indent=4)


def get_access_token(client_id, client_secret, refresh_token):
    """Refreshes the expired access token."""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(TOKEN_URL, data=payload)
    try:
        data = response.json()
    except ValueError:
        print("Failed to parse token refresh response as JSON:")
        print(response.text)
        return None

    return data.get("access_token"), data.get("refresh_token")


def get_segment_times(access_token, segment_id, athlete_id):
    """Fetches segment efforts for a specific authorized athlete."""
    url = "https://www.strava.com/api/v3/segment_efforts"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "segment_id": segment_id,
        "athlete_id": athlete_id,
        "per_page": 5,  # Fetches the 5 most recent efforts
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            print("Failed to parse segment efforts response as JSON:")
            print(response.text)
            return None
    elif response.status_code == 429:
        print("Rate limit exceeded. Waiting 15 minutes...")
        return None

    print(f"Error {response.status_code}: {response.text}")

    return None


def get_authenticated_athlete_efforts_by_date(access_token, segment_id, target_date_str):
    """target_date_str format: 'YYYY-MM-DD' (e.g., '2026-05-15')"""
    
    # CORRECT ENDPOINT: Pass segment_id as a query parameter
    url = "https://www.strava.com/api/v3/segment_efforts"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Convert the target date into proper ISO 8601 strings
    start_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    end_date = start_date + datetime.timedelta(days=1)

    params = {
        "segment_id": segment_id,
        "start_date_local": start_date.strftime("%Y-%m-%dT00:00:00Z"),
        "end_date_local": end_date.strftime("%Y-%m-%dT23:59:59Z"),
    }

    res = requests.get(url, headers=headers, params=params)

    if res.status_code != 200:
        print(f"Error {res.status_code}:", res.text)
        return None

    efforts = res.json()

    if not efforts:
        print(f"No efforts found on Segment {segment_id} on {target_date_str}.")
        return []

    # print(efforts)
    # print(f"Found {len(efforts)} effort(s) on {target_date_str}:")
    # for effort in efforts:
    #     print(f"- Effort ID: {effort['id']}")
    #     print(f"  Moving Time: {effort['moving_time']} seconds")
    #     print(f"  Elapsed Time: {effort['elapsed_time']} seconds")
    #     print(f"  Activity ID: {effort['activity']['id']}")
    #     print("---")

    return efforts


def append_to_csv_with_pandas(results_list):
    """Converts a list of dicts to a DataFrame and appends it to the CSV file securely."""
    if not results_list:
        print("[System] No new data to write.")
        return

    new_df = pd.DataFrame(results_list)

    if os.path.isfile(CSV_FILE):
        # Read the existing data
        old_df = pd.read_csv(CSV_FILE)
        # Combine old data and new data
        combined_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    if "Effort ID" in combined_df.columns:
        combined_df.drop_duplicates(subset=["Effort ID"], keep="first", inplace=True)

    combined_df.sort_values(
        by=["Date", "Segment ID", "Elapsed Time (s)"], 
        ascending=[True, True, True],
        inplace=True
        )
    
    combined_df.to_csv(CSV_FILE, index=False, encoding="utf-8")
    
    print(f"[System] Successfully sorted and saved to {CSV_FILE}")


def main():
    refresh_token_check = False
    TARGET_DATE = "2026-05-15"
    ATHLETE_TOKENS = load_athlete_tokens()

    all_runs_data = []
    for TARGET_ATHLETE_ID_str, ref_token in ATHLETE_TOKENS.items():
        TARGET_ATHLETE_ID = int(TARGET_ATHLETE_ID_str)
        print(f"\n{athlete[TARGET_ATHLETE_ID]} - Refreshing access token...")

        access_token, refresh_token  = get_access_token(CLIENT_ID, CLIENT_SECRET, ref_token)
        if ATHLETE_TOKENS[str(TARGET_ATHLETE_ID)] != refresh_token:
            ATHLETE_TOKENS[str(TARGET_ATHLETE_ID)] = refresh_token  # Update with new refresh token (this is only necessary because of temp refresh tokens)
            refresh_token_check = True
        for TARGET_SEGMENT_ID in TARGET_SEGMENTS:
            efforts = get_authenticated_athlete_efforts_by_date(access_token, TARGET_SEGMENT_ID, TARGET_DATE)
            # print(efforts)
            for effort in efforts:
                name = effort.get("name")
                elapsed_time = effort.get("elapsed_time")
                start_date = effort.get("start_date_local")

                # Convert seconds to MM:SS format
                minutes = elapsed_time // 60
                seconds = elapsed_time % 60

                print(
                    f"{name}  - Time: {minutes:02d}:{seconds:02d} | Date: {start_date}"
                )

                athlete_data = {
                    "Athlete Name": athlete[TARGET_ATHLETE_ID],
                    "Date": TARGET_DATE,
                    "Segment ID": TARGET_SEGMENT_ID,
                    "Segment Name": name,
                    "Elapsed Time (s)": effort.get("elapsed_time"),
                    "Effort ID": effort.get("id")
                }

                all_runs_data.append(athlete_data)
                time.sleep(0.5)

    if refresh_token_check:
        save_athlete_tokens(ATHLETE_TOKENS)

    append_to_csv_with_pandas(all_runs_data)

if __name__ == "__main__":
    main()

    


'''
curl -X POST https://strava.com \
  -F client_id=245963 \
  -F client_secret=ff2ef6fe7c91586380ba6f85e542df563e342b65 \
  -F code=1666a002d60064234a8f7e0f55f9fbe20260d75a \
  -F grant_type=authorization_code


this is for getting the initial access and refresh tokens. You only need to do this once per athlete (or whenever you need to generate new tokens). After you have the refresh token, you can use it to get new access tokens without needing to go through the authorization code flow again.
https://www.strava.com/oauth/authorize?client_id=245963&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=read_all
'''

