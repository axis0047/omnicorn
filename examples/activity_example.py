"""
Activity example demonstrating background task execution.

This example shows:
- Defining activities with retry logic
- Deferring activities for background execution
- Activity error handling
"""

from omnicorn import activity, defer_activity
import asyncio


@activity(name="fetch_data", retries=3)
async def fetch_data_activity(url: str):
    """Fetch data from an external API (simulated)."""
    print(f"🌐 Fetching data from {url}")
    await asyncio.sleep(1)
    return {"status": "success", "url": url}


@activity(name="transform_data", retries=2)
async def transform_data_activity(data: dict):
    """Transform fetched data (simulated)."""
    print(f"🔄 Transforming data: {data}")
    await asyncio.sleep(0.5)
    return {**data, "transformed": True}


@activity(name="store_data", retries=3)
async def store_data_activity(data: dict, destination: str):
    """Store transformed data (simulated)."""
    print(f"💾 Storing data to {destination}: {data}")
    await asyncio.sleep(1)
    return {"stored": True, "destination": destination}


async def run_data_pipeline(url: str, destination: str):
    """Run a data processing pipeline using activities."""
    print("🚀 Starting data pipeline")

    # Fetch data
    await defer_activity("fetch_data", url=url)

    # Transform (would normally wait for fetch to complete)
    # In a real workflow, you'd chain these properly

    # Store
    await defer_activity("store_data", data={"example": "data"}, destination=destination)

    print("✅ Data pipeline started")


if __name__ == "__main__":
    # This would be called from your application
    asyncio.run(run_data_pipeline("https://api.example.com/data", "s3://bucket/"))
