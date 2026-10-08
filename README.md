# Stroller Price Tracker

A Python-based automation project that monitors product prices across multiple e-commerce websites, stores price history, and sends notifications through Telegram.

The project runs automatically on a scheduled basis using GitHub Actions and includes automated tests with pytest.

## Features

* Automated price monitoring across multiple websites
* Multiple price extraction strategies:

  * JSON-LD structured data
  * HTML meta tags
  * Configurable CSS selectors
* Persistent price history stored in CSV
* Automatic detection of price changes
* Telegram notifications for price changes and daily summaries
* Error handling for HTTP failures, timeouts, and bot protection
* Automated testing with pytest
* Scheduled execution using GitHub Actions
* Secure Telegram credentials using GitHub Actions Secrets

## Architecture

```text
GitHub Actions
      │
      ▼
Install dependencies
      │
      ▼
Run automated tests
      │
      ▼
Run price tracker
      │
      ├──► E-commerce websites
      │
      ├──► Price extraction
      │
      ├──► CSV price history
      │
      └──► Telegram Bot API
                │
                ▼
           Notifications
```

## Technologies

* Python 3.12
* Requests
* BeautifulSoup
* lxml
* pytest
* Git
* GitHub Actions
* GitHub Actions Secrets
* Telegram Bot API
* CSV

## Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── daily-price-check.yml
├── tests/
│   └── test_price_tracker.py
├── StrollerPriceTracker.py
├── requirements.txt
├── pytest.ini
├── price_history.csv
└── README.md
```

## Automated Testing

The project uses pytest for automated testing.

Tests cover core functionality such as:

* Price string parsing
* JSON-LD price extraction
* Handling of missing price data

Tests can be executed locally with:

```bash
pytest
```

The GitHub Actions workflow runs the tests before starting the price monitoring process.

If a test fails, the workflow stops and the price tracker is not executed.

## GitHub Actions

The application is executed automatically using GitHub Actions.

The workflow:

1. Checks out the repository
2. Sets up Python
3. Installs dependencies
4. Runs automated tests
5. Runs the price monitoring application
6. Saves updated price history back to the repository

The workflow can also be started manually using GitHub Actions.

## Configuration

Telegram credentials are provided through environment variables:

```text
TELEGRAM_TOKEN
TELEGRAM_CHAT_ID
```

The credentials are stored as GitHub Actions Secrets and are not committed to the repository.

## Error Handling

The application handles common operational problems including:

* HTTP request failures
* Request timeouts
* HTTP 403 and 429 responses
* Potential bot protection
* Missing price data
* Telegram API failures

Application events and errors are reported using Python's logging module.

## Example Use Case

The original use case was monitoring the price of a baby stroller across several Bulgarian e-commerce websites.

The system automatically checks the configured websites, compares prices with previously recorded values, stores the latest results, and sends a Telegram notification when a price changes.

## Future Improvements

Possible future improvements include:

* Database storage instead of CSV
* Additional e-commerce websites
* More comprehensive test coverage
* Docker containerization
* Improved monitoring and alerting
* Configurable price thresholds
* Web dashboard for price history

## Author

Mario Petrov

GitHub: [MPetrov23](https://github.com/MPetrov23)
