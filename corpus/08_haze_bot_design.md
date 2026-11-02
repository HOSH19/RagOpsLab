# Haze Planner Product Notes

A practical haze planner combines a website and a Telegram bot. Users pick a region and receive outdoors-OK versus stay-indoors windows for the day.

## Architecture sketch

- Web app hosts the interactive plan view and live PM2.5
- Telegram bot answers `/plan` and `/now` with region pickers
- Nightly jobs ingest NEA history, retrain a small model, and export outlook JSON
- Hosting can be serverless for the bot webhook so no always-on laptop is required

## Quality gates

Before publishing new model weights, check holdout error against a baseline. If the new model is worse, keep the previous artifact. This is the same regression mindset used in LLM evals: do not ship silent quality drops.

## User messaging

Keep guidance short. Lead with the recommendation, then the PM2.5 number, then the time window. Avoid dumping raw sensor tables into chat.
