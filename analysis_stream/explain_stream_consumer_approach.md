# Stream Consumer Approach: DDoS Detection Strategy

## Overview
This document explains the multi-layered approach for real-time DDoS detection in our streaming pipeline. The consumer processes network traffic data from Redis streams and implements various detection algorithms to identify potential attacks.

## Architecture Context
```
CSV File → Producer → Redis Stream → Consumer → Alerts + Metrics
```

The consumer is the core analytics component that transforms raw network data into actionable security insights.

## Multi-Layered Detection Strategy

### Layer 1: Immediate Rate Limiting (Fixed Thresholds)
**Purpose**: Catch obvious, high-volume attacks quickly
**Implementation**: Simple counters with fixed thresholds

#### Detection Rules:
- **High Request Rate**: >100 requests/minute from single IP
- **Port Scanning**: Single IP accessing >10 different ports
- **Traffic Spike**: 10x normal volume in short time window
- **New IP Attack**: Previously unseen IP with >50 requests/minute

#### Advantages:
- ✅ Fast detection (minimal processing)
- ✅ Low false negatives for obvious attacks
- ✅ Simple to implement and debug

#### Limitations:
- ❌ May miss sophisticated attacks
- ❌ False positives during legitimate traffic spikes
- ❌ Doesn't adapt to changing traffic patterns

### Layer 2: Adaptive Baseline Detection
**Purpose**: Detect attacks that are abnormal relative to recent traffic patterns
**Implementation**: Rolling averages and statistical analysis

#### Baseline Establishment:
- **Time Window**: 5-minute rolling window
- **Metrics Tracked**: 
  - Average requests per IP per minute
  - Standard deviation of request rates
  - Protocol distribution
  - Geographic distribution

#### Detection Logic:
```python
# Adaptive threshold calculation
baseline_avg = rolling_average(requests_per_minute, window=5min)
baseline_std = rolling_std(requests_per_minute, window=5min)
threshold = baseline_avg + (2 * baseline_std)  # 2-sigma rule

if current_rate > threshold:
    trigger_alert("ANOMALOUS_TRAFFIC")
```

#### Advantages:
- ✅ Adapts to changing traffic patterns
- ✅ Reduces false positives during legitimate spikes
- ✅ Catches sophisticated attacks

#### Limitations:
- ❌ Requires time to establish baseline
- ❌ More complex to implement
- ❌ May miss attacks during baseline establishment

### Layer 3: Pattern-Based Detection
**Purpose**: Identify specific attack types based on behavioral patterns
**Implementation**: Rule-based pattern matching

#### Attack Pattern Detection:

##### SYN Flood Detection:
- **Pattern**: Many incomplete TCP connections
- **Indicators**: 
  - High ratio of SYN flags to completed connections
  - Low response times or no responses
  - Small packet sizes (40-60 bytes)

##### HTTP Flood Detection:
- **Pattern**: High volume of HTTP requests
- **Indicators**:
  - Requests to web ports (80, 443, 8080)
  - HTTP methods (GET, POST)
  - Consistent user agents or missing user agents

##### UDP Amplification Detection:
- **Pattern**: Small requests generating large responses
- **Indicators**:
  - Large response packets (2000-4000 bytes)
  - DNS or NTP protocols
  - Amplification ratio >10:1

##### Slowloris Detection:
- **Pattern**: Many incomplete HTTP connections
- **Indicators**:
  - Incomplete HTTP headers
  - Long-lived connections without completion
  - Gradual connection buildup

#### Advantages:
- ✅ Specific attack type identification
- ✅ Helps with incident response
- ✅ Enables targeted mitigation

#### Limitations:
- ❌ Requires deep packet inspection
- ❌ May miss novel attack patterns
- ❌ Higher computational cost

### Layer 4: Correlation Analysis
**Purpose**: Cross-reference current activity with known attack patterns
**Implementation**: Temporal and spatial correlation

#### Correlation Factors:
- **Temporal**: Match current time with known attack windows
- **Spatial**: Geographic clustering of attack sources
- **Behavioral**: Similar attack patterns across multiple IPs
- **Infrastructure**: Targeting specific services or ports

#### Implementation:
```python
# Cross-reference with dataset attack schedule
attack_windows = [
    (15, 25, "syn_flood"),
    (40, 50, "http_flood"), 
    (70, 80, "udp_flood"),
    (95, 105, "amplification")
]

def correlate_with_known_attacks(current_minute):
    for start, end, attack_type in attack_windows:
        if start <= current_minute < end:
            return attack_type
    return None
```

## Stateful Processing Implementation

### Redis-Based State Management
**Challenge**: Maintain per-IP counters and patterns across time windows
**Solution**: Redis key-value store with TTL for automatic cleanup

