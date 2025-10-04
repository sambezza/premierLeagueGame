import streamlit as st
import pandas as pd
import os
import openpyxl
import json

@st.cache_data
def load_fixtures(file_path):
    """Load fixtures from Excel file"""
    try:
        df = pd.read_excel(file_path)
        # Clean column names
        df.columns = df.columns.str.strip()
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

def get_round_fixtures(df, round_num):
    """Get fixtures for a specific round"""
    round_df = df[df['Round Number'] == round_num].copy()
    return round_df

def calculate_points(pred_home, pred_away, actual_home, actual_away):
    """Calculate points and return detailed result counts"""
    points = 0
    exact = False
    correct_res = False
    try:
        pred_home = int(pred_home)
        pred_away = int(pred_away)
        actual_home = int(actual_home)
        actual_away = int(actual_away)
    except (ValueError, TypeError):
        return 0, False, False

    # Exact score: 5 points (and automatically correct result)
    if pred_home == actual_home and pred_away == actual_away:
        points = 5
        exact = True
        correct_res = True
    else:
        # Correct result (win/draw/loss): 2 points
        pred_result = "draw" if pred_home == pred_away else ("home" if pred_home > pred_away else "away")
        actual_result = "draw" if actual_home == actual_away else ("home" if actual_home > actual_away else "away")

        if pred_result == actual_result:
            points = 2
            correct_res = True

    return points, exact, correct_res

#Update calculate_player_points
def calculate_player_points(player_name, fixtures_df, all_predictions):
    """Calculate total points for a player across all rounds"""
    if player_name not in all_predictions:
        return 0, {}

    total_points = 0
    round_breakdown = {}

    # Use the passed-in all_predictions data
    player_predictions = all_predictions[player_name]

    for round_num, predictions in player_predictions.items():
        round_fixtures = get_round_fixtures(fixtures_df, round_num)
        round_points = 0

        # Check if results are available for this round
        if round_fixtures['Home Score'].notna().any():
            for idx, (fixture_idx, pred) in enumerate(predictions.items()):
                fixture = round_fixtures[round_fixtures.index == fixture_idx]
                if not fixture.empty and pd.notna(fixture.iloc[0]['Home Score']):
                    actual_home = int(fixture.iloc[0]['Home Score'])
                    actual_away = int(fixture.iloc[0]['Away Score'])
                    points, _, _ = calculate_points(
                        pred['home'], pred['away'], actual_home, actual_away
                    )

                    round_points += points

            round_breakdown[round_num] = round_points
            total_points += round_points

    return total_points, round_breakdown

#Update update_leaderboard
def update_leaderboard(fixtures_df):
    """
    Update leaderboard with all predictions by pulling data directly from the JSON file.

    The returned dictionary contains 'Exact Scores', 'Correct Results', and 'Total Points'
    for each player.
    """
    all_predictions = load_predictions_data()

    leaderboard = {}

    for player in all_predictions.keys():
        total_points = 0
        exact_scores = 0
        correct_results = 0

        # Use the loaded predictions
        player_rounds_predictions = all_predictions[player]

        for round_num, predictions in player_rounds_predictions.items():
            # Ensure round_num is handled as an integer here if it was string in JSON keys
            round_fixtures = get_round_fixtures(fixtures_df, round_num)

            # Check if results are available for this round
            if round_fixtures['Home Score'].notna().any():
                for fixture_idx, pred in predictions.items():
                    fixture = round_fixtures[round_fixtures.index == fixture_idx]

                    if not fixture.empty and pd.notna(fixture.iloc[0]['Home Score']):
                        actual_home = int(fixture.iloc[0]['Home Score'])
                        actual_away = int(fixture.iloc[0]['Away Score'])
                        pred_home = pred['home']
                        pred_away = pred['away']

                        # 🎯 Use the DRY detailed calculation function
                        points, exact, correct_res = calculate_points(
                            pred_home, pred_away, actual_home, actual_away
                        )

                        total_points += points
                        if exact:
                            exact_scores += 1
                        if correct_res:
                            correct_results += 1

        leaderboard[player] = {
            'Exact Scores': exact_scores,
            'Correct Results': correct_results,
            'Total Points': total_points
        }

    return leaderboard

# Function to load predictions outside of Streamlit's state management
def load_predictions_data():
    """Load predictions from file for calculations"""
    if os.path.exists(PREDICTIONS_FILE):
        with open(PREDICTIONS_FILE, 'r') as f:
            json_predictions = json.load(f)
            # Convert string keys back to integers where needed
            predictions = {}
            for player, rounds in json_predictions.items():
                predictions[player] = {}
                for round_num, preds in rounds.items():
                    predictions[player][int(round_num)] = {
                        int(k): v for k, v in preds.items()
                    }
            return predictions
    return {}

