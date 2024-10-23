import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(page_title="Enhanced Weather Monitor", page_icon="🌦️", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .stApp {
        background-color: #f0f2f6;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
    }
    .stAlert {
        background-color: #ffeb3b;
    }
    </style>
    """, unsafe_allow_html=True)

# OpenWeatherMap API configuration
API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "238b164a9ad9727211ee6bc4d30ffff0")
BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

# Indian metros with coordinates
CITIES = {
    "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Chennai": (13.0827, 80.2707),
    "Bangalore": (12.9716, 77.5946),
    "Kolkata": (22.5726, 88.3639),
    "Hyderabad": (17.3850, 78.4867)
}

# Initialize session state
if 'weather_data' not in st.session_state:
    st.session_state.weather_data = pd.DataFrame()
if 'daily_summaries' not in st.session_state:
    st.session_state.daily_summaries = pd.DataFrame()
if 'alerts' not in st.session_state:
    st.session_state.alerts = []

@st.cache_data(ttl=300)
def fetch_weather_data(city):
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric"
    }
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Use current timestamp if 'dt' is not in the response
        timestamp = data.get("dt", int(datetime.now().timestamp()))
        
        return {
            "city": city,
            "main": data.get("weather", [{}])[0].get("main", "Unknown"),
            "description": data.get("weather", [{}])[0].get("description", "Unknown"),
            "temp": data.get("main", {}).get("temp", 0),
            "feels_like": data.get("main", {}).get("feels_like", 0),
            "humidity": data.get("main", {}).get("humidity", 0),
            "pressure": data.get("main", {}).get("pressure", 0),
            "wind_speed": data.get("wind", {}).get("speed", 0),
            "dt": datetime.fromtimestamp(timestamp)
        }
    except requests.RequestException as e:
        st.error(f"Error fetching data for {city}: {str(e)}")
        return None

def update_weather_data():
    new_data = []
    for city in CITIES:
        data = fetch_weather_data(city)
        if data:
            new_data.append(data)
    
    new_df = pd.DataFrame(new_data)
    
    if not new_df.empty:
        st.session_state.weather_data = pd.concat([st.session_state.weather_data, new_df], ignore_index=True)
        st.session_state.weather_data.drop_duplicates(subset=['city', 'dt'], inplace=True)

def calculate_daily_summary():
    if st.session_state.weather_data.empty:
        return

    daily_data = st.session_state.weather_data.set_index('dt')
    daily_summary = daily_data.groupby([daily_data.index.date, 'city']).agg({
        'temp': ['mean', 'max', 'min'],
        'humidity': 'mean',
        'wind_speed': 'mean',
        'main': lambda x: x.value_counts().index[0]
    }).reset_index()
    daily_summary.columns = ['date', 'city', 'avg_temp', 'max_temp', 'min_temp', 'avg_humidity', 'avg_wind_speed', 'dominant_weather']
    st.session_state.daily_summaries = daily_summary

def check_alerts(thresholds):
    if st.session_state.weather_data.empty:
        return

    latest_data = st.session_state.weather_data.groupby('city').last().reset_index()
    
    for _, row in latest_data.iterrows():
        if row['temp'] > thresholds['temp']:
            st.session_state.alerts.append(f"🌡️ Alert: Temperature in {row['city']} exceeded {thresholds['temp']}°C. Current temperature: {row['temp']:.1f}°C")
        
        if row['humidity'] > thresholds['humidity']:
            st.session_state.alerts.append(f"💧 Alert: Humidity in {row['city']} exceeded {thresholds['humidity']}%. Current humidity: {row['humidity']}%")
        
        if row['wind_speed'] > thresholds['wind_speed']:
            st.session_state.alerts.append(f"🌬️ Alert: Wind speed in {row['city']} exceeded {thresholds['wind_speed']} m/s. Current wind speed: {row['wind_speed']} m/s")
        
        if row['main'] == thresholds['condition']:
            st.session_state.alerts.append(f"🌤️ Alert: {thresholds['condition']} weather detected in {row['city']}.")

def create_map(data):
    fig = go.Figure()

    for city, (lat, lon) in CITIES.items():
        city_data = data[data['city'] == city].iloc[-1]
        fig.add_trace(go.Scattermapbox(
            lat=[lat],
            lon=[lon],
            mode='markers',
            marker=go.scattermapbox.Marker(size=14),
            text=f"{city}<br>Temp: {city_data['temp']:.1f}°C<br>{city_data['main']}",
            hoverinfo='text'
        ))

    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(
            center=dict(lat=22.5726, lon=78.3639),  # Center of India
            zoom=4
        ),
        showlegend=False,
        height=400,
        margin={"r":0,"t":0,"l":0,"b":0}
    )

    return fig

def main():
    st.title("🌦️ Enhanced Real-Time Weather Monitoring System")

    # Sidebar for user inputs
    st.sidebar.header("Settings")
    update_interval = st.sidebar.slider("Update interval (seconds)", 60, 300, 300)
    
    # Thresholds
    st.sidebar.subheader("Alert Thresholds")
    temp_threshold = st.sidebar.number_input("Temperature threshold (°C)", 0, 50, 35)
    humidity_threshold = st.sidebar.number_input("Humidity threshold (%)", 0, 100, 80)
    wind_speed_threshold = st.sidebar.number_input("Wind speed threshold (m/s)", 0, 50, 10)
    condition_threshold = st.sidebar.selectbox("Weather condition alert", ["Rain", "Snow", "Clear", "Clouds"])

    thresholds = {
        'temp': temp_threshold,
        'humidity': humidity_threshold,
        'wind_speed': wind_speed_threshold,
        'condition': condition_threshold
    }

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Fetch Latest Weather Data"):
            update_weather_data()
            calculate_daily_summary()
            check_alerts(thresholds)

        # Display current weather map
        st.subheader("Current Weather Map")
        if not st.session_state.weather_data.empty:
            st.plotly_chart(create_map(st.session_state.weather_data), use_container_width=True)

    with col2:
        # Display alerts
        st.subheader("Weather Alerts")
        if st.session_state.alerts:
            for alert in st.session_state.alerts[-5:]:  # Show last 5 alerts
                st.warning(alert)
        else:
            st.info("No active alerts")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["Current Weather", "Daily Summary", "Historical Data"])

    with tab1:
        st.header("Current Weather")
        if not st.session_state.weather_data.empty:
            latest_data = st.session_state.weather_data.groupby('city').last().reset_index()
            st.dataframe(latest_data, use_container_width=True)

            # Visualize current temperatures
            fig = px.bar(latest_data, x='city', y='temp', 
                         title="Current Temperatures", 
                         color='temp', 
                         color_continuous_scale=px.colors.sequential.Viridis)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("Daily Weather Summary")
        if not st.session_state.daily_summaries.empty:
            st.dataframe(st.session_state.daily_summaries, use_container_width=True)

            # Visualize temperature trends
            fig = px.line(st.session_state.daily_summaries, x='date', y=['avg_temp', 'max_temp', 'min_temp'], 
                          color='city', title="Temperature Trends")
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("Historical Data")
        date_range = st.date_input("Select Date Range", 
                                   [datetime.today() - timedelta(days=7), datetime.today()])
        
        if not st.session_state.weather_data.empty:
            filtered_data = st.session_state.weather_data[
                (st.session_state.weather_data['dt'] >= pd.to_datetime(date_range[0])) &
                (st.session_state.weather_data['dt'] <= pd.to_datetime(date_range[1]))
            ]
            if not filtered_data.empty:
                st.dataframe(filtered_data, use_container_width=True)

                # Plot historical temperature data
                fig = px.line(filtered_data, x='dt', y='temp', color='city', title="Historical Temperatures")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data available for the selected date range.")
        else:
            st.info("No historical data available.")

if __name__ == "__main__":
    main()
