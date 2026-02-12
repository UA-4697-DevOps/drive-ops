#!/usr/bin/env python3
"""
Health Check Smoke Test for Drive-Ops services.

Checks availability of all services through their health endpoints.
"""

import os
import sys
import time
from typing import Dict, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Colors:
    """ANSI color codes for formatted output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def create_session() -> requests.Session:
    """
    Creates a requests session with retry logic.
    
    Returns:
        Session with configured retry parameters
    """
    session = requests.Session()
    
    # Retry logic: 3 attempts, 5 seconds between attempts
    retry_strategy = Retry(
        total=3,
        backoff_factor=5,  # 5 seconds between attempts
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def check_service(
    session: requests.Session,
    name: str,
    url: str,
    expected_status: int = 200,
    validate_json: bool = False,
    service_type: str = "http"
) -> Tuple[bool, str]:
    """
    Checks one service.
    
    Args:
        session: requests session
        name: service name
        url: URL to check
        expected_status: expected HTTP status code
        validate_json: whether to validate JSON response
        service_type: service type ("http" or "telegram_bot")
    
    Returns:
        Tuple[success, message]
    """
    try:
        print(f"  Checking {name}...", end=' ', flush=True)
        
        response = session.get(url, timeout=10)
        
        # Check status code
        if response.status_code != expected_status:
            msg = f"HTTP {response.status_code} (expected {expected_status})"
            return False, msg
        
        # Validate JSON depending on service type
        if validate_json:
            try:
                data = response.json()
                if service_type == "telegram_bot":
                    # For Telegram API expect {"ok": true}
                    if not data.get("ok"):
                        return False, f"Telegram API error: {data.get('description', 'Unknown error')}"
                else:
                    # For HTTP services accept both "ok" and "healthy" as valid statuses
                    if data.get("status") not in ["ok", "healthy"]:
                        return False, f"Invalid response: {data}"
            except ValueError as e:
                return False, f"Invalid JSON: {str(e)}"
        
        return True, "OK"
        
    except requests.exceptions.Timeout:
        return False, "Timeout after 10s (tried 3 times)"
    except requests.exceptions.ConnectionError as e:
        if "Connection reset by peer" in str(e):
            return False, f"Service appears to be down (connection reset): Port may be closed or service crashed"
        elif "Connection refused" in str(e):
            return False, f"Service not running (connection refused): Check if service is started"
        else:
            return False, f"Connection error: {str(e)}"
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def print_header():
    """Prints the test header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  Drive-Ops Health Check Smoke Test{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_results(results: Dict[str, Tuple[bool, str, str]]):
    """
    Prints results in table format.
    
    Args:
        results: Dict with check results {service_name: (success, url, message)}
    """
    print(f"\n{Colors.BOLD}Results:{Colors.END}\n")
    print(f"{'Service':<20} {'Status':<15} {'Details'}")
    print("-" * 70)
    
    for service_name, (success, url, message) in results.items():
        status_icon = f"{Colors.GREEN}✅ OK{Colors.END}" if success else f"{Colors.RED}❌ FAIL{Colors.END}"
        status_text = f"{status_icon:<24}"  # 24 to compensate for ANSI codes
        
        # Shorten URL for compactness
        if "api.telegram.org" in url:
            # For Telegram API hide token
            short_url = "api.telegram.org/bot..."
        else:
            short_url = url.replace("http://", "").replace("https://", "")
            if len(short_url) > 40:
                short_url = short_url[:37] + "..."
        
        details = message if not success else short_url
        print(f"{service_name:<20} {status_text} {details}")
    
    print("-" * 70)


def main():
    """Main function."""
    print_header()
    
    # Read URLs from environment variables
    services = {
        "Trip Service": {
            "url_env": "SMOKE_TRIP_SERVICE_URL",
            "endpoint": "/health",
            "validate_json": True,
            "type": "http"
        },
        "Driver Service": {
            "url_env": "SMOKE_DRIVER_SERVICE_URL",
            "endpoint": "/health",
            "validate_json": True,
            "type": "http"
        },
        "Client Gateway": {
            "url_env": "SMOKE_CLIENT_GATEWAY_URL",
            "endpoint": "/health",
            "validate_json": True,
            "type": "http"
        }
    }
    
    # Check for required env variables
    missing_vars = []
    for service_name, config in services.items():
        env_var = config["url_env"]
        if not os.getenv(env_var):
            missing_vars.append(env_var)
    
    if missing_vars:
        print(f"{Colors.RED}Error: Missing required environment variables:{Colors.END}")
        for var in missing_vars:
            print(f"  - {var}")
        print(f"\n{Colors.YELLOW}Example:{Colors.END}")
        print(f"  export SMOKE_TRIP_SERVICE_URL=http://trip-service.example.com:8081")
        print(f"  export SMOKE_DRIVER_SERVICE_URL=http://driver-service.example.com:8082")
        print(f"  export SMOKE_CLIENT_GATEWAY_URL=http://client-gateway.example.com:8080")
        sys.exit(1)
    
    # Create session with retry logic
    session = create_session()
    
    # Check all services
    results = {}
    all_success = True
    
    print(f"{Colors.BOLD}Running health checks...{Colors.END}\n")
    
    for service_name, config in services.items():
        # Form URL depending on service type
        if config["type"] == "telegram_bot":
            bot_token = os.getenv(config["url_env"])
            full_url = f"https://api.telegram.org/bot{bot_token}{config['endpoint']}"
        else:
            base_url = os.getenv(config["url_env"])
            full_url = base_url.rstrip("/") + config["endpoint"]
        
        success, message = check_service(
            session,
            service_name,
            full_url,
            validate_json=config["validate_json"],
            service_type=config["type"]
        )
        
        results[service_name] = (success, full_url, message)
        all_success = all_success and success
        
        # Print result immediately
        if success:
            print(f"{Colors.GREEN}✅{Colors.END}")
        else:
            print(f"{Colors.RED}❌ {message}{Colors.END}")
        
        # Small pause between requests
        time.sleep(0.5)
    
    # Print summary table
    print_results(results)
    
    # Final message
    if all_success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All services are healthy!{Colors.END}\n")
        sys.exit(0)
    else:
        failed_count = sum(1 for success, _, _ in results.values() if not success)
        print(f"\n{Colors.RED}{Colors.BOLD}❌ {failed_count} service(s) failed health check!{Colors.END}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