def save_predictions():
    """Save predictions to file"""
    # Convert any non-string keys to strings for JSON compatibility
    json_predictions = {}
    for player, rounds in st.session_state.predictions.items():
        json_predictions[player] = {}
        for round_num, preds in rounds.items():
            json_predictions[player][str(round_num)] = {
                str(k): v for k, v in preds.items()
            }

    with open(PREDICTIONS_FILE, 'w') as f:
        json.dump(json_predictions, f, indent=2)

def is_round_locked(fixtures_df, round_num):
    round_fixtures = get_round_fixtures(fixtures_df, round_num)

    # Ensure 'Date' is datetime and find the earliest match time
    # (Assuming you applied the improvement to convert 'Date' column once in load_fixtures)

    if round_fixtures.empty or round_fixtures['Date'].isna().all():
        return False  # No dates available, so don't lock it

    # Find the earliest date/time for the fixtures in this round
    first_match_time = round_fixtures['Date'].min()

    # Compare the earliest match time to the current time
    return pd.Timestamp.now() >= first_match_time

# Configuration - Update this path to your Excel file
PREDICTIONS_FILE = "predictions.json"
FIXTURES_FILE = "premier_league_fixtures.xlsx"  # Change this to your file name/path

# Initialize session state
if 'predictions' not in st.session_state:
    st.session_state.predictions = load_predictions_data()
if 'fixtures_df' not in st.session_state:
    st.session_state.fixtures_df = None

# Streamlit UI
st.set_page_config(layout="wide")
st.title("⚽ The Boys Score Prediction Game")
st.markdown("---")

# Load fixtures from file
if st.session_state.fixtures_df is None:
    if os.path.exists(FIXTURES_FILE):
        st.session_state.fixtures_df = load_fixtures(FIXTURES_FILE)
    else:
        st.error(f"❌ Fixtures file not found: {FIXTURES_FILE}")
        st.info("Please ensure your Excel file is in the same directory as this script.")
        st.stop()

