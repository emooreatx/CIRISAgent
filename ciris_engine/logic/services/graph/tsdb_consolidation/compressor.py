"""
Compression utilities for profound consolidation.

This module handles in-place compression of daily summaries for long-term storage efficiency.
Future versions will include multimedia compression for images, video, and telemetry data.
"""

import json
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SummaryCompressor:
    """Handles compression of summary nodes for profound consolidation."""
    
    def __init__(self, target_mb_per_day: float):
        """
        Initialize the compressor.
        
        Args:
            target_mb_per_day: Target size in MB per day after compression
        """
        self.target_mb_per_day = target_mb_per_day
    
    def compress_summary(self, attributes: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """
        Compress a summary's attributes in-place.
        
        Args:
            attributes: The summary attributes to compress
            
        Returns:
            Tuple of (compressed_attributes, size_reduction_ratio)
        """
        original_size = len(json.dumps(attributes))
        compressed = attributes.copy()
        
        # Current compression strategies (text-based)
        compressed = self._compress_metrics(compressed)
        compressed = self._compress_descriptions(compressed)
        compressed = self._remove_redundancy(compressed)
        
        # Future compression strategies
        # compressed = self._compress_images(compressed)
        # compressed = self._compress_video_thumbnails(compressed)
        # compressed = self._compress_telemetry_data(compressed)
        
        compressed_size = len(json.dumps(compressed))
        reduction_ratio = 1.0 - (compressed_size / original_size)
        
        return compressed, reduction_ratio
    
    def _compress_metrics(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress metrics by keeping only significant patterns.
        
        Args:
            attrs: Attributes containing metrics
            
        Returns:
            Attributes with compressed metrics
        """
        if 'metrics' not in attrs:
            return attrs
        
        metrics = attrs['metrics']
        
        # Keep only metrics with significant values
        significant_metrics = {}
        for metric_name, metric_data in metrics.items():
            if isinstance(metric_data, dict):
                # Keep metric if it has meaningful activity
                if metric_data.get('count', 0) > 10 or metric_data.get('sum', 0) > 100:
                    # Reduce precision for storage
                    compressed_data = {
                        'c': metric_data.get('count', 0),  # Shortened keys
                        's': round(metric_data.get('sum', 0), 2),
                        'a': round(metric_data.get('avg', 0), 2)
                    }
                    significant_metrics[metric_name] = compressed_data
            elif isinstance(metric_data, (int, float)) and metric_data > 0:
                significant_metrics[metric_name] = round(metric_data, 2)
        
        attrs['metrics'] = significant_metrics
        return attrs
    
    def _compress_descriptions(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress text descriptions by removing redundancy.
        
        Args:
            attrs: Attributes containing descriptions
            
        Returns:
            Attributes with compressed descriptions
        """
        # Compress conversation summaries
        if 'messages_by_channel' in attrs:
            compressed_channels = {}
            for channel, data in attrs['messages_by_channel'].items():
                # Keep only channel ID and count
                compressed_channels[channel] = data.get('count', 0)
            attrs['messages_by_channel'] = compressed_channels
        
        # Compress participant data
        if 'participants' in attrs:
            compressed_participants = {}
            for user_id, data in attrs['participants'].items():
                # Keep only essential data
                compressed_participants[user_id] = {
                    'msg_count': data.get('message_count', 0),
                    'name': data.get('author_name', '')[:20]  # Truncate names
                }
            attrs['participants'] = compressed_participants
        
        # Remove verbose fields
        verbose_fields = [
            'detailed_description',
            'full_context',
            'raw_data',
            'debug_info'
        ]
        for field in verbose_fields:
            attrs.pop(field, None)
        
        return attrs
    
    def _remove_redundancy(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove redundant information from attributes.
        
        Args:
            attrs: Attributes to clean
            
        Returns:
            Attributes with redundancy removed
        """
        # Remove duplicate timestamp formats
        if 'period_start' in attrs and 'start_time' in attrs:
            attrs.pop('start_time', None)
        if 'period_end' in attrs and 'end_time' in attrs:
            attrs.pop('end_time', None)
        
        # Consolidate error information
        if 'errors' in attrs and isinstance(attrs['errors'], list):
            # Keep only error count and types
            error_types = {}
            for error in attrs['errors']:
                error_type = error.get('type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1
            attrs['error_summary'] = error_types
            attrs.pop('errors', None)
        
        # Remove low-value fields
        low_value_fields = [
            'created_by',
            'updated_by',
            'version',
            'internal_id'
        ]
        for field in low_value_fields:
            attrs.pop(field, None)
        
        return attrs
    
    def estimate_daily_size(self, summaries: List[Dict[str, Any]], days_in_period: int) -> float:
        """
        Estimate the daily storage size for a set of summaries.
        
        Args:
            summaries: List of summary attributes
            days_in_period: Number of days covered by these summaries
            
        Returns:
            Estimated MB per day
        """
        total_size = sum(len(json.dumps(s)) for s in summaries)
        size_mb = total_size / (1024 * 1024)
        return size_mb / days_in_period if days_in_period > 0 else 0
    
    def needs_compression(self, summaries: List[Dict[str, Any]], days_in_period: int) -> bool:
        """
        Check if summaries need compression based on target size.
        
        Args:
            summaries: List of summary attributes
            days_in_period: Number of days covered
            
        Returns:
            True if compression is needed
        """
        current_daily_mb = self.estimate_daily_size(summaries, days_in_period)
        return current_daily_mb > self.target_mb_per_day
    
    # Future multimedia compression methods
    
    def _compress_images(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Future: Compress embedded images using lossy compression.
        
        Will handle:
        - Converting to JPEG with quality reduction
        - Resizing to thumbnails
        - Extracting key frames only
        """
        # TODO: Implement when image support is added
        return attrs
    
    def _compress_video_thumbnails(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Future: Compress video data to thumbnails and metadata.
        
        Will handle:
        - Extracting keyframes
        - Creating timeline thumbnails
        - Keeping only metadata (duration, resolution, codec)
        """
        # TODO: Implement when video support is added
        return attrs
    
    def _compress_telemetry_data(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Future: Compress robotic/sensor telemetry data.
        
        Will handle:
        - Downsampling time series data
        - Statistical aggregation (min/max/avg/std)
        - Anomaly detection and preservation
        """
        # TODO: Implement when telemetry support is added
        return attrs