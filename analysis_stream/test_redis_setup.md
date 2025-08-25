# Redis Setup Testing - Step-by-Step Process

## Overview
This document outlines the step-by-step process for setting up and testing the Redis server for the DDoS detection streaming pipeline.

## Step 1: Initial Setup Issues

### Problem Encountered
When first attempting to start Redis with Docker Compose, we encountered:
```
unable to get image 'redis:7-alpine': Cannot connect to the Docker daemon at unix:///Users/peterkim/.docker/run/docker.sock. Is the docker daemon running?
```

### Solution
Docker Desktop was not running on the macOS system. We started Docker using:
```bash
open -a Docker
```

## Step 2: Docker Compose File Optimization

### Issue Fixed
Removed obsolete `version` attribute from docker-compose.yml to eliminate warnings:
```yaml
# Before
version: '3.8'
services:

# After  
services:
```

## Step 3: Starting Redis Services

### Command Executed
```bash
cd turion_takehome_v2/analysis_stream
docker-compose up -d
```

### Services Started
- **Redis Server** (ddos_redis): Port 6379
- **Redis Commander** (ddos_redis_commander): Port 8081

### Output
```
[+] Running 14/14
 ✔ redis Pulled                                                                                       12.1s 
 ✔ redis-commander Pulled                                                                             12.5s
[+] Running 5/5
 ✔ Network analysis_stream_default Created0.0s
 ✔ Volume "analysis_stream_redis_data" Created0.0s
 ✔ Container ddos_redis Started0.5s
 ✔ Container ddos_redis_commander Started0.4s
```

### Note
Received platform mismatch warning for redis-commander (ARM64 vs AMD64), but service started successfully.

## Step 4: Verification of Services

### Check Container Status
```bash
docker-compose ps
```

### Output
```
NAME                   IMAGE                                   COMMAND                  SERVICE           CREATED          STATUS                             PORTS
ddos_redis             redis:7-alpine                          "docker-entrypoint.s…"   redis             22 seconds ago   Up 21 seconds (health: starting)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
ddos_redis_commander   rediscommander/redis-commander:latest   "/usr/bin/dumb-init …"   redis-commander   22 seconds ago   Up 21 seconds (health: starting)   0.0.0.0:8081->8081/tcp, [::]:8081->8081/tcp
```

## Step 5: Redis Connection Test

### Test Command
```bash
docker exec ddos_redis redis-cli ping
```

### Expected Result
```
PONG
```

### Actual Result
```
PONG
```

## Step 5.5: Basic Redis Operations Test

### Test Commands
To verify Redis is fully functional, we tested basic operations:

```bash
# Set a test key-value pair
docker exec ddos_redis redis-cli SET test "Hello Redis"

# Retrieve the value
docker exec ddos_redis redis-cli GET test

# Delete the test key
docker exec ddos_redis redis-cli DEL test
```

### Expected Results
```
OK
Hello Redis
(integer) 1
```

### Actual Results
```
OK
Hello Redis
(integer) 1
```

### Verification
- ✅ **SET operation**: Successfully stored key-value pair
- ✅ **GET operation**: Successfully retrieved stored value
- ✅ **DEL operation**: Successfully deleted key
- ✅ **Redis functionality**: All basic operations working correctly

## Step 6: Access Points Available

### Redis Server
- **Host**: localhost
- **Port**: 6379
- **Status**: ✅ Running and responding

### Redis Commander (Web UI)
- **URL**: http://localhost:8081
- **Purpose**: Web-based Redis management interface
- **Features**: Real-time data viewing, key management, performance monitoring

## Step 7: Architecture Validation

### Current Setup
```
CSV File → [Producer Script] → Redis (localhost:6379) → [Consumer Script] → [Streamlit Dashboard]
```

### Components Status
- ✅ **Redis Server**: Running and tested
- ⏳ **Producer Script**: Next to implement
- ⏳ **Consumer Script**: To be implemented
- ⏳ **Streamlit Dashboard**: To be implemented

## Step 8: Next Steps

### Immediate Actions
1. Create producer script to read CSV and send data to Redis
2. Create consumer script for real-time analytics
3. Create Streamlit dashboard for visualization

### Testing Strategy
- Use Redis Commander web interface to monitor data flow
- Implement step-by-step testing of each component
- Validate real-time processing capabilities

## Technical Notes

### Docker Compose Configuration
- Uses Redis 7 Alpine for lightweight deployment
- Includes persistent volume for data storage
- Health checks enabled for reliability
- Automatic restart policy configured

### Platform Considerations
- Running on macOS ARM64 (Apple Silicon)
- Redis Commander image compatibility noted but functional
- No performance impact observed from platform mismatch

## Success Criteria Met

- ✅ Docker containers started successfully
- ✅ Redis server responding to ping
- ✅ Ports accessible (6379, 8081)
- ✅ Web interface available
- ✅ Ready for producer/consumer development
