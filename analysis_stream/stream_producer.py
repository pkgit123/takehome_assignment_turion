#!/usr/bin/env python3
"""
Stream Producer for DDoS Detection Pipeline

This script reads network traffic data from CSV and sends it to Redis
for real-time processing by the consumer.

Usage:
    python stream_producer.py [--records 100] [--delay 0.1] [--csv-path ../dataset/network_traffic.csv]
"""

import pandas as pd
import redis
import json
import time
import argparse
from datetime import datetime
import sys
from pathlib import Path

class StreamProducer:
    def __init__(self, redis_host='localhost', redis_port=6379, stream_name='network_traffic'):
        """Initialize the stream producer."""
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.stream_name = stream_name
        self.records_sent = 0
        
    def test_connection(self):
        """Test Redis connection."""
        try:
            self.redis_client.ping()
            print("✅ Redis connection successful")
            return True
        except redis.ConnectionError as e:
            print(f"❌ Redis connection failed: {e}")
            return False
    
    def send_record(self, record):
        """Send a single record to Redis stream."""
        try:
            # Convert record to JSON string
            record_json = json.dumps(record, default=str)
            
            # Add timestamp if not present
            if 'timestamp' not in record or pd.isna(record['timestamp']):
                record['timestamp'] = datetime.now().isoformat()
            
            # Send to Redis stream
            stream_id = self.redis_client.xadd(
                self.stream_name,
                {
                    'data': record_json,
                    'timestamp': record['timestamp'],
                    'source_ip': str(record.get('source_ip', '')),
                    'dest_ip': str(record.get('dest_ip', '')),
                    'protocol': str(record.get('protocol', '')),
                    'is_attack': str(record.get('is_attack', False))
                }
            )
            
            self.records_sent += 1
            return stream_id
            
        except Exception as e:
            print(f"❌ Error sending record: {e}")
            return None
    
    def process_csv(self, csv_path, max_records=None, delay=0.1):
        """Process CSV file and send records to Redis."""
        try:
            print(f"📖 Reading CSV file: {csv_path}")
            
            # Read CSV in chunks to handle large files efficiently
            chunk_size = 1000
            records_processed = 0
            
            for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
                print(f"🔄 Processing chunk with {len(chunk)} records...")
                
                for _, record in chunk.iterrows():
                    # Check if we've reached the limit
                    if max_records and records_processed >= max_records:
                        print(f"✅ Reached limit of {max_records} records")
                        return
                    
                    # Send record to Redis
                    stream_id = self.send_record(record)
                    if stream_id:
                        records_processed += 1
                        
                        # Print progress every 100 records
                        if records_processed % 100 == 0:
                            print(f"📤 Sent {records_processed} records to Redis")
                    
                    # Add delay to simulate real-time processing
                    if delay > 0:
                        time.sleep(delay)
                
                print(f"📊 Chunk processed. Total records sent: {records_processed}")
            
            print(f"✅ Finished processing. Total records sent: {records_processed}")
            
        except FileNotFoundError:
            print(f"❌ CSV file not found: {csv_path}")
        except Exception as e:
            print(f"❌ Error processing CSV: {e}")

def main():
    """Main function to run the stream producer."""
    parser = argparse.ArgumentParser(description='Stream Producer for DDoS Detection')
    parser.add_argument('--records', type=int, default=100, 
                       help='Maximum number of records to process (default: 100)')
    parser.add_argument('--delay', type=float, default=0.1,
                       help='Delay between records in seconds (default: 0.1)')
    parser.add_argument('--csv-path', type=str, 
                       default='../dataset/network_traffic.csv',
                       help='Path to CSV file (default: ../dataset/network_traffic.csv)')
    parser.add_argument('--redis-host', type=str, default='localhost',
                       help='Redis host (default: localhost)')
    parser.add_argument('--redis-port', type=int, default=6379,
                       help='Redis port (default: 6379)')
    
    args = parser.parse_args()
    
    print("🚀 Starting Stream Producer for DDoS Detection")
    print("=" * 60)
    print(f"📁 CSV Path: {args.csv_path}")
    print(f"📊 Max Records: {args.records}")
    print(f"⏱️  Delay: {args.delay}s")
    print(f"🔗 Redis: {args.redis_host}:{args.redis_port}")
    print("=" * 60)
    
    # Check if CSV file exists
    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        print("💡 Make sure you're running from the analysis_stream directory")
        print("💡 The CSV file should be in ../dataset/network_traffic.csv")
        sys.exit(1)
    
    # Initialize producer
    producer = StreamProducer(
        redis_host=args.redis_host,
        redis_port=args.redis_port
    )
    
    # Test Redis connection
    if not producer.test_connection():
        print("❌ Cannot proceed without Redis connection")
        sys.exit(1)
    
    # Process CSV
    start_time = time.time()
    producer.process_csv(
        csv_path=args.csv_path,
        max_records=args.records,
        delay=args.delay
    )
    end_time = time.time()
    
    # Print summary
    print("=" * 60)
    print("📈 PRODUCER SUMMARY")
    print("=" * 60)
    print(f"📤 Records sent: {producer.records_sent}")
    print(f"⏱️  Total time: {end_time - start_time:.2f} seconds")
    if producer.records_sent > 0:
        print(f"🚀 Rate: {producer.records_sent / (end_time - start_time):.2f} records/second")
    print("=" * 60)

if __name__ == "__main__":
    main()

