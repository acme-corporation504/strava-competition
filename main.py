import time
from dotenv import load_dotenv
import os
from utilities import *

# --- CONFIGURATION ---
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE = "tokens.json"
TOKEN_URL = "https://www.strava.com/oauth/token"

TARGET_SEGMENTS = [712653, 12512083, 13419662, 9488848]

SEGMENTS_DICT = {
    5476260: "Just Visiting",
    712653: "Lakeshore Speedway (Eastbound)",
    12512083: "Lakeshore: Kipling > Islington",
    13419662: "Ellis from Gardens",
    9488848: "SPANISH HILL",
    17287772: "Dup --> Dav on Sym"
    }

TARGET_ATHLETES = [10611852, 4037596, 3179714]
athlete = {
    10611852:'Winston Chong', 
    4037596: 'Spagz', 
    3179714: 'Julian',
    7019517: 'Brian Chou'
    }

GPS_DICT = {
            # "colborne and queensway": (43.639658, -79.459587), 
            "colborne and queensway": (43.639715, -79.459898),
            "just after colborne and queensway": (43.639367, -79.461283),
            "gears mississauga": (43.548647, -79.590383), 
            "town sign toronto": (43.589353, -79.545938), 
        }


def main():
    refresh_token_check = False
    TARGET_DATE = "2026-06-05"
    
    ATHLETE_TOKENS = load_athlete_tokens(TOKEN_FILE)
    print(ATHLETE_TOKENS)

    all_runs_data = []
    new = []
    for TARGET_ATHLETE_ID_str, ref_token in ATHLETE_TOKENS.items():
        TARGET_ATHLETE_ID = int(TARGET_ATHLETE_ID_str)
        athlete_name = athlete[TARGET_ATHLETE_ID]
        print(f"\n{athlete[TARGET_ATHLETE_ID]} - Refreshing access token...")
        if athlete_name in new:
            print("getting initial tokens")
            access_token, refresh_token  = get_initial_tokens(CLIENT_ID, CLIENT_SECRET, ref_token, TOKEN_URL)
            new.remove(athlete_name)
        else:
            print("refreshing access token")
            access_token, refresh_token  = get_access_token(CLIENT_ID, CLIENT_SECRET, ref_token, TOKEN_URL)
        print(f"access token {access_token}, refresh token {refresh_token}")
        if ATHLETE_TOKENS[str(TARGET_ATHLETE_ID)] != refresh_token:
            ATHLETE_TOKENS[str(TARGET_ATHLETE_ID)] = refresh_token  # Update with new refresh token (this is only necessary because of temp refresh tokens)
            refresh_token_check = True
        for TARGET_SEGMENT_ID in SEGMENTS_DICT.keys():
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
                    "Athlete Name": athlete_name,
                    "Date": TARGET_DATE,
                    "Segment ID": TARGET_SEGMENT_ID,
                    "Segment Name": name,
                    "Elapsed Time (s)": effort.get("elapsed_time"),
                    "Effort ID": effort.get("id")
                }

                all_runs_data.append(athlete_data)
                time.sleep(0.5)
        
        activity_id = effort.get("activity").get("id")
        print(f"Fetching arrival time for {athlete_name} (Activity ID: {activity_id})...")
        
        for location_name, (lat, lng) in GPS_DICT.items():
            arrival_info_list = get_arrival_time(access_token, activity_id, lat, lng)
            for arrival_info in arrival_info_list:
                print(f"Arrival info for {location_name}: {arrival_info['arrival_time']} (Unix Timestamp: {arrival_info['arrival_time_unix_timestamp']})")

                # might have to rejigger this a bit since we're allowing two laps of LP
                if location_name == "just after colborne and queensway":
                    start_run = arrival_info['arrival_time_unix_timestamp']            
                elif location_name == "gears mississauga":
                    finish_run = arrival_info['arrival_time_unix_timestamp']
        elapsed_time = (finish_run - start_run) / 60
        print(f"Elapsed time between colborne and queensway and gears mississauga: {elapsed_time:.2f} minutes")

    if refresh_token_check:
        save_athlete_tokens(TOKEN_FILE, ATHLETE_TOKENS)

    append_to_csv_with_pandas(all_runs_data)

if __name__ == "__main__":
    main()

    
# curl -X GET "https://strava.com" \
#      -H "Authorization: Bearer [NEW_ACCESS_TOKEN]"

'''
curl -X POST https://strava.com \
  -F client_id=245963 \
  -F client_secret=ff2ef6fe7c91586380ba6f85e542df563e342b65 \
  -F code=1666a002d60064234a8f7e0f55f9fbe20260d75a \
  -F grant_type=authorization_code


this is for getting the initial access and refresh tokens. You only need to do this once per athlete (or whenever you need to generate new tokens). After you have the refresh token, you can use it to get new access tokens without needing to go through the authorization code flow again.
https://www.strava.com/oauth/authorize?client_id=245963&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=read,activity:read,activity:read_all,read_all
'''

