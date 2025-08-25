#!/usr/bin/env python3
"""
Stream Consumer for DDoS Detection Pipeline

This script processes network traffic data from Redis streams and implements
multi-layered DDoS detection algorithms.

Usage:
    python stream_consumer.py [--consumer-group mygroup] [--stream network_traffic]
"""

import redis
import json
import time
import argparse
from datetime import datetime, timedelta
import sys
from collections import defaultdict, deque
import statistics  # Built into Python 3.4+

class DDoSDetector:
    def __init__(self, redis_host='localhost', redis_port=6379):
        """Initialize the DDoS detector with Redis connection."""
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.stream_name = 'network_traffic'
        self.alerts_stream = 'alerts'
        self.metrics_stream = 'metrics'
        
        # Detection thresholds (lowered for testing)
        self.thresholds = {
            'high_request_rate': 5,     # requests per minute (lowered from 100)
            'port_scan_threshold': 3,   # different ports (lowered from 10)
            'new_ip_threshold': 2,      # requests per minute for new IPs (lowered from 50)
            'traffic_spike_multiplier': 10,  # 10x normal volume
            'baseline_window': 300,     # 5 minutes in seconds
            'sigma_threshold': 2.0      # standard deviations for anomaly
        }
        
        # Attack windows from dataset generation
        self.attack_windows = [
            (15, 25, "syn_flood"),
            (40, 50, "http_flood"), 
            (70, 80, "udp_flood"),
            (95, 105, "amplification")
        ]
        
        # State tracking
        self.processed_records = 0
        self.alerts_generated = 0
        self.start_time = time.time()
        
        # Baseline tracking
        self.baseline_data = deque(maxlen=300)  # 5 minutes of data
        self.ip_history = {}  # Track IPs we've seen
        
    def test_connection(self):
        """Test Redis connection."""
        try:
            self.redis_client.ping()
            print("✅ Redis connection successful")
            return True
        except redis.ConnectionError as e:
            print(f"❌ Redis connection failed: {e}")
            return False
    
    def parse_pandas_series_string(self, series_str):
        """Parse pandas Series string format into dictionary."""
        try:
            print(f"🔍 Parsing pandas series string: {series_str[:100]}...")
            
            # Split by newlines and extract key-value pairs
            lines = series_str.strip().split('\n')
            record = {}
            
            for line in lines:
                if 'Name:' in line or 'dtype:' in line:
                    continue  # Skip pandas metadata
                
                print(f"🔍 Processing line: '{line}'")
                
                # Find the first occurrence of multiple spaces (at least 2)
                import re
                match = re.match(r'^(\S+)\s{2,}(.*)$', line)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    print(f"  ✅ Matched: key='{key}', value='{value}'")
                    
                    # Handle NaN values
                    if value == 'NaN':
                        value = None
                    elif value == 'True':
                        value = True
                    elif value == 'False':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    elif value.replace('.', '').replace('-', '').isdigit():
                        value = float(value)
                    
                    record[key] = value
                else:
                    print(f"  ❌ No match for line: '{line}'")
            
            print(f"✅ Parsed record: {record}")
            return record
        except Exception as e:
            print(f"❌ Error parsing pandas series: {e}")
            return {}
    
    def extract_field(self, data_str, field_name):
        """Extract a specific field from pandas series string."""
        try:
            # Find the field in the string
            if field_name in data_str:
                # Look for the field followed by spaces and a value
                import re
                pattern = rf'{field_name}\s{{2,}}([^\n]+)'
                match = re.search(pattern, data_str)
                if match:
                    value = match.group(1).strip()
                    # Handle NaN values
                    if value == 'NaN':
                        return None
                    elif value == 'True':
                        return True
                    elif value == 'False':
                        return False
                    elif value.isdigit():
                        return int(value)
                    elif value.replace('.', '').replace('-', '').isdigit():
                        return float(value)
                    else:
                        return value
            return None
        except Exception as e:
            print(f"❌ Error extracting field {field_name}: {e}")
            return None
    
    def update_ip_counters(self, record):
        """Update per-IP counters and detect basic attacks."""
        source_ip = record.get('source_ip', '')
        dest_port = record.get('dest_port', '')
        
        # Convert dest_port to int if it's a string
        if isinstance(dest_port, str) and dest_port.isdigit():
            dest_port = int(dest_port)
        
        if not source_ip or source_ip == 'nan':
            return None
        
        # Update request count
        count_key = f"ip:{source_ip}:count"
        current_count = self.redis_client.incr(count_key)
        self.redis_client.expire(count_key, 60)  # 1-minute TTL
        
        # Update ports accessed
        ports_key = f"ip:{source_ip}:ports"
        ports_data = self.redis_client.get(ports_key)
        if ports_data:
            ports = json.loads(ports_data)
        else:
            ports = []
        
        if dest_port not in ports:
            ports.append(dest_port)
            self.redis_client.setex(ports_key, 60, json.dumps(ports))
        
        # Track first seen time
        first_seen_key = f"ip:{source_ip}:first_seen"
        if not self.redis_client.exists(first_seen_key):
            self.redis_client.setex(first_seen_key, 3600, str(time.time()))
        
        return {
            'ip': source_ip,
            'count': current_count,
            'ports': ports,
            'is_new_ip': source_ip not in self.ip_history
        }
    
    def detect_layer1_attacks(self, ip_data, record):
        """Layer 1: Fixed threshold detection."""
        alerts = []
        
        if not ip_data:
            return alerts
        
        # High request rate detection
        if ip_data['count'] > self.thresholds['high_request_rate']:
            alerts.append({
                'type': 'HIGH_REQUEST_RATE',
                'severity': 'HIGH',
                'source_ip': ip_data['ip'],
                'metric': ip_data['count'],
                'threshold': self.thresholds['high_request_rate'],
                'confidence': 0.9
            })
        
        # Port scanning detection
        if len(ip_data['ports']) > self.thresholds['port_scan_threshold']:
            alerts.append({
                'type': 'PORT_SCAN',
                'severity': 'MEDIUM',
                'source_ip': ip_data['ip'],
                'metric': len(ip_data['ports']),
                'threshold': self.thresholds['port_scan_threshold'],
                'confidence': 0.8
            })
        
        # New IP with high activity
        if ip_data['is_new_ip'] and ip_data['count'] > self.thresholds['new_ip_threshold']:
            alerts.append({
                'type': 'NEW_IP_ATTACK',
                'severity': 'HIGH',
                'source_ip': ip_data['ip'],
                'metric': ip_data['count'],
                'threshold': self.thresholds['new_ip_threshold'],
                'confidence': 0.85
            })
        
        return alerts
    
    def update_baseline(self, record):
        """Update baseline statistics for adaptive detection."""
        # Add current request rate to baseline
        current_time = time.time()
        self.baseline_data.append({
            'timestamp': current_time,
            'requests_per_minute': 1  # This will be aggregated
        })
        
        # Clean old data
        cutoff_time = current_time - self.thresholds['baseline_window']
        while self.baseline_data and self.baseline_data[0]['timestamp'] < cutoff_time:
            self.baseline_data.popleft()
    
    def detect_layer2_anomalies(self, ip_data, record):
        """Layer 2: Adaptive baseline detection."""
        alerts = []
        
        if len(self.baseline_data) < 10:  # Need minimum data for baseline
            return alerts
        
        # Calculate baseline statistics
        request_rates = [d['requests_per_minute'] for d in self.baseline_data]
        baseline_avg = statistics.mean(request_rates)
        baseline_std = statistics.stdev(request_rates) if len(request_rates) > 1 else 0
        
        # Store baseline in Redis for dashboard
        self.redis_client.setex('global:baseline:avg', 300, str(baseline_avg))
        self.redis_client.setex('global:baseline:std', 300, str(baseline_std))
        
        if ip_data and baseline_std > 0:
            current_rate = ip_data['count']
            threshold = baseline_avg + (self.thresholds['sigma_threshold'] * baseline_std)
            
            if current_rate > threshold:
                alerts.append({
                    'type': 'ANOMALOUS_TRAFFIC',
                    'severity': 'MEDIUM',
                    'source_ip': ip_data['ip'],
                    'metric': current_rate,
                    'baseline_avg': baseline_avg,
                    'baseline_std': baseline_std,
                    'threshold': threshold,
                    'confidence': 0.7
                })
        
        return alerts
    
    def detect_layer3_patterns(self, record):
        """Layer 3: Pattern-based attack detection."""
        alerts = []
        
        # SYN Flood detection
        packet_size = record.get('packet_size', 0)
        if isinstance(packet_size, str):
            if packet_size.isdigit():
                packet_size = int(packet_size)
            else:
                packet_size = 0  # Default if not a valid number
        elif packet_size is None:
            packet_size = 0
            
        if (record.get('protocol') == 'TCP' and 
            record.get('flags') == 'SYN' and
            record.get('response_time_ms') is None and
            packet_size < 100):
            
            alerts.append({
                'type': 'SYN_FLOOD_SUSPECT',
                'severity': 'MEDIUM',
                'source_ip': record.get('source_ip'),
                'dest_ip': record.get('dest_ip'),
                'protocol': 'TCP',
                'confidence': 0.6
            })
        
        # HTTP Flood detection
        dest_port = record.get('dest_port')
        if isinstance(dest_port, str) and dest_port.isdigit():
            dest_port = int(dest_port)
            
        if (dest_port in [80, 443, 8080] and
            record.get('http_method') in ['GET', 'POST']):
            
            alerts.append({
                'type': 'HTTP_FLOOD_SUSPECT',
                'severity': 'MEDIUM',
                'source_ip': record.get('source_ip'),
                'dest_port': record.get('dest_port'),
                'http_method': record.get('http_method'),
                'confidence': 0.5
            })
        
        # UDP Amplification detection
        packet_size = record.get('packet_size', 0)
        if isinstance(packet_size, str):
            if packet_size.isdigit():
                packet_size = int(packet_size)
            else:
                packet_size = 0  # Default if not a valid number
        elif packet_size is None:
            packet_size = 0
            
        if (record.get('protocol') == 'UDP' and
            packet_size > 2000):
            
            alerts.append({
                'type': 'UDP_AMPLIFICATION_SUSPECT',
                'severity': 'HIGH',
                'source_ip': record.get('source_ip'),
                'dest_ip': record.get('dest_ip'),
                'packet_size': record.get('packet_size'),
                'confidence': 0.8
            })
        
        return alerts
    
    def correlate_with_known_attacks(self, record):
        """Layer 4: Correlation with known attack patterns."""
        alerts = []
        
        # Extract minute from timestamp
        try:
            timestamp = datetime.fromisoformat(record.get('timestamp', ''))
            current_minute = timestamp.hour * 60 + timestamp.minute
        except:
            return alerts
        
        # Check if we're in a known attack window
        for start, end, attack_type in self.attack_windows:
            if start <= current_minute < end:
                alerts.append({
                    'type': f'KNOWN_{attack_type.upper()}',
                    'severity': 'HIGH',
                    'source_ip': record.get('source_ip'),
                    'attack_type': attack_type,
                    'window': f'{start}-{end}',
                    'confidence': 0.95
                })
                break
        
        return alerts
    
    def generate_alert(self, alert_data, record):
        """Generate and store alert."""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'alert_type': alert_data['type'],
            'severity': alert_data['severity'],
            'source_ip': alert_data.get('source_ip', record.get('source_ip')),
            'dest_ip': record.get('dest_ip'),
            'protocol': record.get('protocol'),
            'metrics': alert_data,
            'confidence': alert_data.get('confidence', 0.5),
            'record_data': {
                'timestamp': record.get('timestamp'),
                'source_port': record.get('source_port'),
                'dest_port': record.get('dest_port'),
                'packet_size': record.get('packet_size')
            }
        }
        
        # Store alert in Redis stream (convert to JSON)
        alert_json = json.dumps(alert, default=str)
        self.redis_client.xadd(self.alerts_stream, {'alert': alert_json})
        
        # Update alert counter
        self.alerts_generated += 1
        self.redis_client.incr('global:alerts:total')
        
        # Print alert to console
        print(f"🚨 ALERT: {alert['alert_type']} from {alert['source_ip']} "
              f"(Confidence: {alert['confidence']:.2f})")
        
        return alert
    
    def process_record(self, record):
        """Process a single network traffic record."""
        try:
            # Parse record data - handle pandas Series string format
            if isinstance(record, str):
                # Remove surrounding quotes if present
                if record.startswith('"') and record.endswith('"'):
                    record = record[1:-1]
                
                # Try to parse as JSON first
                try:
                    record = json.loads(record)
                except json.JSONDecodeError:
                    # If it's a pandas Series string, extract key-value pairs
                    record = self.parse_pandas_series_string(record)
            
            # Update IP counters and get IP data
            ip_data = self.update_ip_counters(record)
            
            # Update baseline
            self.update_baseline(record)
            
            # Run all detection layers
            alerts = []
            
            # Layer 1: Fixed thresholds
            alerts.extend(self.detect_layer1_attacks(ip_data, record))
            
            # Layer 2: Adaptive baseline
            alerts.extend(self.detect_layer2_anomalies(ip_data, record))
            
            # Layer 3: Pattern detection
            alerts.extend(self.detect_layer3_patterns(record))
            
            # Layer 4: Correlation analysis
            alerts.extend(self.correlate_with_known_attacks(record))
            
            # Generate alerts
            for alert_data in alerts:
                self.generate_alert(alert_data, record)
            
            # Update IP history
            if ip_data:
                self.ip_history[ip_data['ip']] = time.time()
            
            # Update metrics
            self.processed_records += 1
            self.redis_client.set('global:processed_records', self.processed_records)
            
        except Exception as e:
            print(f"❌ Error processing record: {e}")
    
    def consume_stream(self, consumer_group=None, block_time=1000, timeout_seconds=None):
        """Consume records from Redis stream."""
        print(f"🔄 Starting stream consumption from '{self.stream_name}'")
        if timeout_seconds:
            print(f"⏱️  Will run for {timeout_seconds} seconds")
        print("=" * 60)
        
        last_id = '0'  # Start from beginning
        start_time = time.time()
        
        while True:
            # Check timeout
            if timeout_seconds and (time.time() - start_time) > timeout_seconds:
                print(f"⏰ Timeout reached ({timeout_seconds} seconds)")
                break
            try:
                # Read from stream
                messages = self.redis_client.xread(
                    {self.stream_name: last_id},
                    count=10,
                    block=block_time
                )
                
                if not messages:
                    continue
                
                # Process messages
                for stream, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        # Extract record data - use the individual fields from Redis
                        record = {
                            'timestamp': fields.get('timestamp', ''),
                            'source_ip': fields.get('source_ip', ''),
                            'dest_ip': fields.get('dest_ip', ''),
                            'protocol': fields.get('protocol', ''),
                            'is_attack': fields.get('is_attack', 'False') == 'True'
                        }
                        
                        # Try to parse additional data from the data field
                        data_field = fields.get('data', '{}')
                        if isinstance(data_field, str) and data_field.startswith('"'):
                            # Extract key fields from pandas series string
                            if 'source_port' in data_field:
                                record['source_port'] = self.extract_field(data_field, 'source_port')
                            if 'dest_port' in data_field:
                                record['dest_port'] = self.extract_field(data_field, 'dest_port')
                            if 'packet_size' in data_field:
                                record['packet_size'] = self.extract_field(data_field, 'packet_size')
                            if 'flags' in data_field:
                                record['flags'] = self.extract_field(data_field, 'flags')
                            if 'response_time_ms' in data_field:
                                record['response_time_ms'] = self.extract_field(data_field, 'response_time_ms')
                            if 'http_method' in data_field:
                                record['http_method'] = self.extract_field(data_field, 'http_method')
                        
                        self.process_record(record)
                        
                        # Update last processed ID
                        last_id = message_id
                
                # Print periodic stats
                if self.processed_records % 100 == 0 and self.processed_records > 0:
                    elapsed = time.time() - self.start_time
                    rate = self.processed_records / elapsed
                    print(f"📊 Processed {self.processed_records} records, "
                          f"{self.alerts_generated} alerts, "
                          f"Rate: {rate:.2f} records/sec")
                
            except KeyboardInterrupt:
                print("\n🛑 Consumer stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in stream consumption: {e}")
                time.sleep(1)  # Brief pause before retry
    
    def print_summary(self):
        """Print processing summary."""
        elapsed = time.time() - self.start_time
        rate = self.processed_records / elapsed if elapsed > 0 else 0
        
        print("=" * 60)
        print("📈 CONSUMER SUMMARY")
        print("=" * 60)
        print(f"📤 Records processed: {self.processed_records}")
        print(f"🚨 Alerts generated: {self.alerts_generated}")
        print(f"⏱️  Total time: {elapsed:.2f} seconds")
        print(f"🚀 Processing rate: {rate:.2f} records/second")
        print(f"📊 Alert rate: {self.alerts_generated / elapsed:.2f} alerts/second")
        print("=" * 60)

