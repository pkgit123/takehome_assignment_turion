# Streaming Analysis Setup

This directory contains the streaming analysis components for the DDoS detection pipeline.

## Architecture Overview

```
CSV File → Producer → Redis → Consumer → Streamlit Dashboard
```

### Components:
1. **Redis Server** (Docker) - Message broker for real-time data
2. **Producer** - Reads CSV and sends records to Redis
3. **Consumer** - Processes real-time data and detects attacks
4. **Streamlit Dashboard** - Visualizes real-time analytics

## Quick Start

### 1. Start Docker Desktop
Before starting the Redis server, ensure Docker Desktop is running:

```bash
# Start Docker Desktop (macOS)
open -a Docker

# Wait for Docker to fully start (check system tray/status)
# You can verify Docker is running with:
docker --version
```

### 1.5. Install Dependencies (Important!)
Before running any components, ensure all dependencies are installed:

```bash
# Navigate to the analysis_stream directory
cd turion_takehome_v2/analysis_stream

# Install all required packages
pip install -r requirements.txt
```

### 2. Start Redis Server
```bash
# Make sure you're in the correct directory
cd turion_takehome_v2/analysis_stream
docker-compose up -d
```

This will start:
- Redis server on port 6379
- Redis Commander (web UI) on port 8081

### 2. Verify Redis is Running
```bash
# Check if containers are running
docker-compose ps

# Test Redis connection
docker exec ddos_redis redis-cli ping
# Should return: PONG
```

### 3. Access Redis Commander (Optional)
Open http://localhost:8081 in your browser to view Redis data in real-time.

## Development Workflow

### Terminal 1: Start Redis Infrastructure
```bash
# Make sure you're in the correct directory
cd turion_takehome_v2/analysis_stream
docker-compose up -d
```

### Terminal 2: Start Consumer (Real-time Detection)
```bash
# Make sure you're in the correct directory
cd turion_takehome_v2/analysis_stream

# Run for 2 minutes (120 seconds)
python stream_consumer.py --timeout 120
```

### Terminal 3: Start Producer (Data Ingestion)
```bash
# Make sure you're in the correct directory
cd turion_takehome_v2/analysis_stream

# Send 1000 records with 0.1 second delay (no timeout option available)
python stream_producer.py --csv-path ../dataset/network_traffic.csv --records 1000 --delay 0.1
```

### Terminal 4: Start Streamlit Dashboard (Real-time Visualization)
```bash
# Make sure you're in the correct directory
cd turion_takehome_v2/analysis_stream

# Install/update dependencies first
pip install -r requirements.txt

# Start Streamlit dashboard
streamlit run stream_dashboard.py --server.port 8501
```

**Troubleshooting Streamlit Issues:**
- If you get `ModuleNotFoundError: No module named 'streamlit.cli'`, run: `pip install -r requirements.txt`
- If Streamlit won't start, try: `python -m streamlit run stream_dashboard.py --server.port 8501`
- Ensure you're in the `analysis_stream` directory when running commands

## 🔄 Workflow Order & Timing

### **Why This Order Matters:**
1. **Redis First**: All components depend on Redis infrastructure
2. **Consumer Second**: Ensures no data is lost, ready to process immediately
3. **Producer Third**: Data begins flowing to already-listening consumer
4. **Dashboard Last**: Visualizes real-time data already flowing in Redis

### **Recommended Demo Sequence:**
1. **Start Redis** → Wait 5 seconds for startup
2. **Start Consumer** → Wait 10 seconds for initialization  
3. **Start Producer** → Data begins flowing immediately
4. **Start Dashboard** → See real-time visualization

### **Data Flow Architecture:**
```
CSV Data → Producer → Redis Streams → Consumer → Alerts
                                    ↓
                              Dashboard ← Redis Data
```

## ⏱️ Testing Timeframes

