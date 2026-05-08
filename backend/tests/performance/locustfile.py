from __future__ import annotations

import itertools
import os
import random
from decimal import Decimal, InvalidOperation

from locust import HttpUser, between, task


def _comma_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _pick_next(values: list[str], fallback_name: str) -> str:
    if not values:
        raise RuntimeError(
            f"{fallback_name} is required for this Locust scenario. "
            f"Set {fallback_name} as a comma-separated environment variable."
        )

    if not hasattr(_pick_next, "_cycles"):
        _pick_next._cycles = {}

    cycles = _pick_next._cycles
    cycle = cycles.get(fallback_name)
    if cycle is None:
        cycle = itertools.cycle(values)
        cycles[fallback_name] = cycle
    return next(cycle)


class BrowseAndSearchUser(HttpUser):
    wait_time = between(0.2, 1.2)

    categories = [
        "pottery",
        "jewelry",
        "textiles",
        "woodwork",
        "leather",
        "candles",
        "paintings",
        "baskets",
        "glass",
        "decor",
    ]
    search_terms = [
        "handmade",
        "vase",
        "bracelet",
        "woven",
        "candle",
        "bowl",
        "linen",
        "wood",
        "ceramic",
        "art",
    ]
    sorts = ["newest", "popular", "price_asc", "price_desc"]

    @task(4)
    def browse_products(self) -> None:
        params = {
            "limit": 24,
            "offset": 0,
            "sort": random.choice(self.sorts),
        }
        self.client.get("/api/v1/products", params=params, name="/api/v1/products [browse]")

    @task(3)
    def search_products(self) -> None:
        params = {
            "search": random.choice(self.search_terms),
            "limit": 24,
            "sort": random.choice(self.sorts),
        }
        self.client.get("/api/v1/products", params=params, name="/api/v1/products [search]")

    @task(2)
    def browse_by_category(self) -> None:
        params = {
            "category": random.choice(self.categories),
            "limit": 24,
            "sort": random.choice(self.sorts),
        }
        self.client.get("/api/v1/products", params=params, name="/api/v1/products [category]")

    @task(1)
    def view_auctions(self) -> None:
        self.client.get("/api/v1/auctions", params={"view": "active", "limit": 12}, name="/api/v1/auctions [active]")


class SimultaneousBidUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.auction_id = os.getenv("LOCUST_AUCTION_ID", "").strip()
        if not self.auction_id:
            raise RuntimeError("LOCUST_AUCTION_ID is required for the bid load test.")

        token_list = _comma_list("LOCUST_BIDDER_TOKENS")
        self.access_token = _pick_next(token_list, "LOCUST_BIDDER_TOKENS")
        self.client.headers.update({"Authorization": f"Bearer {self.access_token}"})

    def _minimum_next_bid(self) -> Decimal | None:
        with self.client.get(f"/api/v1/auctions/{self.auction_id}", name="/api/v1/auctions/:id [detail]", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Failed to load auction detail: {response.status_code}")
                return None

            data = response.json()
            raw_minimum = data.get("minimum_next_bid")
            try:
                return Decimal(str(raw_minimum))
            except (InvalidOperation, TypeError):
                response.failure(f"Invalid minimum_next_bid payload: {raw_minimum!r}")
                return None

    @task
    def place_bid(self) -> None:
        for attempt in range(3):
            minimum_next_bid = self._minimum_next_bid()
            if minimum_next_bid is None:
                return

            payload = {"bid_amount": str(minimum_next_bid)}
            with self.client.post(
                f"/api/v1/auctions/{self.auction_id}/bids",
                json=payload,
                name="/api/v1/auctions/:id/bids [place]",
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    response.success()
                    return

                if response.status_code in {400, 409} and attempt < 2:
                    response.success()
                    continue

                if response.status_code in {400, 409}:
                    response.failure(
                        "Bid could not be placed after refreshing the minimum bid under concurrent load."
                    )
                    return

                response.failure(f"Unexpected status code: {response.status_code}")
                return