def main():
    """Main function to run the stream consumer."""
    parser = argparse.ArgumentParser(description='Stream Consumer for DDoS Detection')
    parser.add_argument('--redis-host', type=str, default='localhost',
                       help='Redis host (default: localhost)')
    parser.add_argument('--redis-port', type=int, default=6379,
                       help='Redis port (default: 6379)')
    parser.add_argument('--stream', type=str, default='network_traffic',
                       help='Redis stream name (default: network_traffic)')
    parser.add_argument('--consumer-group', type=str, default=None,
                       help='Consumer group name (optional)')
    parser.add_argument('--block-time', type=int, default=1000,
                       help='Block time in milliseconds (default: 1000)')
    parser.add_argument('--timeout', type=int, default=None,
                       help='Timeout in seconds (default: run indefinitely)')
    
    args = parser.parse_args()
    
    print("🚀 Starting Stream Consumer for DDoS Detection")
    print("=" * 60)
    print(f"🔗 Redis: {args.redis_host}:{args.redis_port}")
    print(f"📡 Stream: {args.stream}")
    print(f"⏱️  Block time: {args.block_time}ms")
    print("=" * 60)
    
    # Initialize detector
    detector = DDoSDetector(
        redis_host=args.redis_host,
        redis_port=args.redis_port
    )
    
    # Test Redis connection
    if not detector.test_connection():
        print("❌ Cannot proceed without Redis connection")
        sys.exit(1)
    
    # Start consuming
    try:
        detector.consume_stream(
            consumer_group=args.consumer_group,
            block_time=args.block_time,
            timeout_seconds=args.timeout
        )
    except KeyboardInterrupt:
        print("\n🛑 Consumer stopped by user")
    finally:
        detector.print_summary()

if __name__ == "__main__":
    main()
