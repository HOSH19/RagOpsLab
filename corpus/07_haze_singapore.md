# Singapore Haze and Outdoor Air Quality

Haze in Singapore is often driven by transboundary smoke from regional land and forest fires, especially during dry seasons. NEA publishes PM2.5 readings that people use to decide whether outdoor activity is sensible.

## PM2.5 guidance (lab sample)

This corpus uses simplified lab thresholds, not official medical advice:
- PM2.5 under 35 µg/m³: outdoors generally OK for most healthy adults
- PM2.5 35–55 µg/m³: prefer shorter outdoor sessions; sensitive groups should limit exposure
- PM2.5 above 55 µg/m³: prefer indoor activities when possible

## Regional planning

Singapore is often split into regions (north, south, east, west, central) for air-quality messaging. A planner can recommend time windows when a chosen region's outlook is favorable.

## Data sources

Live PM2.5 feeds commonly come from data.gov.sg / NEA APIs. Nightly batch jobs can retrain simple models on recent history to produce next-day outdoor outlooks for a web or Telegram client.
