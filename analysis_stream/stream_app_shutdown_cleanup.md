# Streaming Application Shutdown and Cleanup Guide

## Overview
This document provides step-by-step instructions for properly shutting down all components of the streaming application to ensure clean resource management and prevent orphaned processes.

## 🛑 Shutdown Order
Follow these steps in order to ensure all components are properly terminated:

### **Step 1: Stop Streamlit Dashboard**
```bash
# Check if Streamlit is running
ps aux | grep streamlit | grep -v grep

# If running, kill the process (replace PID with actual process ID)
kill <PID>

# Alternative: Kill all Streamlit processes
pkill -f streamlit
```

### **Step 2: Stop Producer and Consumer Applications**
```bash
# Check for running Python streaming processes
ps aux | grep python | grep -E "(stream|consumer|producer)" | grep -v grep

# Kill any running streaming processes
pkill -f "stream_producer.py"
pkill -f "stream_consumer.py"
```

### **Step 3: Stop Docker Services**
```bash
# Navigate to the analysis_stream directory
cd /path/to/turion_takehome_v2/analysis_stream

# Check running Docker containers
docker-compose ps

# Stop and remove all containers
docker-compose down

# Verify containers are stopped
docker ps
```

### **Step 4: Verify Complete Cleanup**
```bash
# Check for any remaining Python processes
ps aux | grep python | grep -E "(stream|consumer|producer)" | grep -v grep

# Check for any remaining Docker containers
docker ps

# Check for any remaining Redis processes
ps aux | grep redis | grep -v grep
```

## 🔍 Verification Commands

### **Check Running Processes**
```bash
# Check Streamlit processes
ps aux | grep streamlit | grep -v grep

# Check Python streaming processes
ps aux | grep python | grep -E "(stream|consumer|producer)" | grep -v grep

# Check Redis processes
ps aux | grep redis | grep -v grep
```

### **Check Docker Status**
```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# Check Docker Compose services
docker-compose ps
```

### **Check Network Ports**
```bash
# Check if ports are still in use
lsof -i :8501  # Streamlit
lsof -i :6379  # Redis
lsof -i :8081  # Redis Commander
```

## 🚨 Troubleshooting

### **If Streamlit Won't Stop**
```bash
# Force kill Streamlit process
pkill -9 -f streamlit

# Or kill by port
lsof -ti:8501 | xargs kill -9
```

### **If Docker Containers Won't Stop**
```bash
# Force stop all containers
docker stop $(docker ps -q)

# Remove all containers
docker rm $(docker ps -aq)

# Remove all networks
docker network prune -f
```

### **If Redis Data Persists**
```bash
# Clear Redis data (if needed)
docker exec ddos_redis redis-cli flushall

# Or remove Redis volume
docker volume rm analysis_stream_redis_data
```

## 📋 Cleanup Checklist

### **✅ Pre-Shutdown Verification**
- [ ] Note any running process IDs
- [ ] Check current data in Redis (if needed)
- [ ] Save any important logs or outputs

### **✅ Component Shutdown**
- [ ] Streamlit dashboard stopped
- [ ] Producer application stopped
- [ ] Consumer application stopped
- [ ] Redis server stopped
- [ ] Redis Commander stopped

### **✅ Resource Cleanup**
- [ ] Docker containers removed
- [ ] Docker networks cleaned up
- [ ] No orphaned processes
- [ ] Ports freed up

### **✅ Final Verification**
- [ ] No Python streaming processes running
- [ ] No Docker containers running
- [ ] No Redis processes running
- [ ] All ports available

## 🎯 Quick Shutdown Script

For convenience, you can create a quick shutdown script:

```bash
#!/bin/bash
# quick_shutdown.sh

echo "🛑 Shutting down streaming application..."

# Kill Streamlit
echo "📊 Stopping Streamlit..."
pkill -f streamlit

# Kill streaming processes
echo "🔄 Stopping producer/consumer..."
pkill -f "stream_producer.py"
pkill -f "stream_consumer.py"

# Stop Docker services
echo "🐳 Stopping Docker services..."
cd /path/to/turion_takehome_v2/analysis_stream
docker-compose down

# Verify cleanup
echo "🔍 Verifying cleanup..."
ps aux | grep -E "(streamlit|python.*stream|redis)" | grep -v grep || echo "✅ No streaming processes found"
docker ps || echo "✅ No Docker containers running"

echo "✅ Shutdown complete!"
```

## 📝 Important Notes

### **Data Persistence**
- Redis data is typically lost when containers are stopped
- If you need to preserve data, consider using Docker volumes
- The streaming application is designed for real-time processing, not data persistence

### **Port Conflicts**
- If ports remain in use after shutdown, check for other applications
- Common ports: 8501 (Streamlit), 6379 (Redis), 8081 (Redis Commander)

### **Resource Usage**
- Monitor system resources during shutdown
- Large datasets may take time to process during shutdown
- Consider graceful shutdown for production environments

## 🔄 Restart Instructions

After shutdown, you can restart the application using the instructions in `README.md`:

1. Start Docker services: `docker-compose up -d`
2. Start consumer: `python stream_consumer.py`
3. Start producer: `python stream_producer.py`
4. Start Streamlit: `streamlit run stream_dashboard.py --server.port 8501`

## 📚 Related Documentation

- [`README.md`](README.md) - Main setup and startup instructions
- [`test_redis_setup.md`](test_redis_setup.md) - Redis infrastructure testing
- [`requirements.txt`](requirements.txt) - Python dependencies

---

**Last Updated:** $(date)
**Version:** 1.0