### Quick Demo (2 minutes)
- **Consumer**: `--timeout 120`
- **Producer**: `--records 1000 --delay 0.1` (no timeout option)
- **Result**: ~1000 records processed, quick demonstration

### Standard Demo (5 minutes)
- **Consumer**: `--timeout 300`
- **Producer**: `--records 2500 --delay 0.1` (no timeout option)
- **Result**: ~2500 records processed, good coverage

### Full Dataset (Not recommended for demo)
- **Consumer**: `--timeout 7200` (2 hours)
- **Producer**: `--records 800000 --delay 0.1` (no timeout option)
- **Result**: ~800K records processed, production-like load

### Terminal 5: Cleanup Redis Data (After Testing)
```bash
# Clear all Redis data to start fresh
docker exec ddos_redis redis-cli flushall

# Or stop and remove containers completely
docker-compose down -v
```

## Redis Data Structure

### Streams
- `network_traffic` - Raw network events
- `alerts` - DDoS attack alerts
- `metrics` - Real-time metrics

### Key-Value Stores
- `ip_request_counts` - Sliding window counts per IP
- `attack_patterns` - Detected attack patterns
- `system_metrics` - Overall system statistics

## Configuration

### Redis Connection
- Host: localhost
- Port: 6379
- No authentication required (development setup)

### Performance Tuning
- Adjust CSV reading rate in producer
- Configure sliding window sizes in consumer
- Set alert thresholds for different attack types

## Monitoring

### Redis Commander
- Web interface at http://localhost:8081
- View streams, keys, and data in real-time
- Monitor memory usage and performance

### Logs
```bash
# View Redis logs
docker-compose logs redis

# View all service logs
docker-compose logs -f
```

## Troubleshooting

### Common Issues and Solutions

#### Streamlit Issues
- **Error**: `ModuleNotFoundError: No module named 'streamlit.cli'`
  - **Solution**: Run `pip install -r requirements.txt` to fix version conflicts
  
- **Error**: Streamlit won't start or shows blank page
  - **Solution**: Try `python -m streamlit run stream_dashboard.py --server.port 8501`
  
- **Error**: Dashboard shows no data
  - **Solution**: Ensure producer and consumer are running, check Redis data with `docker exec ddos_redis redis-cli xlen network_traffic`

#### Directory Issues
- **Error**: `File does not exist: stream_dashboard.py`
  - **Solution**: Ensure you're in the `turion_takehome_v2/analysis_stream` directory
  
- **Error**: `No such file or directory: stream_consumer.py`
  - **Solution**: Run `cd turion_takehome_v2/analysis_stream` before executing commands

#### Redis Issues
- **Error**: `Cannot connect to the Docker daemon`
  - **Solution**: Start Docker Desktop first with `open -a Docker`
  
- **Error**: Redis connection failed
  - **Solution**: Check if containers are running with `docker-compose ps`

#### Data Flow Issues
- **Problem**: No alerts being generated
  - **Solution**: Ensure consumer is running before starting producer
- **Problem**: Dashboard shows old data
  - **Solution**: Clear Redis data with `docker exec ddos_redis redis-cli flushall`

### Verification Steps
After each step, verify the component is working:

1. **Docker**: `docker --version` should return version info
2. **Redis**: `docker exec ddos_redis redis-cli ping` should return `PONG`
3. **Producer**: Should show progress messages like "📤 Sent 100 records to Redis"
4. **Consumer**: Should show alert messages like "🚨 DDoS Alert detected"
5. **Dashboard**: Should be accessible at http://localhost:8501

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (will delete all data)
docker-compose down -v
```

## Next Steps

1. ✅ Producer script (`stream_producer.py`) - Reads CSV and sends to Redis
2. ✅ Consumer script (`stream_consumer.py`) - Real-time DDoS detection
3. ✅ Streamlit dashboard (`stream_dashboard.py`) - Real-time visualization
4. ✅ DDoS detection algorithms implemented
5. Add alerting and notification systems
