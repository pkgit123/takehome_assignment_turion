#!/usr/bin/env python3
"""
Create Test Subset Script

This script extracts a smaller time window from the large network_traffic.csv
for realistic testing and demonstration purposes.

Usage:
    python create_test_subset.py --minutes 15 --start-time "2025-08-12T21:00:00"
"""

import pandas as pd
import argparse
from datetime import datetime, timedelta
import sys

def create_test_subset(input_file, output_file, start_time, minutes):
    """Create a subset of the dataset for testing."""
    print(f"📖 Reading large dataset: {input_file}")
    
    # Read the CSV file
    df = pd.read_csv(input_file)
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate time range
    start_dt = pd.to_datetime(start_time)
    end_dt = start_dt + timedelta(minutes=minutes)
    
    print(f"⏰ Extracting data from {start_dt} to {end_dt}")
    print(f"📊 Total records in dataset: {len(df):,}")
    
    # Filter data within the time window
    subset = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)]
    
    print(f"✅ Extracted {len(subset):,} records")
    print(f"📈 Data spans: {subset['timestamp'].min()} to {subset['timestamp'].max()}")
    
    # Save subset
    subset.to_csv(output_file, index=False)
    
    # Calculate statistics
    attack_records = subset[subset['is_attack'] == True]
    normal_records = subset[subset['is_attack'] == False]
    
    print(f"🚨 Attack records: {len(attack_records):,} ({len(attack_records)/len(subset)*100:.1f}%)")
    print(f"✅ Normal records: {len(normal_records):,} ({len(normal_records)/len(subset)*100:.1f}%)")
    
    # Show attack types
    if len(attack_records) > 0:
        print("\n🎯 Attack types in subset:")
        attack_counts = attack_records['attack_type'].value_counts()
        for attack_type, count in attack_counts.items():
            print(f"  - {attack_type}: {count:,} records")
    
    # Estimate processing time
    estimated_time = len(subset) / 25  # Based on our consumer rate
    print(f"\n⏱️  Estimated processing time: {estimated_time/60:.1f} minutes")
    
    return subset

def main():
    parser = argparse.ArgumentParser(description='Create test subset from network traffic data')
    parser.add_argument('--input', type=str, default='../dataset/network_traffic.csv',
                       help='Input CSV file (default: ../dataset/network_traffic.csv)')
    parser.add_argument('--output', type=str, default='test_subset.csv',
                       help='Output CSV file (default: test_subset.csv)')
    parser.add_argument('--minutes', type=int, default=15,
                       help='Number of minutes to extract (default: 15)')
    parser.add_argument('--start-time', type=str, default='2025-08-12T21:00:00',
                       help='Start time for extraction (default: 2025-08-12T21:00:00)')
    
    args = parser.parse_args()
    
    print("🚀 Creating Test Subset for DDoS Detection Demo")
    print("=" * 60)
    print(f"📁 Input: {args.input}")
    print(f"📁 Output: {args.output}")
    print(f"⏱️  Duration: {args.minutes} minutes")
    print(f"🕐 Start time: {args.start_time}")
    print("=" * 60)
    
    try:
        subset = create_test_subset(args.input, args.output, args.start_time, args.minutes)
        print(f"\n✅ Test subset created successfully: {args.output}")
        print(f"📊 File size: {len(subset):,} records")
        
    except Exception as e:
        print(f"❌ Error creating subset: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

