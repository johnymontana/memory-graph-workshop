"""Geocoding client using OpenStreetMap Nominatim with caching."""

import os
import time
from typing import Optional, Dict, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import asyncio


class GeocodingClient:
    """Client for geocoding location entities using OpenStreetMap Nominatim."""

    def __init__(self):
        """Initialize the geocoding client with caching."""
        # User agent is required by Nominatim
        self.geolocator = Nominatim(
            user_agent="pydantic-ai-neo4j-memory-system/1.0",
            timeout=10
        )
        # In-memory cache for geocoding results
        self.cache: Dict[str, Tuple[float, float]] = {}
        # Rate limiting: Nominatim requires 1 req/sec
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds
    
    def _rate_limit(self):
        """Enforce rate limiting for Nominatim API (1 request per second)."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def geocode_location(
        self, 
        location_name: str,
        use_cache: bool = True
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode a location name to latitude and longitude.
        
        Args:
            location_name: Name of the location to geocode
            use_cache: Whether to use cached results
            
        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        if not location_name or not location_name.strip():
            return None
        
        # Normalize location name for cache lookup
        normalized_name = location_name.strip().lower()
        
        # Check cache first
        if use_cache and normalized_name in self.cache:
            print(f"✓ Geocoding cache hit for: {location_name}")
            return self.cache[normalized_name]
        
        try:
            # Enforce rate limiting
            self._rate_limit()
            
            print(f"Geocoding location: {location_name}")
            
            # Run geocoding in executor to avoid blocking
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None,
                self.geolocator.geocode,
                location_name
            )
            
            if location:
                lat_lng = (location.latitude, location.longitude)
                # Cache the result
                self.cache[normalized_name] = lat_lng
                print(f"✓ Geocoded {location_name}: {lat_lng}")
                return lat_lng
            else:
                print(f"⚠️  Could not geocode location: {location_name}")
                return None
                
        except GeocoderTimedOut:
            print(f"⚠️  Geocoding timeout for: {location_name}")
            return None
        except GeocoderServiceError as e:
            print(f"⚠️  Geocoding service error for {location_name}: {e}")
            return None
        except Exception as e:
            print(f"⚠️  Unexpected geocoding error for {location_name}: {e}")
            return None
    
    async def batch_geocode(
        self,
        locations: list[str],
        use_cache: bool = True
    ) -> Dict[str, Optional[Tuple[float, float]]]:
        """
        Geocode multiple locations, respecting rate limits.
        
        Args:
            locations: List of location names to geocode
            use_cache: Whether to use cached results
            
        Returns:
            Dictionary mapping location names to coordinates
        """
        results = {}
        
        for location in locations:
            coords = await self.geocode_location(location, use_cache)
            results[location] = coords
        
        return results
    
    def get_cached_location(self, location_name: str) -> Optional[Tuple[float, float]]:
        """
        Get a location from cache only (no API call).
        
        Args:
            location_name: Name of the location
            
        Returns:
            Tuple of (latitude, longitude) or None if not in cache
        """
        normalized_name = location_name.strip().lower()
        return self.cache.get(normalized_name)
    
    def clear_cache(self):
        """Clear the geocoding cache."""
        self.cache.clear()
        print("✓ Geocoding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_locations": len(self.cache),
            "cache_keys": list(self.cache.keys())
        }