if st.session_state.fixtures_df is not None:
    fixtures_df = st.session_state.fixtures_df
    available_rounds = sorted(fixtures_df['Round Number'].unique())

    # Tabs
    tab1, tab2 = st.tabs(["Make Predictions", "Leaderboard"])

    with tab1:
        st.header("Make Your Predictions")

        player_name = st.selectbox("Select your name:", ["Jaaaaaamieeee","Kawazy J","Lil Wheezy","Seagullhead1","Shezza","Stiggsy"], key="player_name")

        if player_name:
            # Auto-select next round based on today's date
            now = pd.Timestamp.now()  # current date & time
            default_round = available_rounds[0]  # fallback

            for i, round_num in enumerate(available_rounds):
                round_fixtures = get_round_fixtures(fixtures_df, round_num)

                if (round_fixtures['Date'] <= now).any():
                    # At least one fixture has started → show NEXT round if it exists
                    if i + 1 < len(available_rounds):
                        default_round = available_rounds[i + 1]
                    else:
                        default_round = round_num  # last round, stay on it
                elif (round_fixtures['Date'] > now).any():
                    # No fixtures started yet → show this round
                    default_round = round_num
                    break  # stop at the first upcoming round

            default_index = available_rounds.index(default_round)

            round_number = st.selectbox(
                "Select Round:",
                available_rounds,
                index=default_index,
                key="pred_round"
            )

            round_fixtures = get_round_fixtures(fixtures_df, round_number)
            locked = is_round_locked(fixtures_df, round_number)

            # Check if predictions already exist for this player and round
            existing_predictions = None
            if player_name in st.session_state.predictions:
                if round_number in st.session_state.predictions[player_name]:
                    existing_predictions = st.session_state.predictions[player_name][round_number]
                    st.info("You have already made predictions for this round. You can update them below.")

            st.subheader(f"Round {round_number} Fixtures")

            predictions = {}
            if locked:
                st.warning(
                    f"🔒 **Round {round_number} is locked.** The first match has started. Predictions can no longer be updated.")

            for idx, row in round_fixtures.iterrows():
                home_team = row['Home Team']
                away_team = row['Away Team']
                date = row['Date']
                location = row['Location']

                # Get existing prediction if available
                default_home = existing_predictions[idx][
                    'home'] if existing_predictions and idx in existing_predictions else 0
                default_away = existing_predictions[idx][
                    'away'] if existing_predictions and idx in existing_predictions else 0

                # Create a card using container with border
                with st.container(border=True):
                    st.caption(f"📍 {location} | 📅 {date}")

                    col1, col2, col3, col4 = st.columns([0.5, 0.5, 0.5, 3])

                    with col1:
                        st.write(f"**{home_team}**")
                    with col2:
                        home_score = st.number_input(
                            "Score",
                            min_value=0,
                            max_value=10,
                            value=default_home,
                            key=f"pred_home_{player_name}_{idx}_{round_number}",
                            label_visibility="collapsed"
                        )
                    with col3:
                        away_score = st.number_input(
                            "Score",
                            min_value=0,
                            max_value=10,
                            value=default_away,
                            key=f"pred_away_{player_name}_{idx}_{round_number}",
                            label_visibility="collapsed"
                        )
                    with col4:
                        st.write(f"**{away_team}**")

                    predictions[idx] = {'home': home_score, 'away': away_score}

                    # Show actual result if available
                    if pd.notna(row['Home Score']):
                        actual_home = int(row['Home Score'])
                        actual_away = int(row['Away Score'])
                        st.success(f"✅ Actual Result: {actual_home} - {actual_away}")

                        if existing_predictions and idx in existing_predictions:
                            points, _, _ = calculate_points(
                                existing_predictions[idx]['home'],
                                existing_predictions[idx]['away'],
                                actual_home,
                                actual_away
                            )
                            st.info(f"🎯 Your Points: {points}")

            if st.button("Submit Predictions", type="primary", disabled=locked):
                if player_name not in st.session_state.predictions:
                    st.session_state.predictions[player_name] = {}

                st.session_state.predictions[player_name][round_number] = predictions
                save_predictions()
                st.success(f"✅ Predictions submitted for {player_name} - Round {round_number}!")


    with tab2:
        st.header("🏆 Leaderboard")

        # Check if the predictions file has any data
        if os.path.exists(PREDICTIONS_FILE) and os.path.getsize(PREDICTIONS_FILE) > 2:

            # Use the updated function which pulls data directly from JSON
            leaderboard = update_leaderboard(fixtures_df)

            # Convert dictionary to DataFrame
            leaderboard_df = pd.DataFrame.from_dict(leaderboard, orient='index')
            leaderboard_df.index.name = 'Player'

            # Sort the DataFrame by 'Total Points'
            leaderboard_df = leaderboard_df.sort_values(
                by='Total Points',
                ascending=False
            ).reset_index()

            # Add Rank column
            leaderboard_df.index += 1
            leaderboard_df.insert(0, 'Rank', leaderboard_df.index)

            # Rename columns for display
            leaderboard_df.columns = [
                'Rank', 'Player', 'Exact Scores', 'Correct Results', 'Total Points'
            ]

            # Display leaderboard
            st.dataframe(
                leaderboard_df,
                width='stretch',
                hide_index=True  # Hide the default index, as we have a 'Rank' column
            )

            # Show detailed breakdown
            if st.checkbox("Show detailed breakdown by round"):
                st.subheader("Detailed Player Scores")

                # Reload predictions here to use in the breakdown (could also pass from update_leaderboard)
                all_predictions_data = load_predictions_data()

                selected_player = st.selectbox(
                    "Select Player:",
                    sorted(all_predictions_data.keys())
                )

                if selected_player:
                    # Pass the loaded predictions data
                    total_points, round_breakdown = calculate_player_points(
                        selected_player,
                        fixtures_df,
                        all_predictions_data
                    )

                    st.markdown(f"### {selected_player} - Total: {total_points} points")

                    # Use the loaded predictions data for the breakdown
                    player_predictions = all_predictions_data.get(selected_player, {})

                    for round_num in sorted(player_predictions.keys()):
                        # ... (rest of the detailed breakdown logic remains the same, but using player_predictions)
                        with st.expander(
                                f"Round {round_num} - {round_breakdown.get(round_num, 'Results pending')} points"):
                            predictions = player_predictions[round_num]
                            round_fixtures = get_round_fixtures(fixtures_df, round_num)
                            # ... (rest of the logic using 'predictions' and 'round_fixtures')

                            for fixture_idx, pred in predictions.items():
                                fixture = round_fixtures[round_fixtures.index == fixture_idx]
                                if not fixture.empty:
                                    with st.container(border=True):
                                        fixture = fixture.iloc[0]
                                        col1, col2 = st.columns([1, 1])

                                        with col1:
                                            st.write(f"**{fixture['Home Team']} vs {fixture['Away Team']}**")
                                            st.write(f"Your Prediction: {pred['home']} - {pred['away']}")

                                            if pd.notna(fixture['Home Score']):
                                                actual_home = int(fixture['Home Score'])
                                                actual_away = int(fixture['Away Score'])
                                                st.write(f"Actual Result: {actual_home} - {actual_away}")

                                        with col2:
                                            # Only calculate points if the match has been played
                                            if pd.notna(fixture['Home Score']):
                                                actual_home = int(fixture['Home Score'])
                                                actual_away = int(fixture['Away Score'])
                                                points, _, _ = calculate_points(pred['home'], pred['away'],
                                                                                actual_home, actual_away)
                                                if points == 4:
                                                    st.success(f"🎯 Perfect! **{points} points**")
                                                elif points > 0:
                                                    st.info(f"✓ **{points} points**")
                                                else:
                                                    st.error("✗ **0 points**")
                                            else:
                                                st.warning("Match not played yet")
                                else:
                                    st.warning("Match not found")

        else:
            st.info("No predictions submitted yet. Make your predictions in the first tab!")

else:
    st.error(f"❌ Could not load fixtures file: {FIXTURES_FILE}")
    st.info("Please check that the file exists and is in the correct format.")