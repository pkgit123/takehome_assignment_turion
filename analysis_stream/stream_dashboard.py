#!/usr/bin/env python3
"""
Streamlit Dashboard for Real-time DDoS Detection
===============================================

This dashboard provides real-time visualization of:
- Network traffic patterns
- DDoS attack alerts
- IP address analysis
- System metrics
- Alert trends over time
"""

import streamlit as st
import redis
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from collections import defaultdict, deque
import threading

# Page configuration
st.set_page_config(
    page_title="DDoS Detection Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .alert-high {
        background-color: #ffebee;
        border-left-color: #f44336;
    }
    .alert-medium {
        background-color: #fff3e0;
        border-left-color: #ff9800;
    }
    .alert-low {
        background-color: #e8f5e8;
        border-left-color: #4caf50;
    }
</style>
""", unsafe_allow_html=True)

class RedisDashboard:
    def __init__(self, host='localhost', port=6379):
        """Initialize Redis connection and data structures."""
        self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
        self.alert_history = deque(maxlen=1000)  # Keep last 1000 alerts
        self.traffic_history = deque(maxlen=1000)  # Keep last 1000 traffic records
        self.ip_stats = defaultdict(lambda: {
            'request_count': 0,
            'alert_count': 0,
            'first_seen': None,
            'last_seen': None,
            'ports_accessed': set(),
            'protocols': set()
        })
        
    def get_redis_connection_status(self):
        """Check if Redis is connected."""
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def get_stream_length(self, stream_name):
        """Get the length of a Redis stream."""
        try:
            return self.redis_client.xlen(stream_name)
        except:
            return 0
    
    def get_latest_alerts(self, count=50, until_time=None):
        """Get alerts from Redis, optionally filtered by time."""
        try:
            alerts = self.redis_client.xrevrange('alerts', count=count)
            alert_list = []
            for alert in alerts:
                alert_data = json.loads(alert[1]['alert'])
                
                # Filter by time if specified
                if until_time is not None:
                    alert_time = pd.to_datetime(alert_data.get('timestamp', ''))
                    if alert_time > until_time:
                        continue
                
                alert_list.append(alert_data)
            return alert_list
        except Exception as e:
            st.error(f"Error fetching alerts: {e}")
            return []
    
    def get_latest_traffic(self, count=50, until_time=None):
        """Get traffic records from Redis, optionally filtered by time."""
        try:
            traffic = self.redis_client.xrevrange('network_traffic', count=count)
            records = []
            for record in traffic:
                # The data is stored as a pandas Series string, need to parse it
                data_str = record[1]['data']
                # Convert the pandas Series string back to a dictionary
                import ast
                try:
                    # Parse the pandas Series string format
                    lines = data_str.strip().split('\n')
                    record_dict = {}
                    for line in lines:
                        if 'Name:' in line or 'dtype:' in line:
                            continue
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 2:
                                key = parts[0]
                                value = ' '.join(parts[1:])
                                record_dict[key] = value
                    
                    # Filter by time if specified
                    if until_time is not None and 'timestamp' in record_dict:
                        try:
                            record_time = pd.to_datetime(record_dict['timestamp'])
                            if record_time > until_time:
                                continue
                        except:
                            pass
                    
                    records.append(record_dict)
                except Exception as parse_error:
                    st.warning(f"Could not parse traffic record: {parse_error}")
                    continue
            return records
        except Exception as e:
            st.error(f"Error fetching traffic: {e}")
            return []
    
    def get_global_metrics(self):
        """Get global system metrics from Redis."""
        metrics = {}
        try:
            metrics['processed_records'] = int(self.redis_client.get('global:processed_records') or 0)
            metrics['total_alerts'] = int(self.redis_client.get('global:alerts:total') or 0)
            metrics['baseline_avg'] = float(self.redis_client.get('global:baseline:avg') or 0)
            metrics['baseline_std'] = float(self.redis_client.get('global:baseline:std') or 0)
        except:
            pass
        return metrics
    
    def get_time_range(self):
        """Get the time range of processed data."""
        time_range = {
            'oldest': None,
            'newest': None,
            'duration': 0
        }
        
        try:
            # Get all traffic records to find time range
            all_traffic = self.redis_client.xrange('network_traffic')
            if not all_traffic:
                return time_range
            
            timestamps = []
            for record in all_traffic:
                data_str = record[1]['data']
                
                # Parse the timestamp from the data string
                lines = data_str.strip().split('\n')
                for line in lines:
                    # Handle both quoted and unquoted timestamp lines
                    if line.startswith('"timestamp') or line.startswith('timestamp'):
                        # Extract timestamp value - handle the pandas Series format
                        # Remove quotes if present
                        line = line.strip('"')
                        # Split by whitespace and get the second part (the actual timestamp)
                        parts = line.split()
                        if len(parts) >= 2:
                            # Clean the timestamp string - remove any trailing parts
                            timestamp_str = parts[1].split('\\n')[0]  # Remove \n and anything after
                            try:
                                timestamp = pd.to_datetime(timestamp_str)
                                timestamps.append(timestamp)
                                break
                            except Exception:
                                continue
            
            if timestamps:
                time_range['oldest'] = min(timestamps)
                time_range['newest'] = max(timestamps)
                time_range['duration'] = int((time_range['newest'] - time_range['oldest']).total_seconds() / 60)
        
        except Exception as e:
            st.sidebar.warning(f"Could not determine time range: {e}")
        
        return time_range
    
    def update_dashboard_data(self):
        """Update dashboard data from Redis."""
        # Get selected time from session state
        selected_time = st.session_state.get('selected_time')
        
        # Get alerts filtered by time
        alerts = self.get_latest_alerts(100, until_time=selected_time)
        for alert in alerts:
            self.alert_history.append(alert)
        
        # Get traffic filtered by time
        traffic = self.get_latest_traffic(100, until_time=selected_time)
        for record in traffic:
            self.traffic_history.append(record)
        

        
        # Update IP statistics
        self._update_ip_stats()
    
    def _update_ip_stats(self):
        """Update IP address statistics."""
        # Get all IP keys from Redis
        try:
            ip_keys = self.redis_client.keys('ip:*:first_seen')
            for key in ip_keys:
                ip = key.split(':')[1]
                first_seen = self.redis_client.get(key)
                
                if ip not in self.ip_stats:
                    self.ip_stats[ip]['first_seen'] = first_seen
                
                self.ip_stats[ip]['last_seen'] = datetime.now().isoformat()
        except:
            pass

def create_alert_timeline_chart(alerts):
    """Create a timeline chart of alerts."""
    if not alerts:
        return go.Figure()
    
    df = pd.DataFrame(alerts)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    
    # Group by alert type and create timeline
    fig = go.Figure()
    
    for alert_type in df['alert_type'].unique():
        type_data = df[df['alert_type'] == alert_type]
        fig.add_trace(go.Scatter(
            x=type_data['timestamp'],
            y=[alert_type] * len(type_data),
            mode='markers',
            name=alert_type,
            marker=dict(size=8),
            hovertemplate='<b>%{y}</b><br>Time: %{x}<br>IP: %{text}<extra></extra>',
            text=type_data['source_ip']
        ))
    
    fig.update_layout(
        title="Alert Timeline",
        xaxis_title="Time",
        yaxis_title="Alert Type",
        height=400,
        showlegend=True
    )
    
    return fig

def create_ip_heatmap(alerts):
    """Create a heatmap of IP addresses and alert types."""
    if not alerts:
        return go.Figure()
    
    df = pd.DataFrame(alerts)
    ip_alert_counts = df.groupby(['source_ip', 'alert_type']).size().unstack(fill_value=0)
    
    fig = go.Figure(data=go.Heatmap(
        z=ip_alert_counts.values,
        x=ip_alert_counts.columns,
        y=ip_alert_counts.index,
        colorscale='Reds',
        hovertemplate='IP: %{y}<br>Alert Type: %{x}<br>Count: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title="IP Address vs Alert Type Heatmap",
        xaxis_title="Alert Type",
        yaxis_title="Source IP",
        height=500
    )
    
    return fig

def create_traffic_volume_chart(traffic_records):
    """Create a chart showing traffic volume over time."""
    if not traffic_records:
        fig = go.Figure()
        fig.add_annotation(
            text="No traffic data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(
            title="Network Traffic Volume Over Time",
            height=400
        )
        return fig
    
    try:
        df = pd.DataFrame(traffic_records)
        
        # Check if timestamp column exists
        if 'timestamp' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(
                text="No timestamp data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            fig.update_layout(
                title="Network Traffic Volume Over Time",
                height=400
            )
            return fig
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Resample to minute intervals
        df.set_index('timestamp', inplace=True)
        volume_by_minute = df.resample('1T').size()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=volume_by_minute.index,
            y=volume_by_minute.values,
            mode='lines+markers',
            name='Traffic Volume',
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.update_layout(
            title="Network Traffic Volume Over Time",
            xaxis_title="Time",
            yaxis_title="Records per Minute",
            height=400
        )
        
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error creating chart: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(
            title="Network Traffic Volume Over Time",
            height=400
        )
        return fig

def main():
    """Main dashboard function."""
    # Header
    st.markdown('<h1 class="main-header">🛡️ DDoS Detection Dashboard</h1>', unsafe_allow_html=True)
    
    # Initialize Redis connection
    dashboard = RedisDashboard()
    
    # Sidebar configuration
    st.sidebar.title("Dashboard Controls")
    
    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 1, 30, 5)
    
    # Time navigation slider
    st.sidebar.markdown("---")
    st.sidebar.subheader("⏰ Time Navigation")
    
    # Get time range for slider
    time_range = dashboard.get_time_range()
    
    if time_range['oldest'] and time_range['newest']:
        # Create time slider
        total_seconds = int((time_range['newest'] - time_range['oldest']).total_seconds())
        current_time = st.sidebar.slider(
            "Time Position",
            min_value=0,
            max_value=total_seconds,
            value=total_seconds,  # Default to latest time
            step=1
        )
        
        # Convert slider value to datetime
        selected_time = time_range['oldest'] + timedelta(seconds=current_time)
        st.sidebar.write(f"**Current View:** {selected_time.strftime('%H:%M:%S')}")
        
        # Store selected time in session state
        st.session_state['selected_time'] = selected_time
        st.session_state['time_range'] = time_range
        
        # Time animation controls
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("⏮️ Start"):
                st.session_state['animation_time'] = 0
                st.session_state['selected_time'] = time_range['oldest']
        
        with col2:
            if st.button("⏭️ End"):
                st.session_state['animation_time'] = total_seconds
                st.session_state['selected_time'] = time_range['newest']
        
        # Auto-play through time
        auto_play = st.sidebar.checkbox("Auto-play through time", value=False)
        if auto_play and 'animation_time' in st.session_state:
            # Increment time by 10 seconds
            current_animation_time = st.session_state.get('animation_time', 0)
            if current_animation_time < total_seconds:
                st.session_state['animation_time'] = min(current_animation_time + 10, total_seconds)
                st.session_state['selected_time'] = time_range['oldest'] + timedelta(seconds=st.session_state['animation_time'])
                time.sleep(0.5)  # Small delay for animation effect
    else:
        st.sidebar.info("No time data available for navigation")
        st.session_state['selected_time'] = None
        st.session_state['time_range'] = None
    
    # Connection status
    if dashboard.get_redis_connection_status():
        st.sidebar.success("✅ Redis Connected")
    else:
        st.sidebar.error("❌ Redis Disconnected")
        st.error("Cannot connect to Redis. Please ensure Redis is running.")
        return
    
    # Data coverage information
    time_range = dashboard.get_time_range()
    if time_range['oldest'] and time_range['newest']:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Data Coverage")
        st.sidebar.write(f"**Start:** {time_range['oldest'].strftime('%Y-%m-%d %H:%M:%S')}")
        st.sidebar.write(f"**End:** {time_range['newest'].strftime('%Y-%m-%d %H:%M:%S')}")
        st.sidebar.write(f"**Duration:** {time_range['duration']} minutes")
        st.sidebar.write(f"**Records:** {dashboard.get_stream_length('network_traffic')}")
    
    # Update data
    dashboard.update_dashboard_data()
    
    # Main dashboard layout
    col1, col2, col3, col4 = st.columns(4)
    
    # Get time range from traffic data
    time_range = dashboard.get_time_range()
    
    # Key metrics
    with col1:
        if time_range['oldest'] and time_range['newest']:
            st.metric(
                label="Data Timeframe",
                value=f"{time_range['oldest'].strftime('%H:%M:%S')} - {time_range['newest'].strftime('%H:%M:%S')}",
                delta=f"{time_range['duration']} minutes"
            )
        else:
            st.metric(
                label="Total Records",
                value=dashboard.get_stream_length('network_traffic'),
                delta=None
            )
    
    with col2:
        # Show alerts up to selected time
        selected_time = st.session_state.get('selected_time')
        if selected_time:
            alerts_up_to_time = len(dashboard.get_latest_alerts(1000, until_time=selected_time))
            st.metric(
                label="Alerts (up to selected time)",
                value=alerts_up_to_time,
                delta=None
            )
        else:
            st.metric(
                label="Total Alerts",
                value=dashboard.get_stream_length('alerts'),
                delta=None
            )
    
    with col3:
        # Show records up to selected time
        if selected_time:
            traffic_up_to_time = len(dashboard.get_latest_traffic(1000, until_time=selected_time))
            st.metric(
                label="Records (up to selected time)",
                value=traffic_up_to_time,
                delta=None
            )
        else:
            global_metrics = dashboard.get_global_metrics()
            st.metric(
                label="Processed Records",
                value=global_metrics.get('processed_records', 0),
                delta=None
            )
    
    with col4:
        st.metric(
            label="Unique IPs",
            value=len(dashboard.ip_stats),
            delta=None
        )
    
    # Charts section
    st.markdown("---")
    
    # Create tabs for different visualizations
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Alert Timeline", "🔥 IP Heatmap", "📈 Traffic Volume", "📋 Recent Alerts"])
    
    with tab1:
        st.plotly_chart(
            create_alert_timeline_chart(list(dashboard.alert_history)),
            use_container_width=True
        )
    
    with tab2:
        st.plotly_chart(
            create_ip_heatmap(list(dashboard.alert_history)),
            use_container_width=True
        )
    
    with tab3:
        st.plotly_chart(
            create_traffic_volume_chart(list(dashboard.traffic_history)),
            use_container_width=True
        )
    
    with tab4:
        # Recent alerts table
        if dashboard.alert_history:
            recent_alerts = list(dashboard.alert_history)[-20:]  # Last 20 alerts
            alert_df = pd.DataFrame(recent_alerts)
            
            # Format the dataframe for display
            display_df = alert_df[['timestamp', 'alert_type', 'source_ip', 'severity', 'confidence']].copy()
            display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%H:%M:%S')
            
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No alerts to display")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
