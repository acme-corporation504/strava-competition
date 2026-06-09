import requests
from datetime import timedelta, datetime
import pandas as pd
import os
import json
import math



CSV_FILE = "strava_segment_times.csv"

def load_athlete_tokens(TOKEN_FILE):
    """Reads tokens securely from the local JSON file."""
    
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)
    

def save_athlete_tokens(TOKEN_FILE, tokens_dict):
    """Saves updated tokens back to the JSON file."""
    
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens_dict, f, indent=4)


def get_initial_tokens(client_id, client_secret, code, TOKEN_URL):
    """Exchanges the authorization code for access and refresh tokens. This must be done once per athlete during the initial OAuth flow."""
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }
    response = requests.post(TOKEN_URL, data=payload)
    print(response.json())
    try:
        data = response.json()
        print(data.get('scope', ''))
        if 'activity:read' not in data.get('scope', '') and 'activity:read_all' not in data.get('scope', ''):
            print("❌ ERROR: Your refresh token does not have 'activity:read' or 'activity:read_all' scopes!")
            print("Go back to the browser OAuth step and include &scope=activity:read_all")
            exit()
    except ValueError:
        print("Failed to parse token exchange response as JSON:")
        print(response.text)
        return None

    return data.get("access_token"), data.get("refresh_token")


def get_access_token(client_id, client_secret, refresh_token, TOKEN_URL):
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
        print(f"scope: {data.get('scope', '')}")
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
    start_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    end_date = start_date + timedelta(days=1)

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
    
    combined_df['rank'] = combined_df.groupby(['Date', 'Segment ID'])['Elapsed Time (s)'].rank(method='min').astype(int)

    combined_df['points'] = combined_df.apply(lambda row: max(5 - (row['rank'] - 1), 0), axis=1)
    
    combined_df.to_csv(CSV_FILE, index=False, encoding="utf-8")
    
    print(f"[System] Successfully sorted and saved to {CSV_FILE}")


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in meters."""
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of Earth in meters
    r = 6371000 
    return c * r


def get_arrival_time(access_token, activity_id, target_lat, target_lng):

    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    activity_res = requests.get(f"https://www.strava.com/api/v3/activities/{activity_id}", headers=headers).json()
    
    if 'start_date_local' not in activity_res:
        raise Exception(f"Error fetching activity: {activity_res.get('message', 'Unknown error')}")
        
    start_time_str = activity_res['start_date_local']  # Example: "2026-05-20T08:00:00Z"
    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")
    
    # 2. Fetch the latlng and time streams
    streams_url = f"https://www.strava.com/api/v3/activities/{activity_id}/streams"
    params = {'keys': 'latlng,time', 'key_by_type': 'true'}
    streams_res = requests.get(streams_url, headers=headers, params=params).json()
    
    latlng_data = streams_res.get('latlng', {}).get('data', [])
    time_data = streams_res.get('time', {}).get('data', [])
    
    if not latlng_data or not time_data:
        raise Exception("Could not retrieve stream data for this activity.")

    # 3. Find the index of the closest coordinate
    min_distance = float('inf')
    closest_index = -1
    
    # what happens if there are multiple points with the same minimum distance? In that case, we will take the first one we encounter (the earliest in the activity). This is a reasonable approach since we want to know the arrival time at the target location, and if multiple points are equidistant, the first one would represent the initial arrival.
    distance_list = []
    for idx, coord in enumerate(latlng_data):
        distance = haversine_distance(target_lat, target_lng, coord[0], coord[1])
        distance_list.append(distance)
        # collect all indexes which have the same minimum distance (in case of ties)
        # for example hitting gears twice to count the two laps
        if distance < min_distance:
            min_distance = distance
            closest_index = idx
    
    indices = [i for i, x in enumerate(distance_list) if x == min_distance]
    data_list = []
    for idx in indices:
        elapsed_seconds = time_data[idx]
        arrival_time = start_time + timedelta(seconds=elapsed_seconds)

        data_list.append({
        "arrival_time_unix_timestamp": int(arrival_time.timestamp()),
        "arrival_time": arrival_time.strftime("%Y-%m-%d %H:%M:%S"),
        "distance_to_target_meters": round(min_distance, 2),
        "elapsed_seconds": elapsed_seconds
        })

    # 4. Calculate the absolute arrival timestamp
    elapsed_seconds = time_data[closest_index]
    arrival_time = start_time + timedelta(seconds=elapsed_seconds)
    
    # return {
    #     "arrival_time_unix_timestamp": int(arrival_time.timestamp()),
    #     "arrival_time": arrival_time.strftime("%Y-%m-%d %H:%M:%S"),
    #     "distance_to_target_meters": round(min_distance, 2),
    #     "elapsed_seconds": elapsed_seconds
    # }

    return data_list