#### Data Structures:
```python
# Per-IP counters (1-minute TTL)
"ip:{ip}:count" -> request_count
"ip:{ip}:ports" -> json.dumps(ports_accessed)
"ip:{ip}:first_seen" -> timestamp

# Global metrics (5-minute TTL)
"global:baseline:avg" -> average_requests_per_minute
"global:baseline:std" -> standard_deviation
"global:attack_count" -> total_attacks_detected
```

#### Sliding Window Implementation:
```python
# Update counters with TTL
redis.incr(f"ip:{ip}:count")
redis.expire(f"ip:{ip}:count", 60)  # 1-minute TTL

# Track ports accessed
ports = json.loads(redis.get(f"ip:{ip}:ports") or "[]")
ports.append(port)
redis.setex(f"ip:{ip}:ports", 60, json.dumps(list(set(ports))))
```

### Memory Management
**Strategy**: Automatic cleanup using Redis TTL
- **1-minute data**: IP counters, port lists
- **5-minute data**: Baseline calculations
- **1-hour data**: IP reputation, attack history

## Alert Generation Strategy

### Alert Types:
1. **IMMEDIATE**: High-volume attacks requiring immediate response
2. **WARNING**: Suspicious activity requiring monitoring
3. **INFO**: Baseline deviations for trend analysis

### Alert Content:
```python
alert = {
    "timestamp": current_time,
    "alert_type": "DDoS_DETECTED",
    "severity": "HIGH",
    "source_ip": "192.168.1.1",
    "attack_type": "SYN_FLOOD",
    "metrics": {
        "requests_per_minute": 150,
        "ports_accessed": 15,
        "baseline_threshold": 100
    },
    "confidence": 0.95
}
```

### Alert Storage:
- **Redis Stream**: Real-time alerts for dashboard
- **Redis Hash**: Alert history for analysis
- **Console Output**: Immediate visibility during development

## Performance Considerations

### Processing Speed:
- **Target**: Process 1000+ records/second
- **Optimization**: Batch processing, efficient Redis operations
- **Monitoring**: Track processing latency and throughput

### Memory Usage:
- **Strategy**: TTL-based cleanup, limit stored data
- **Monitoring**: Track Redis memory usage
- **Scaling**: Horizontal scaling with multiple consumers

### Accuracy vs. Latency:
- **Trade-off**: More sophisticated detection vs. faster response
- **Strategy**: Layer 1 for immediate alerts, Layer 2+ for detailed analysis
- **Optimization**: Parallel processing where possible

## Integration Points

### Producer Integration:
- **Input**: Redis stream `network_traffic`
- **Format**: JSON records with metadata
- **Rate**: Configurable processing speed

### Dashboard Integration:
- **Output**: Redis stream `alerts`
- **Metrics**: Real-time counters and statistics
- **Visualization**: Attack patterns and trends

### External Systems:
- **Logging**: Structured logs for analysis
- **Monitoring**: Health checks and performance metrics
- **Alerting**: Integration with notification systems

## Testing Strategy

### Unit Testing:
- **Detection Algorithms**: Test each layer independently
- **State Management**: Verify Redis operations
- **Alert Generation**: Validate alert format and content

### Integration Testing:
- **End-to-End**: Producer → Consumer → Dashboard
- **Performance**: Load testing with realistic data volumes
- **Reliability**: Error handling and recovery

### Validation Testing:
- **Known Attacks**: Verify detection of dataset attack patterns
- **False Positives**: Test with normal traffic patterns
- **Edge Cases**: Handle missing data, malformed records

## Success Metrics

### Detection Accuracy:
- **True Positives**: Correctly identified attacks
- **False Positives**: Normal traffic flagged as attacks
- **False Negatives**: Missed attacks
- **Detection Time**: Time from attack start to alert

### Performance Metrics:
- **Throughput**: Records processed per second
- **Latency**: Time from record arrival to alert generation
- **Memory Usage**: Redis memory consumption
- **CPU Usage**: Processing overhead

### Operational Metrics:
- **Uptime**: Consumer availability
- **Error Rate**: Failed record processing
- **Alert Volume**: Number of alerts generated
- **Response Time**: Time to investigate and respond to alerts

## Future Enhancements

### Machine Learning Integration:
- **Feature Engineering**: Extract ML-ready features
- **Model Training**: Train on historical attack data
- **Real-time Scoring**: ML-based anomaly detection

### Advanced Analytics:
- **Attack Attribution**: Identify attack sources and motives
- **Trend Analysis**: Long-term attack pattern analysis
- **Predictive Analytics**: Forecast potential attacks

### Scalability Improvements:
- **Consumer Groups**: Multiple consumers for load balancing
- **Partitioning**: Shard data by IP ranges or time windows
- **Caching**: Optimize frequently accessed data

This multi-layered approach provides comprehensive DDoS detection while maintaining performance and scalability for production deployment.
